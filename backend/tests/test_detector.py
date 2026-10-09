"""Per-class confidence in the detector: doors and windows score far lower than furniture."""

import pytest

from app.services import detector


class _Stub:
    """Stands in for the ONNX network: returns the same three boxes for every image."""

    def __init__(self, path):
        self.asked = None

    def predict(self, image_path, conf, classes):
        self.asked = conf
        boxes = [
            {"cls": 0, "box": [0, 0, 10, 10], "conf": 0.06},    # a plain door
            {"cls": 1, "box": [0, 0, 10, 10], "conf": 0.09},    # window, above its own threshold of 0.07
            {"cls": 2, "box": [0, 0, 10, 10], "conf": 0.18},    # a cabinet that is not sure of itself
            {"cls": 2, "box": [0, 0, 10, 10], "conf": 0.55},
        ]
        return [b for b in boxes if b["conf"] >= conf and b["cls"] in classes]


@pytest.fixture()
def model(monkeypatch):
    monkeypatch.setattr("app.services.detector_onnx.ONNXDetector", _Stub)
    return detector._Model("test", "unused.onnx", {0: "door", 1: "window", 2: "cabinet"}, 0.25, {"door": 0.05, "window": 0.07})


def test_each_class_uses_its_own_threshold(model):
    found = {(d["cls"], d["conf"]) for d in model.predict("frame.jpg")}
    assert found == {("door", 0.06), ("window", 0.09), ("cabinet", 0.55)}


def test_the_network_is_asked_for_the_lowest_threshold_any_class_needs(model):
    model.predict("frame.jpg")
    assert model.detector.asked == 0.05


def test_without_per_class_settings_one_threshold_applies(monkeypatch):
    monkeypatch.setattr("app.services.detector_onnx.ONNXDetector", _Stub)
    plain = detector._Model("plain", "unused.onnx", {0: "door", 1: "window", 2: "cabinet"}, 0.25)
    assert [d["cls"] for d in plain.predict("frame.jpg")] == ["cabinet"]

