"""Sample local videos and report fire/smoke detections from best.pt."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "jetson_agent" / "best.pt"
VIDEOS = sorted((ROOT / "video").glob("*.mp4"))


def sample_video(path: Path):
    capture = cv2.VideoCapture(str(path))
    fps = capture.get(cv2.CAP_PROP_FPS) or 1
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(int(fps), 1)
    frames, positions = [], []
    index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if index % step == 0:
            frames.append(frame)
            positions.append(round(index / fps, 2))
        index += 1
    capture.release()
    return frames, positions, fps, frame_count


def main():
    model = YOLO(str(MODEL))
    report = {"model_classes": model.names, "videos": []}
    for path in VIDEOS:
        frames, positions, fps, frame_count = sample_video(path)
        counts = {"fire": 0, "smoke": 0}
        maxima = {"fire": 0.0, "smoke": 0.0}
        hits = []
        results = model.predict(frames, conf=0.25, imgsz=640, verbose=False)
        for seconds, prediction in zip(positions, results):
            frame_hits = []
            for box in prediction.boxes:
                name = str(model.names[int(box.cls[0])]).lower()
                confidence = float(box.conf[0])
                if name in counts:
                    counts[name] += 1
                    maxima[name] = max(maxima[name], confidence)
                    frame_hits.append({"class": name, "confidence": round(confidence, 4)})
            if frame_hits:
                hits.append({"seconds": seconds, "detections": frame_hits})
        report["videos"].append({
            "file": path.name,
            "fps": round(fps, 2),
            "frames": frame_count,
            "sampled_frames": len(frames),
            "box_counts": counts,
            "max_confidence": {key: round(value, 4) for key, value in maxima.items()},
            "hits": hits,
        })
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

