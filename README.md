# PartCheck: which part is missing?

**Task chosen: B.**

PartCheck is an offline web app for a fixed-camera PCB line. You upload one photo of a good board,
draw a box around each part and name it, then upload photos of the same board.
For each photo it says **OK** (green) or **MISSING: R2, C3** (red) and outlines the missing parts on the photo.

- Runs 100% offline on a laptop: Python + OpenCV + Flask. No cloud APIs and no CDN; the UI is plain HTML/JS.
- No training and no dataset needed. One reference photo is enough.
- About 0.2 s per photo on a laptop CPU.
- Extras: move or resize boxes, a summary bar (photos checked / OK / with missing parts), **Export CSV** report, and click a score chip to highlight that part.

## Install

Requires Python 3.9+.

```bash
git clone <this-repo-url> partcheck
cd partcheck
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Open **http://127.0.0.1:8765** in a browser. After installation, no internet is needed.

## How to use it (3 steps in the top bar)

1. **Reference board**: drop a photo of a good, complete board.
2. **Name the parts**: click and drag a box around a part, type a name (`C3`, `USB port`, …) and press Enter.
   Drag a box to move it, or drag its corner to resize it. Rename or delete parts in the side list. Press <kbd>Ctrl/⌘+Z</kbd> to undo. Changes save automatically.
3. **Inspect photos**: drop one or more photos. Each photo gets a card:
   - green **✔ OK** when every part is present
   - red **✖ MISSING** with the part names, and blinking red outlines on the photo
   - a similarity score for every part (click the image to enlarge it)
   - an **⚙ Sensitivity** slider if a line needs stricter or looser checking

The reference and the parts are kept in `data/`, so they survive a restart.

## Measuring accuracy on your own photos

Put a reference photo, test photos and a `ground_truth.json` (which parts are really missing in each photo) in a folder, then run:

```bash
python tools/evaluate.py my_board/
```

It prints the verdict for each photo, part-level precision and recall, and the score gap between present and missing parts.
The format is described at the top of `tools/evaluate.py`. The `parts` list can be copied straight from `data/parts.json` after you name the parts in the app.

## Repo layout

| Path | What |
|---|---|
| `app.py` | Flask server: REST API + serves the UI |
| `inspector.py` | Computer vision: alignment and per-part comparison |
| `static/` | UI (`index.html`, `style.css`, `app.js`) with no external libraries |
| `tools/evaluate.py` | Accuracy report on a labelled folder of real photos |
| `docs/` | Archify architecture diagram (`architecture.html` / `.png`) |
| `README.md`, `AI_COLLAB.md`, `RESEARCH.md`, `ARCHITECTURE.md` | Required docs |
| `chat_history/` | Full AI chat history |
