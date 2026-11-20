"""Score the detector on a folder of real labelled photos.

Folder layout:
  reference.jpg|png          photo of the good board
  ground_truth.json          {"parts": [{name,x,y,w,h} 0..1], "tests": {"photo1.jpg": ["C3"], "photo2.jpg": []}}
  photo1.jpg, photo2.jpg ... photos to check
Tip: "parts" can be copied from data/parts.json after naming the parts in the app.

Usage: python tools/evaluate.py my_board/ [--threshold 0.55]
Prints per-photo verdicts and part-level precision / recall, plus the score margin
between the lowest 'present' score and highest 'missing' score (bigger = more robust).
"""
import argparse
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import inspector  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--threshold", type=float, default=inspector.DEFAULT_THRESHOLD)
    a = ap.parse_args()
    d = Path(a.folder)
    gt = json.loads((d / "ground_truth.json").read_text())
    ref = next(cv2.imread(str(f)) for f in sorted(d.glob("reference.*")))
    tp = fp = fn = 0
    photo_ok = 0
    present_scores, missing_scores = [], []
    for name, miss in gt["tests"].items():
        r = inspector.inspect(ref, cv2.imread(str(d / name)), gt["parts"], a.threshold)
        pred = set(r["missing"])
        truth = set(miss)
        tp += len(pred & truth); fp += len(pred - truth); fn += len(truth - pred)
        photo_ok += pred == truth
        for p in r["parts"]:
            (missing_scores if p["name"] in truth else present_scores).append(p["score"])
        flag = "PASS" if pred == truth else "FAIL"
        print(f"{flag} {name:28s} truth={sorted(truth)} pred={sorted(pred)} align={r['alignment']['method']}")
    n = len(gt["tests"])
    print(f"\nphotos correct: {photo_ok}/{n}")
    print(f"parts  TP={tp} FP={fp} FN={fn}  precision={tp / max(1, tp + fp):.2f} recall={tp / max(1, tp + fn):.2f}")
    if present_scores and missing_scores:
        print(f"min present score={min(present_scores):.3f}  max missing score={max(missing_scores):.3f}")


if __name__ == "__main__":
    main()
