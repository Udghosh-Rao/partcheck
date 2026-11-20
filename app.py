"""PartCheck - offline missing-component inspector. Run: python app.py  -> http://127.0.0.1:8765"""
from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
from flask import Flask, jsonify, request, send_file, send_from_directory

import inspector

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
REF = DATA / "reference.png"
PARTS = DATA / "parts.json"
SETTINGS = DATA / "settings.json"

app = Flask(__name__, static_folder=str(ROOT / "static"), static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024
_ref_cache: dict = {}


def load_ref():
    if not REF.exists():
        return None
    m = REF.stat().st_mtime
    if _ref_cache.get("m") != m:
        _ref_cache.update(m=m, img=cv2.imread(str(REF)))
    return _ref_cache["img"]


def load_json(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/project")
def project():
    ref = load_ref()
    return jsonify({
        "has_reference": ref is not None,
        "reference_url": f"/api/reference.png?v={int(REF.stat().st_mtime)}" if ref is not None else None,
        "reference_size": [int(ref.shape[1]), int(ref.shape[0])] if ref is not None else None,
        "parts": load_json(PARTS, []),
        "threshold": load_json(SETTINGS, {}).get("threshold", inspector.DEFAULT_THRESHOLD),
    })


@app.get("/api/reference.png")
def reference_png():
    return send_file(REF, mimetype="image/png", max_age=0)


@app.post("/api/reference")
def set_reference():
    f = request.files.get("file")
    if not f:
        return jsonify(error="No file uploaded"), 400
    try:
        img = inspector.decode_image(f.read())
    except ValueError as e:
        return jsonify(error=str(e)), 400
    cv2.imwrite(str(REF), img)
    PARTS.write_text("[]")  # new board -> parts must be marked again
    return project()


@app.put("/api/parts")
def save_parts():
    parts = request.get_json(force=True)
    clean = []
    for p in parts:
        name = str(p.get("name", "")).strip()[:40]
        if not name:
            continue
        clean.append({"name": name, **{k: float(min(1, max(0, p[k]))) for k in ("x", "y", "w", "h")}})
    PARTS.write_text(json.dumps(clean, indent=1))
    return jsonify(parts=clean)


@app.put("/api/settings")
def save_settings():
    t = float(request.get_json(force=True).get("threshold", inspector.DEFAULT_THRESHOLD))
    SETTINGS.write_text(json.dumps({"threshold": min(0.95, max(0.05, t))}))
    return jsonify(ok=True)


@app.post("/api/inspect")
def inspect_route():
    ref = load_ref()
    parts = load_json(PARTS, [])
    if ref is None:
        return jsonify(error="Upload a reference photo first"), 400
    if not parts:
        return jsonify(error="Mark at least one part on the reference first"), 400
    threshold = load_json(SETTINGS, {}).get("threshold", inspector.DEFAULT_THRESHOLD)
    out = []
    for f in request.files.getlist("files"):
        t0 = time.time()
        try:
            res = inspector.inspect(ref, inspector.decode_image(f.read()), parts, threshold)
        except Exception as e:  # keep going for the other photos
            res = {"error": str(e)}
        res["filename"] = f.filename
        res["ms"] = int((time.time() - t0) * 1000)
        out.append(res)
    return jsonify(results=out)


if __name__ == "__main__":
    print("\n  PartCheck running -> open http://127.0.0.1:8765\n")
    app.run(host="127.0.0.1", port=8765, debug=False)
