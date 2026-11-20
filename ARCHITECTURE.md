# Architecture

Diagram made with [Archify](https://github.com/tt-a1i/archify) (v3.2.0): source `docs/architecture.json`,
interactive version `docs/architecture.html`.

![architecture](docs/architecture.png)

## Flow

**Setup (once):** the user uploads a reference photo, which is saved to `data/reference.png`. The user then draws and names boxes,
which are saved to `data/parts.json` as 0–1 coordinates, so they do not depend on image size.

**Inspect (per photo)** in `inspector.inspect()`:

1. **Resize** both images so the longest side is at most 1400 px.
2. **Align** the photo to the reference: ORB features (6000) after CLAHE, then ratio-test matching and a RANSAC homography.
   A sanity check rejects flipped or degenerate homographies. Fallbacks: ECC affine, then plain rescaling, since the camera is fixed.
3. **Normalise lighting**: match the photo's LAB mean and standard deviation to the reference.
4. **Compare each part**: take the part box from the reference with 15% padding as a template and search for it in a slightly larger
   window of the aligned photo. This absorbs small leftover misalignment.
   Score = 0.5·NCC(grayscale) + 0.5·NCC(edge magnitude) − colour-shift penalty (ΔE in LAB).
5. **Decide**: score < threshold (0.55 by default, adjustable in the UI) means the part is missing.
6. **Draw**: project each box back through the inverse homography onto the user's original photo, then draw it in the browser as SVG.

## Trade-offs

| Chose | Gave up | Why |
|---|---|---|
| **Classical CV (registration + template matching)** instead of a trained detector (YOLO) or anomaly model (PatchCore) | Robustness to big changes in lighting or viewpoint, and to parts that look like the bare board | The brief gives one reference photo and no data. Users name the parts at demo time, so any class set would be unknown in advance. Classical matching works from a single photo, needs no GPU, runs in about 0.2 s, and the score is easy to explain. |
| **Per-part comparison inside the user's boxes** instead of a whole-image diff | It cannot report damage outside the named boxes | The question is "which named part is missing". Checking only the boxes ignores glare, cables or dust elsewhere, which keeps false alarms low. |
| **NCC on grayscale and edges** instead of a raw pixel difference or SSIM | Some sensitivity to subtle colour-only changes (partly covered by the ΔE penalty) | NCC does not change with brightness or contrast, so a darker or brighter photo does not trigger alarms. Edges catch a part whose shape disappears. |
| **Local search window** instead of trusting the homography exactly | A small risk of matching a neighbouring look-alike part | Homographies are never perfect on real photos (lens distortion, board flex). A ±25% search window removes most false alarms. |
| **One global threshold + UI slider** instead of a per-part learned threshold | Optimal per-part tuning | No good/bad training examples are available at demo time. The slider lets the operator adjust it live, and the score chips show why each decision was made. |
| **Flask + plain HTML/JS** instead of React/Streamlit | Less built-in UI tooling | No CDN or build step, so it works offline. It is about 300 lines of UI I fully control (box drawing, SVG overlays). |
| **Server stores one project in `data/`** instead of a multi-board database | Several boards at once | The demo uses one board. Keeping it simple reduces risk during the live demo. |

## Known limits

- The camera must be roughly the same as the reference (the brief guarantees this). Large rotations above about 30° or a very different zoom may fail alignment.
- If a part looks like its bare footprint (for example a tiny 0402 resistor on a matching pad), the score margin shrinks. Use a tighter box or raise the sensitivity.
- Strong specular glare inside a part's box can lower its score.
