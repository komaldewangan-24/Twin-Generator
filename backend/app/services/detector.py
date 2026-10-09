"""Object detection over the extracted frames, plus counting and placement.

Two modes:
  * spatial (default when SfM worked): every sighting is placed on the floor in
    real 3D, sightings from different frames are merged, and positions are in
    metres. Counts are numbers of distinct objects seen in at least 2 frames.
  * view (fallback when no camera poses are available): sightings are merged by
    their position in the camera view. Counts and positions are rough.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import cv2

from app.core.config import settings
from app.services import spatial

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

CONF_THRESHOLD = 0.30   # low on purpose: the 2-frame vote below removes one-off false alarms
VIEW_DEDUP_DISTANCE = 0.10

Progress = Callable[[str, float, str], None]


class _Model:
    def __init__(self, name: str, onnx_path: Path, class_map: dict[int, str], conf: float):
        from app.services.detector_onnx import ONNXDetector

        self.name = name
        self.detector = ONNXDetector(str(onnx_path))
        self.class_map = class_map
        self.conf = conf

    def predict(self, image_path: str) -> list[dict]:
        out = []
        for d in self.detector.predict(image_path, conf=self.conf, classes=set(self.class_map)):
            out.append({"cls": self.class_map[d["cls"]], "box": d["box"], "conf": d["conf"]})
        return out


class Backend:
    """One or more ONNX detectors run on every frame and pooled."""

    def __init__(self, models: list[_Model]):
        self.models = models

    def name(self) -> str:
        return "onnxruntime: " + " + ".join(m.name for m in self.models)

    def predict(self, image_path: str) -> list[dict]:
        dets: list[dict] = []
        for m in self.models:
            dets.extend(m.predict(image_path))
        return dets


def _load_backend() -> Backend:
    models: list[_Model] = []
    coco = Path(settings.YOLO_ONNX_PATH)
    if not coco.exists():
        raise RuntimeError(
            "The object detector model is missing (backend/models/yolov8s.onnx or yolov8n.onnx). See the README section 'Model weights'."
        )
    models.append(_Model(coco.stem, coco, FURNITURE_CLASSES, CONF_THRESHOLD))

    # Optional open-vocabulary model (doors, windows, lights...): an ONNX export
    # plus open_vocab.json = {"names": [...], "conf": 0.25}, produced by
    # scripts/export_open_vocab.py.
    extra = coco.parent / "open_vocab.onnx"
    cfg_file = coco.parent / "open_vocab.json"
    if extra.exists() and cfg_file.exists():
        cfg = json.loads(cfg_file.read_text())
        models.append(_Model("yolo-world", extra, {i: n for i, n in enumerate(cfg["names"])}, float(cfg.get("conf", 0.25))))
    return Backend(models)


def run_detection(frames_dir: str, recon=None, scene: spatial.Scene | None = None, progress: Progress | None = None) -> dict:
    """Detect objects in the frames and aggregate them.

    `recon` and `scene` (from spatial.build_scene) switch on 3D placement.
    """
    backend = _load_backend()
    frames = sorted(Path(frames_dir).glob("*.jpg"))
    if not frames:
        raise RuntimeError("no frames to run detection on")

    spatial_mode = recon is not None and scene is not None
    by_name = {im.name: im for im in recon.images.values() if im.has_pose} if spatial_mode else {}
    if spatial_mode:
        frames = [f for f in frames if f.name in by_name]

    observations: list[dict] = []   # spatial mode
    seen: list[dict] = []           # view mode
    processed = 0

    for i, path in enumerate(frames):
        img = cv2.imread(str(path))
        if img is None:
            continue
        h, w = img.shape[:2]
        dets = backend.predict(str(path))

        if spatial_mode:
            image = by_name[path.name]
            camera = recon.cameras[image.camera_id]
            for d in dets:
                spot = spatial.locate(image, camera, recon, scene, d["cls"], d["box"])
                if spot:
                    observations.append({"cls": d["cls"], "u": spot[0], "v": spot[1], "conf": d["conf"], "frame": path.name, "world": spot[3].tolist()})
        else:
            for d in dets:
                x1, _, x2, y2 = d["box"]
                _merge_in_view(seen, d["cls"], ((x1 + x2) / 2) / w, y2 / h, d["conf"])
        processed += 1
        if progress and i % 5 == 0:
            progress("detect", (i + 1) / len(frames), f"Looking for objects ({i + 1} of {len(frames)} frames)")

    by_class: dict[str, dict] = {}
    if spatial_mode:
        for o in spatial.merge_observations(observations, scene):
            entry = by_class.setdefault(o["class"], {"class": o["class"], "count": 0, "positions": []})
            entry["count"] += 1
            entry["positions"].append({
                "x": round(o["x"], 2), "z": round(o["z"], 2),
                "confidence": round(o["confidence"], 3), "votes": o["votes"], "world": o["world"],
            })
    else:
        for o in seen:
            entry = by_class.setdefault(o["class"], {"class": o["class"], "count": 0, "positions": []})
            entry["count"] += 1
            entry["positions"].append({"x": round(o["x"], 4), "z": round(o["z"], 4), "confidence": round(o["confidence"], 3)})

    meta = {
        "frames_processed": processed,
        "total_frames": len(frames),
        "backend": backend.name(),
        "unit": "m" if spatial_mode else "view",
    }
    calibration = None
    if spatial_mode:
        meta["reconstruction"] = scene.to_json()
        calibration = {
            "method": scene.scale_method,
            "meters_per_unit": round(scene.meters_per_unit, 5),
            "assumed_camera_height_m": spatial.ASSUMED_CAMERA_HEIGHT_M,
        }
    return {"calibration": calibration, "detections": [by_class[c] for c in sorted(by_class)], "meta": meta}


def empty_result(scene: spatial.Scene | None, error: str) -> dict:
    """A valid result with no objects, for when detection could not run."""
    meta = {"frames_processed": 0, "total_frames": 0, "backend": "none", "unit": "m" if scene else "view", "detector_error": error}
    calibration = None
    if scene:
        meta["reconstruction"] = scene.to_json()
        calibration = {
            "method": scene.scale_method,
            "meters_per_unit": round(scene.meters_per_unit, 5),
            "assumed_camera_height_m": spatial.ASSUMED_CAMERA_HEIGHT_M,
        }
    return {"calibration": calibration, "detections": [], "meta": meta}


def _merge_in_view(seen: list[dict], cls: str, cx: float, base_y: float, conf: float) -> None:
    for obj in seen:
        if obj["class"] == cls and ((obj["x"] - cx) ** 2 + (obj["z"] - base_y) ** 2) ** 0.5 < VIEW_DEDUP_DISTANCE:
            if conf > obj["confidence"]:
                obj["x"], obj["z"], obj["confidence"] = cx, base_y, conf
            return
    seen.append({"class": cls, "x": cx, "z": base_y, "confidence": conf})
