import cv2
from pathlib import Path

from app.core.config import settings

# Furniture-relevant COCO classes (YOLOv8 pretrained)
FURNITURE_CLASSES = {
    56: "chair",
    57: "couch",
    58: "potted plant",
    59: "bed",
    60: "dining table",
    61: "toilet",
    62: "tv",
    71: "sink",
    72: "refrigerator",
    13: "bench",
    68: "microwave",
    69: "oven",
    74: "clock",
}

CONF_THRESHOLD = 0.35
DEDUP_DISTANCE = 0.10


def _load_backend():
    """Prefer torch/ultralytics; fall back to ONNX Runtime when torch is broken."""
    try:
        from ultralytics import YOLO

        model = YOLO(settings.YOLO_MODEL_PATH)
        return _TorchBackend(model)
    except Exception:  # noqa: BLE001 - torch DLL issues etc
        onnx_path = Path(settings.YOLO_ONNX_PATH)
        if onnx_path.exists():
            from app.services.detector_onnx import ONNXDetector

            try:
                return _OnnxBackend(ONNXDetector(str(onnx_path)))
            except Exception as onnx_error:  # noqa: BLE001
                raise RuntimeError(f"torch and onnx backends both failed ({onnx_error.__class__.__name__})") from onnx_error
        kind = "torch unavailable + onnx model missing"
        raise RuntimeError(
            f"Detection backend unavailable: {kind}. "
            "Run: venv\\Scripts\\pip install onnxruntime && download yolov8n.onnx to models/"
        )


class _TorchBackend:
    def __init__(self, model):
        self.model = model

    def name(self):
        return "ultralytics-torch"

    def predict(self, image_path: str):
        result = self.model.predict(image_path, conf=CONF_THRESHOLD, verbose=False)[0]
        dets = []
        for box in result.boxes:
            cls = int(box.cls[0])
            if cls not in FURNITURE_CLASSES:
                continue
            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
            dets.append({"cls": cls, "box": (x1, y1, x2, y2), "conf": float(box.conf[0])})
        return dets


class _OnnxBackend:
    def __init__(self, detector):
        self.detector = detector

    def name(self):
        return "onnxruntime"

    def predict(self, image_path: str):
        return self.detector.predict(image_path, conf=CONF_THRESHOLD, classes=set(FURNITURE_CLASSES))


def run_detection(frames_dir: str) -> dict:
    """Run detection over all frames, dedup across frames, aggregate counts."""
    backend = _load_backend()
    frames = sorted(Path(frames_dir).glob("*.jpg"))
    if not frames:
        raise RuntimeError("no frames to run detection on")

    # Normalization reference = largest frame dimensions
    max_w, max_h = 1280, 720
    for path in frames:
        img = cv2.imread(str(path))
        if img is not None:
            max_w = max(max_w, img.shape[1])
            max_h = max(max_h, img.shape[0])

    seen: list[dict] = []
    processed = 0
    for path in frames:
        for det in backend.predict(str(path)):
            cls_name = FURNITURE_CLASSES[det["cls"]]
            x1, y1, x2, y2 = det["box"]
            cx = ((x1 + x2) / 2) / max_w        # horizontal center → x
            base_y = y2 / max_h                 # bottom edge → floor-plane z proxy

            match = None
            for obj in seen:
                if obj["class"] == cls_name and ((obj["x"] - cx) ** 2 + (obj["z"] - base_y) ** 2) ** 0.5 < DEDUP_DISTANCE:
                    match = obj
                    break
            if match:
                if det["conf"] > match["confidence"]:
                    match["x"], match["z"], match["confidence"] = cx, base_y, det["conf"]
            else:
                seen.append({"class": cls_name, "x": cx, "z": base_y, "confidence": det["conf"]})
        processed += 1

    by_class: dict[str, dict] = {}
    for obj in seen:
        entry = by_class.setdefault(obj["class"], {"class": obj["class"], "count": 0, "positions": []})
        entry["count"] += 1
        entry["positions"].append({
            "x": round(obj["x"], 4),
            "z": round(obj["z"], 4),
            "confidence": round(obj["confidence"], 3),
        })
    detections = [by_class[c] for c in sorted(by_class)]

    return {
        "calibration": None,
        "detections": detections,
        "meta": {"frames_processed": processed, "total_frames": len(frames), "backend": backend.name()},
    }