"""Export an open-vocabulary detector (YOLO-World) to ONNX so the app can find
doors, windows, lights and other things the COCO model does not know.

Run this ONCE in a throwaway environment; the app itself only needs onnxruntime.

    python -m venv /tmp/ov && source /tmp/ov/bin/activate
    pip install ultralytics onnx onnxslim "git+https://github.com/ultralytics/CLIP.git"
    python backend/scripts/export_open_vocab.py

Downloads (first run): yolov8s-worldv2.pt (~25 MB) and the CLIP text encoder (~340 MB).
Licence: ultralytics / YOLO-World is AGPL-3.0 / GPL-3.0. Fine for an open-source
academic project; check before shipping it in a closed product.

Writes backend/models/open_vocab.onnx and backend/models/open_vocab.json.
"""

import json
import shutil
from pathlib import Path

from ultralytics import YOLOWorld

# text prompt -> class name used by the app (several prompts can map to one name)
PROMPTS = {
    "door": "door",
    "window": "window",
    "ceiling light": "light",
    "lamp": "light",
    "kitchen counter": "counter",
    "cabinet": "cabinet",
    "bookshelf": "shelf",
    "framed picture on wall": "picture",
    "curtain": "curtain",
}
CONF = 0.25
MODELS = Path(__file__).resolve().parent.parent / "models"


def main() -> None:
    MODELS.mkdir(exist_ok=True)
    model = YOLOWorld("yolov8s-worldv2.pt")
    model.set_classes(list(PROMPTS))
    onnx = Path(model.export(format="onnx", imgsz=640, simplify=True))
    shutil.copy(onnx, MODELS / "open_vocab.onnx")
    (MODELS / "open_vocab.json").write_text(json.dumps({"names": list(PROMPTS.values()), "conf": CONF}, indent=2))
    print("Wrote", MODELS / "open_vocab.onnx")


if __name__ == "__main__":
    main()
