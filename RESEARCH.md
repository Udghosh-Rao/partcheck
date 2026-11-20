# Research

## The problem in one line
This is a **golden-sample comparison**: one image of a good board, a fixed camera, user-named regions, and a yes/no for each region.
The industry name is AOI (Automated Optical Inspection), specifically *component presence/absence* checking.

## What exists

| Source | What it is | Takeaway for us |
|---|---|---|
| Commercial AOI machines (Koh Young, Omron, Saki, Mirtec…) | Inline inspection with a golden board, per-component "windows" and similarity thresholds | Our UX copies this proven pattern: *teach once by drawing windows, then compare each window*. |
| OpenCV feature matching + homography tutorial: https://docs.opencv.org/4.x/d1/de0/tutorial_py_feature_homography.html | ORB/SIFT + RANSAC to register two views of a planar object | A PCB is planar, so a homography is the right model for registration. |
| OpenCV template matching: https://docs.opencv.org/4.x/d4/dc6/tutorial_py_template_matching.html | `TM_CCOEFF_NORMED` (normalised cross-correlation) | Does not change with brightness or contrast. We use it for the per-part decision. |
| ECC image alignment (Evangelidis & Psarakis, 2008; `cv2.findTransformECC`) | Intensity-based alignment | Used as a fallback when a board has few features. |
| SSIM (Wang et al., 2004) | Structural similarity | Considered, but it is more sensitive to small shifts than NCC with a search window. |
| PatchCore, "Towards Total Recall in Industrial Anomaly Detection": https://arxiv.org/abs/2106.08265 | Unsupervised anomaly detection from good images only | Strong, but needs many good images, a backbone download and a GPU or slow CPU, and it gives an anomaly map instead of *named* parts. |
| PaDiM: https://arxiv.org/abs/2011.08785 | Same family as PatchCore | Same reasons. |
| Anomalib (Intel): https://github.com/openvinotoolkit/anomalib | Library implementing PatchCore, PaDiM, … | A good choice if many good images exist later (see Future work). |
| YOLO-style component detectors | Supervised detection of classes like resistor or capacitor | Needs labelled training data for *these* parts. The demo board and part names are unknown in advance. |

## Data sources looked at

| Dataset | Link | Fit |
|---|---|---|
| DeepPCB | https://github.com/tangsanli5201/DeepPCB | Template and test pairs, but defects are on bare-board traces (opens, shorts), not missing components. Useful for the *template + test* idea. |
| MVTec AD | https://www.mvtec.com/company/research/datasets/mvtec-ad | Industrial anomaly benchmark with no PCB components. Background only. |
| PKU-Market-PCB / surface-defect collections | https://github.com/Charmve/Surface-Defect-Detection (index of many datasets) | Mostly bare-PCB defects (missing hole, mouse bite). Not component absence. |

Most public datasets cover bare-board defects (broken traces, missing holes). None matched "same board, same camera, named components, some removed".
So I don't ship any dataset. The app needs only what the brief says the examiners will bring: one reference photo plus up to 3 photos of the same board.
For my own testing I use photos of one board taken from a fixed position, plus `tools/evaluate.py` to score them against a hand-written `ground_truth.json`.
Any AI-generated test photos are used only to test, never inside the app, as the rules require.

## Options compared

| Option | Data needed | Offline/CPU | Names parts? | Explainable | Verdict |
|---|---|---|---|---|---|
| Pixel diff after alignment | 1 image | ✅ | via boxes | medium | ❌ too sensitive to lighting and small shifts, so many false alarms |
| **Alignment + per-box NCC (chosen)** | **1 image** | **✅ ~0.2 s** | **✅** | **✅ score per part** | ✅ |
| SSIM per box | 1 image | ✅ | ✅ | ✅ | ➖ similar, less tolerant of shifts |
| PatchCore / PaDiM anomaly | 50–200 good images | slow on CPU, weights download | ❌ (heatmap) | low | ❌ for this brief |
| YOLO component detector | 100s of labelled images | ✅ after training | only trained classes | medium | ❌ no data, unknown parts |
| Cloud vision LLM | none | ❌ online | ✅ | low | ❌ forbidden by the rules |

## Decision
Classical registration + per-part normalised cross-correlation. This is what real AOI machines do,
it needs exactly what the brief provides (one reference + named boxes), runs offline on a laptop,
and every decision comes with a number the operator can see.

## Future work
- Switch to SIFT, which has shipped with OpenCV since 4.4, for very low-texture boards.
- With a few dozen good photos per board, learn a per-part threshold (mean − k·std of its "present" scores).
- Optional PatchCore on top to flag *unexpected* defects outside the named boxes.
