# AI collaboration

**Me:** Udghosh Rao. **Task:** B. **AI tool:** Claude Code (Claude Opus 5.5) in the Claude desktop app.
**Full chat history:** `chat_history/`. These are exported session files, starting from my very first prompt.

## How I worked with the AI
I pasted the whole Task B brief and set my constraints: Task B, move fast, don't waste effort, it has to work in the live demo.
The AI proposed a design, built it and tested it. I reviewed each result and steered it.
The biggest correction was removing its generated dummy data and making the repo follow the PDF brief exactly (Decision 6).

---

## Decision 1: which task
**AI suggested:** it went straight to Task B, the one I attached.
**I decided:** Task B, "Which Part Is Missing?"
**Why:** it is a concrete vision problem with a clear yes or no answer per part, so it is easy to demo and to check.
**Evidence:** chat excerpt #1.

## Decision 2: classical computer vision, not deep learning
**AI suggested:** align the photo to the reference with ORB features + RANSAC homography, then compare each named part with normalised cross-correlation. It rejected YOLO (needs labelled training data) and PatchCore/PaDiM (needs many good images and gives no part names).
**I decided:** classical CV.
**Why:** at the demo the examiners bring a board I have never seen and name the parts themselves. Nothing can be trained in advance. All I get is one reference photo, and the method has to work from that.
**Evidence:** RESEARCH.md "Options compared"; chat excerpt #2.

## Decision 3: compare only inside the named boxes
**AI suggested:** score only the regions the user drew, with 15% padding and a small search window around each.
**I decided:** keep it.
**Why:** the brief asks "which *named* parts are missing". A whole-image diff would raise alarms for glare, dust or a cable that are not parts. The search window absorbs small alignment errors.
**Evidence:** `inspector.compare_part()`.

## Decision 4: a score that survives lighting changes
**AI suggested:** 50% NCC on grayscale + 50% NCC on edges, minus a LAB colour-shift penalty, instead of a pixel difference.
**I decided:** keep it.
**Why:** factory lighting drifts. NCC does not change with brightness or contrast, edges catch a part whose shape is gone, and colour catches a bare pad that has a similar outline.
**Evidence:** UI test with shifted, rotated, 0.8× and 1.15× brightness photos: correct OK / R1 missing / U1 missing (chat history).

## Decision 5: a local web page instead of a CLI
**AI suggested:** Flask + one plain HTML/JS page with 3 steps (Reference → Name parts → Inspect), boxes drawn with the mouse, and a big green OK / red MISSING.
**I decided:** a web page with no external JS/CSS libraries, and a polished UI.
**Why:** the UI is part of the score and the users are shop-floor operators. A CDN-based framework could break offline, and drawing boxes in a terminal is not possible.
**Evidence:** `static/`; chat excerpt #3.

## Decision 6: no dummy data in the repo
**AI suggested:** a procedural "fake PCB" generator with 15 synthetic test photos and an accuracy report on them (it reported 15/15).
**I decided:** remove the fake data and the generator. Keep only an evaluation tool that works on *real* labelled photos.
**Why:** synthetic boards drawn as rectangles prove little about the examiners' real photos, and 15/15 on easy fake data could mislead a reviewer. The brief asks for the platform, not a dataset.
**Evidence:** chat excerpt #3; `tools/evaluate.py` now reads any folder with `reference.*` + `ground_truth.json`.

## Decision 7: operator control and output
**AI suggested:** a fixed threshold of 0.55.
**I decided:** add a Sensitivity slider, a score chip per part (click it to highlight the part), a summary bar (photos checked / OK / missing), and a CSV export.
**Why:** unseen demo photos may score closer to the threshold. Being able to adjust it live and *see* why each decision was made is safer than a hidden constant. A factory also needs a record of each inspection.
**Evidence:** UI ⚙ Sensitivity panel, `/api/settings`, "Export CSV" button.

---

## Chat excerpt #1: kickoff
> **me:** *(pasted the full Task B brief)* … you have github access do code and fast dont burn unnecessary token just make, i prepare for internship they give work
>
> **AI:** Plan: check tools (python, opencv, gh) → build backend: align + per-part compare → build web UI (upload, label, inspect) → generate synthetic test boards and verify → write README, AI_COLLAB, RESEARCH, ARCHITECTURE → create public GitHub repo and push.

## Chat excerpt #2: the design
> **AI (design notes in inspector.py):** Pipeline (all classical OpenCV, runs offline on CPU): align test → reference with ORB features + RANSAC homography (fallback: ECC affine, fallback: plain resize since the camera is fixed). For every named part, crop a padded patch from the reference and search for it in a slightly larger window of the aligned test image… Similarity = normalized cross-correlation on grayscale AND on edge maps (NCC is invariant to brightness/contrast changes), plus a colour-shift check.

## Chat excerpt #3: my correction
> **me:** upload it create rep all thing do it . but dont make dummy . remove fake data make according to pdf file . complete make it good ui all
>
> **AI (summary of its reply):** removed `samples/` and `tools/make_samples.py`; the evaluator now takes a folder of real labelled photos. Added box move/resize, a results summary bar, CSV export and a first-run "how it works" panel.
