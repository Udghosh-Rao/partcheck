"""Core inspection logic: align a test photo to the reference, then check each named part.

Pipeline (all classical OpenCV, runs offline on CPU):
  1. Resize both images to a working size.
  2. Align test -> reference with ORB features + RANSAC homography
     (fallback: ECC affine, fallback: plain resize since the camera is fixed).
  3. For every named part, crop a padded patch from the reference and search for it
     in a slightly larger window of the aligned test image (absorbs small residual shifts).
  4. Similarity = normalized cross-correlation on grayscale AND on edge maps
     (NCC is invariant to brightness/contrast changes), plus a colour-shift check.
  5. Part is "missing" if the combined score falls below a threshold.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, asdict

import cv2
import numpy as np

WORK_SIZE = 1400          # longest side used for processing
DEFAULT_THRESHOLD = 0.55  # combined score below this -> missing


@dataclass
class PartResult:
    name: str
    present: bool
    score: float          # 0..1, higher = more like the reference
    polygon: list         # 4 [x, y] points in ORIGINAL test-image pixel coords


def _resize(img: np.ndarray, size: int = WORK_SIZE):
    h, w = img.shape[:2]
    s = size / max(h, w)
    if s >= 1:
        return img.copy(), 1.0
    return cv2.resize(img, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA), s


def decode_image(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not read image (unsupported or corrupt file)")
    return img


# --------------------------------------------------------------------------- alignment
def align(ref: np.ndarray, test: np.ndarray):
    """Return (H, method, inliers). H maps test(work) coords -> ref(work) coords."""
    g_ref = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
    g_test = cv2.cvtColor(test, cv2.COLOR_BGR2GRAY)
    # CLAHE makes features robust to lighting differences
    clahe = cv2.createCLAHE(2.0, (8, 8))
    g_ref, g_test = clahe.apply(g_ref), clahe.apply(g_test)

    orb = cv2.ORB_create(nfeatures=6000, fastThreshold=10)
    k1, d1 = orb.detectAndCompute(g_ref, None)
    k2, d2 = orb.detectAndCompute(g_test, None)
    if d1 is not None and d2 is not None and len(k1) > 20 and len(k2) > 20:
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
        pairs = matcher.knnMatch(d2, d1, k=2)
        good = [m for m, n in (p for p in pairs if len(p) == 2) if m.distance < 0.78 * n.distance]
        if len(good) >= 15:
            src = np.float32([k2[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst = np.float32([k1[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
            if H is not None and _sane(H, ref.shape, test.shape):
                inl = int(mask.sum())
                if inl >= 12:
                    return H, "features", inl

    # Fallback: ECC affine on downscaled images (handles low-texture boards)
    sx, sy = ref.shape[1] / test.shape[1], ref.shape[0] / test.shape[0]
    S = np.array([[sx, 0, 0], [0, sy, 0], [0, 0, 1]], np.float64)
    try:
        small = 400 / max(g_ref.shape)
        a = cv2.resize(g_ref, None, fx=small, fy=small).astype(np.float32)
        b = cv2.resize(cv2.warpPerspective(g_test, S, (ref.shape[1], ref.shape[0])), None,
                       fx=small, fy=small).astype(np.float32)
        warp = np.eye(2, 3, dtype=np.float32)
        _, warp = cv2.findTransformECC(a, b, warp, cv2.MOTION_AFFINE,
                                       (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-5),
                                       None, 5)
        W = np.vstack([warp, [0, 0, 1]]).astype(np.float64)
        W[0, 2] /= small
        W[1, 2] /= small
        # ECC gives ref->test mapping; invert for test->ref
        H = np.linalg.inv(W) @ S
        return H, "ecc", 0
    except cv2.error:
        return S, "fixed-camera", 0


def _sane(H, ref_shape, test_shape) -> bool:
    """Reject degenerate homographies (flips, huge scale, strong perspective)."""
    h, w = test_shape[:2]
    corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
    p = cv2.perspectiveTransform(corners, H).reshape(-1, 2)
    area = cv2.contourArea(p.astype(np.float32))
    ref_area = ref_shape[0] * ref_shape[1]
    return cv2.isContourConvex(p.astype(np.float32)) and 0.3 * ref_area < area < 3.0 * ref_area


# --------------------------------------------------------------------------- comparison
def _ncc(a: np.ndarray, b_window: np.ndarray) -> float:
    if a.std() < 1e-3 and b_window.std() < 1e-3:
        return 1.0
    res = cv2.matchTemplate(b_window, a, cv2.TM_CCOEFF_NORMED)
    v = float(res.max())
    return 0.0 if np.isnan(v) else v


def _edges(g: np.ndarray) -> np.ndarray:
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    return cv2.GaussianBlur(cv2.magnitude(gx, gy), (3, 3), 0)


def _match_colors(ref: np.ndarray, test: np.ndarray) -> np.ndarray:
    """Match global per-channel mean/std of test to ref in LAB (lighting normalisation)."""
    r = cv2.cvtColor(ref, cv2.COLOR_BGR2LAB).astype(np.float32)
    t = cv2.cvtColor(test, cv2.COLOR_BGR2LAB).astype(np.float32)
    valid = t.sum(axis=2) > 0
    for c in range(3):
        rm, rs = r[..., c].mean(), r[..., c].std() + 1e-6
        tm, ts = t[..., c][valid].mean(), t[..., c][valid].std() + 1e-6
        t[..., c] = (t[..., c] - tm) / ts * rs + rm
    return cv2.cvtColor(np.clip(t, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)


def compare_part(ref: np.ndarray, aligned: np.ndarray, box) -> float:
    """box = (x, y, w, h) in ref work pixels. Returns similarity 0..1."""
    H, W = ref.shape[:2]
    x, y, w, h = box
    pad = int(round(0.15 * max(w, h))) + 2
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(W, x + w + pad), min(H, y + h + pad)
    tmpl = ref[y0:y1, x0:x1]
    # search window allows residual misalignment
    s = max(6, int(0.25 * max(w, h)), int(0.01 * max(W, H)))
    sx0, sy0 = max(0, x0 - s), max(0, y0 - s)
    sx1, sy1 = min(W, x1 + s), min(H, y1 + s)
    win = aligned[sy0:sy1, sx0:sx1]
    if win.shape[0] < tmpl.shape[0] or win.shape[1] < tmpl.shape[1] or tmpl.size == 0:
        return 0.0

    gt = cv2.cvtColor(tmpl, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gw = cv2.cvtColor(win, cv2.COLOR_BGR2GRAY).astype(np.float32)
    s_gray = _ncc(gt, gw)
    s_edge = _ncc(_edges(gt), _edges(gw))

    # find best location, then compare colour of the inner part region (catches same-shape
    # but different-colour cases e.g. bare pad vs. component of similar outline)
    res = cv2.matchTemplate(gw, gt, cv2.TM_CCOEFF_NORMED)
    _, _, _, loc = cv2.minMaxLoc(res)
    ix, iy = x - x0, y - y0
    inner_ref = tmpl[iy:iy + h, ix:ix + w]
    inner_test = win[loc[1] + iy: loc[1] + iy + h, loc[0] + ix: loc[0] + ix + w]
    color_pen = 0.0
    if inner_ref.shape == inner_test.shape and inner_ref.size:
        lr = cv2.cvtColor(inner_ref, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32).mean(0)
        lt = cv2.cvtColor(inner_test, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32).mean(0)
        de = float(np.linalg.norm(lr - lt))
        color_pen = float(np.clip((de - 18) / 40, 0, 0.5))  # tolerate small colour drift

    score = 0.5 * max(s_gray, 0) + 0.5 * max(s_edge, 0) - color_pen
    return float(np.clip(score, 0, 1))


# --------------------------------------------------------------------------- public API
def inspect(ref_img: np.ndarray, test_img: np.ndarray, parts: list[dict],
            threshold: float = DEFAULT_THRESHOLD) -> dict:
    """parts: [{name, x, y, w, h}] with coords normalised 0..1 relative to the reference."""
    ref, _ = _resize(ref_img)
    test, ts = _resize(test_img)
    H, method, inliers = align(ref, test)
    RH, RW = ref.shape[:2]
    aligned = cv2.warpPerspective(test, H, (RW, RH), flags=cv2.INTER_LINEAR,
                                  borderMode=cv2.BORDER_CONSTANT)
    aligned = _match_colors(ref, aligned)

    # mapping ref(work) -> original test pixels, for drawing on the user's photo
    Hinv = np.linalg.inv(H)
    back = np.diag([1 / ts, 1 / ts, 1]) @ Hinv

    results = []
    for p in parts:
        bx = (int(p["x"] * RW), int(p["y"] * RH), max(4, int(p["w"] * RW)), max(4, int(p["h"] * RH)))
        score = compare_part(ref, aligned, bx)
        x, y, w, h = bx
        pts = np.float32([[x, y], [x + w, y], [x + w, y + h], [x, y + h]]).reshape(-1, 1, 2)
        poly = cv2.perspectiveTransform(pts, back).reshape(-1, 2).round(1).tolist()
        results.append(PartResult(p["name"], score >= threshold, round(score, 3), poly))

    missing = [r.name for r in results if not r.present]
    return {
        "ok": not missing,
        "missing": missing,
        "parts": [asdict(r) for r in results],
        "alignment": {"method": method, "inliers": inliers},
        "aligned_preview": _b64(aligned),
        "size": [int(test_img.shape[1]), int(test_img.shape[0])],
    }


def _b64(img: np.ndarray) -> str:
    small, _ = _resize(img, 900)
    ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode()
