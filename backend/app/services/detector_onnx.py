"""YOLOv8 object detection via ONNX Runtime (CPU).

Falls back on this when the torch/ultralytics wheel is unavailable or broken
on the target machine. Same class semantics as ultralytics YOLOv8.
"""

import cv2
import numpy as np

INPUT_SIZE = 640


def _letterbox(img: np.ndarray, new_shape=INPUT_SIZE):
    h, w = img.shape[:2]
    scale = min(new_shape / h, new_shape / w)
    nh, nw = int(round(h * scale)), int(round(w * scale))
    resized = cv2.resize(img, (nw, nh))
    canvas = np.full((new_shape, new_shape, 3), 114, dtype=np.uint8)
    pad_x = (new_shape - nw) // 2
    pad_y = (new_shape - nh) // 2
    canvas[pad_y:pad_y + nh, pad_x:pad_x + nw] = resized
    return canvas, scale, pad_x, pad_y


class ONNXDetector:
    def __init__(self, model_path: str):
        import onnxruntime as ort

        self.sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.input_name = self.sess.get_inputs()[0].name
        self.output_shape = self.sess.get_outputs()[0].shape  # (1, 84, 8400)

    def predict(self, image_path: str, conf: float = 0.35, classes: set[int] | None = None) -> list[dict]:
        img = cv2.imread(image_path)
        if img is None:
            return []

        lettered, scale, pad_x, pad_y = _letterbox(img)
        blob = lettered.astype("float32") / 255.0
        blob = np.transpose(blob, (2, 0, 1))[None]  # 1x3x640x640

        out = self.sess.run(None, {self.input_name: blob})[0][0]  # 84x8400
        out = out.T  # 8400x84
        preds = out[:, 4:]                       # 8400x80 class scores
        coords = out[:, :4]                      # cx, cy, w, h in letterbox pixels

        cls_ids = np.where(np.any(preds >= conf, axis=1))[0]
        dets = []
        for i in cls_ids:
            scores = preds[i]
            c = int(scores.argmax())
            score = float(scores[c])
            if score < conf or (classes is not None and c not in classes):
                continue
            cx, cy, w, h = coords[i]
            x1 = (cx - w / 2 - pad_x) / scale
            y1 = (cy - h / 2 - pad_y) / scale
            x2 = (cx + w / 2 - pad_x) / scale
            y2 = (cy + h / 2 - pad_y) / scale
            dets.append({"cls": c, "box": (float(x1), float(y1), float(x2), float(y2)), "conf": score})

        dets = self._nms(dets)
        return dets

    @staticmethod
    def _nms(dets: list[dict], iou_thresh: float = 0.45) -> list[dict]:
        if not dets:
            return []
        boxes = np.array([d["box"] for d in dets], dtype=np.float32)
        scores = np.array([d["conf"] for d in dets])
        keep = cv2.dnn.NMSBoxes(
            [(b[0], b[1], b[2] - b[0], b[3] - b[1]) for b in boxes],
            scores,
            score_threshold=0.0,
            nms_threshold=iou_thresh,
        )
        keep = np.asarray(keep).flatten() if len(keep) else []
        return [dets[i] for i in keep]