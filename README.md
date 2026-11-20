# PartCheck: Which Part Is Missing?

**Industry AI Take-home, Task B**, by Udghosh Rao

A factory camera photographs every circuit board. PartCheck tells you **which parts are missing** and **shows where they are**.
If nothing is missing, it shows a big green **OK**.

- Works **fully offline** on a laptop. No internet, no cloud, no AI APIs.
- **No training needed.** One photo of a good board is enough.
- Checks a photo in about **0.2 seconds**.

---

## 1. Quick start

You need **Python 3.9 or newer** ([python.org](https://www.python.org/downloads/)). On Windows, tick **"Add Python to PATH"** while installing.

### Step 1: Download the code
On this GitHub page click the green **Code** button, choose **Download ZIP**, and unzip it.
You get a folder called `partcheck-main`.

### Step 2: Install the requirements (only once)
Open a terminal **inside the `partcheck-main` folder** and run:

**macOS / Linux**
```bash
pip3 install -r requirements.txt
```

**Windows**
```bat
pip install -r requirements.txt
```

### Step 3: Run the app
**macOS / Linux**
```bash
python3 app.py
```

**Windows**
```bat
python app.py
```

When you see

```
PartCheck running -> open http://127.0.0.1:8765
```

open **http://127.0.0.1:8765** in your browser.
To stop the app, press **Ctrl + C** in the terminal.

### Even easier: double-click
- **Windows:** double-click **`run.bat`**
- **macOS:** double-click **`run.command`**. The first time, right-click it and choose **Open**.

These scripts install the requirements if they are missing, start the app and open the browser.

> **How to open a terminal in the folder:** on Windows, open the folder, click the address bar, type `cmd` and press Enter.
> On macOS, right-click the folder and choose **New Terminal at Folder**.
>
> The internet is needed only once, for the install. After that the app runs with Wi-Fi turned off.

---

## 2. How to use it

The app has 3 steps, shown as buttons at the top of the page.

### Step 1: Reference board
Drop in (or click to choose) a photo of a **good, complete** board. Every later photo is compared against it.

### Step 2: Name the parts
- **Click and drag** on the photo to draw a box around a part.
- Type a name (for example `C3`, `U1 chip`, `USB port`) and press **Enter**.
- **Move** a box by dragging it. **Resize** it by dragging its bottom-right corner.
- **Rename** or **delete** a part in the list on the right.
- **Ctrl/⌘ + Z** undoes the last box.
- Everything saves automatically.

### Step 3: Inspect photos
Drop in one or more photos of the same board, taken from the same camera position. Each photo gets a card:

| You see | Meaning |
|---|---|
| Green **✔ OK** | All named parts are present |
| Red **✖ MISSING: C3, R1** | Those parts are missing. They blink in red on the photo |
| Small chips such as `R1 · 0.92` | How similar each part looks to the reference, from 0 to 1. Click a chip to highlight that part |

You also get:
- a **summary bar**: how many photos were checked, how many were OK, and how many have missing parts
- **⬇ Export CSV**: downloads a report of all results
- **⚙ Sensitivity**: the threshold used to decide "missing" (default 0.55). Raise it to be stricter, lower it if good parts get flagged. Press **↻ Re-run** after changing it.
- Click any photo to see it full screen.

The reference photo and part names stay saved in the `data/` folder, so they are still there after you restart the app.
To start over with a new board, use **Replace reference** in step 1.

---

## 3. How it works

```
 reference photo + named boxes          new photo
            │                               │
            └──────────────┬────────────────┘
                           ▼
        ① ALIGN the new photo onto the reference
           (find matching points and correct small shifts, rotation and zoom)
                           ▼
        ② FIX LIGHTING (match brightness and colour to the reference)
                           ▼
        ③ For EACH named box: does this area still look like the reference?
           • compare the shapes   (grayscale similarity)
           • compare the edges    (outline of the part)
           • compare the colour   (bare pad vs. component)
           → similarity score 0 … 1
                           ▼
        ④ score below 0.55 → MISSING, otherwise present
                           ▼
        ⑤ draw the missing boxes on the original photo → OK / MISSING
```

**In simple words:** the app lines up each new photo with the good photo, then looks inside every box you drew and asks
*"does this spot still look like it did on the good board?"* If the part is gone, the spot now shows bare board or solder pads,
so the similarity drops and the part is reported as missing.

**Technical terms:**
1. **Alignment:** ORB keypoints + RANSAC homography (OpenCV). If the board has too few features, it falls back to ECC alignment, and after that to a simple resize, because the camera is fixed.
2. **Lighting fix:** match the mean and standard deviation of each LAB colour channel.
3. **Per-part check:** template matching with normalised cross-correlation (NCC) on grayscale and on edge maps, inside a small search window that absorbs leftover misalignment, minus a penalty for colour change.
4. **Decision:** a single threshold that you can change in the UI.

Why this approach rather than deep learning (YOLO, anomaly detection)? The examiners bring a **new board** and name the parts **themselves**,
so there is no data to train on in advance. This method works from **one** good photo, runs on any laptop CPU, and every decision comes with a score you can explain.
Full comparison: [RESEARCH.md](RESEARCH.md). Diagram and trade-offs: [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 4. Tips for good results

- Take every photo from the **same camera position** as the reference. Small shifts and tilts are fine.
- Draw boxes **snugly around each part**, with a little board around it.
- Avoid strong glare or shadows over the parts.
- If a present part is wrongly flagged, lower the Sensitivity a bit. If a missing part is not caught, raise it.

---

## 5. Measuring accuracy (optional)

If you have labelled photos, the tool below reports precision and recall:

```
my_board/
  reference.jpg
  photo1.jpg
  photo2.jpg
  ground_truth.json
```

`ground_truth.json`:
```json
{
  "parts": [ { "name": "C3", "x": 0.41, "y": 0.22, "w": 0.05, "h": 0.04 } ],
  "tests": { "photo1.jpg": ["C3"], "photo2.jpg": [] }
}
```
Copy the `parts` list from `data/parts.json` after naming the parts in the app. Then run:
```bash
python tools/evaluate.py my_board/
```

---

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| `python3: command not found` / `pip3: command not found` | Install Python from python.org. On Windows, use `python` / `pip` |
| `pip` says "externally-managed-environment" (macOS Homebrew Python) | Run `pip3 install --user --break-system-packages -r requirements.txt` |
| `pip install` fails on opencv | Upgrade pip with `python -m pip install --upgrade pip`, then try again |
| `Address already in use` | Another program uses port 8765. Close it, or change `port=8765` at the bottom of `app.py` |
| Page doesn't open | Make sure the terminal still shows "PartCheck running", and use `http://127.0.0.1:8765` |
| Every part shows MISSING | The photo is probably of a different board or angle. Check that the reference and photos match |
| A good part shows MISSING | Lower the ⚙ Sensitivity (for example to 0.45) and press Re-run, or draw that box tighter |

---

## 7. Project files

| File / folder | What it does |
|---|---|
| `run.bat` / `run.command` | Double-click to install the requirements and start the app (Windows / macOS) |
| `app.py` | Local web server (Flask). Saves the reference and parts, and runs the inspection |
| `inspector.py` | The image-processing logic: alignment, lighting fix, per-part scoring |
| `static/` | The web page: `index.html`, `style.css`, `app.js` (no external libraries) |
| `tools/evaluate.py` | Optional accuracy report on labelled photos |
| `data/` | Created automatically. Holds your reference photo and part names |
| `docs/` | Architecture diagram made with Archify (`architecture.png`, interactive `architecture.html`) |
| `ARCHITECTURE.md` | Diagram and design trade-offs |
| `RESEARCH.md` | What I researched, what I compared, and what I picked and rejected |
| `AI_COLLAB.md` | How I worked with the AI assistant, and the key decisions |
| `chat_history/` | Full AI chat export (zip). Unzip it to read the conversation |

**Tech stack:** Python · OpenCV · NumPy · Flask · plain HTML/CSS/JavaScript.
