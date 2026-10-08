from app.services.calibrate import estimate_scale, observed_area_m2, compute_union_span
from app.services.capacity import compute_capacity
from app.services.segment_rooms import segment_rooms
import pytest


def test_estimate_scale_basic():
    assert estimate_scale(100, 4.0) == pytest.approx(0.04)


def test_estimate_scale_requires_positive_span():
    with pytest.raises(ValueError):
        estimate_scale(0, 4.0)


def test_observed_area_scales_quadratically():
    # 2x2 units² with scale 0.5 m/unit -> 1 m²
    assert observed_area_m2(4.0, 0.5) == pytest.approx(1.0)


def test_union_span():
    pts = [(0, 0), (3, 0), (0, 4)]
    max_dim, w, h = compute_union_span(pts)
    assert (max_dim, w, h) == (4.0, 3.0, 4.0)


def test_capacity_chairs_only():
    cap = compute_capacity([{"class": "chair", "count": 6}])
    assert cap["total"] == 6


def test_capacity_capped_by_tables():
    cap = compute_capacity([
        {"class": "chair", "count": 10},
        {"class": "dining table", "count": 2},
    ])
    assert cap["total"] == 8  # min(10, 2x4)


def test_capacity_couch_seats():
    cap = compute_capacity([{"class": "couch", "count": 2}])
    assert cap["total"] == 6


def test_segment_rooms_two_clusters():
    # 3 chairs clustered left, 2 clustered right -> 2 rooms
    pts = [(0.1, 0.1), (0.12, 0.12), (0.11, 0.13), (0.8, 0.8), (0.82, 0.81)]
    result = segment_rooms(pts, eps=0.1, min_samples=2)
    assert result["count"] == 2


def test_segment_rooms_empty():
    assert segment_rooms([])["count"] == 0


def test_segment_rooms_single_point():
    result = segment_rooms([(0.5, 0.5)])
    assert result["count"] == 1


def test_segment_rooms_is_json_serializable():
    """Regression: DBSCAN returns numpy.int64, which crashed FastAPI's JSON
    encoder and surfaced in the browser as a bogus CORS error on /analytics."""
    import json

    from fastapi.encoders import jsonable_encoder

    pts = [(0.1, 0.1), (0.12, 0.12), (0.11, 0.13), (0.8, 0.8), (0.82, 0.81)]
    result = segment_rooms(pts, eps=0.1, min_samples=2)

    json.dumps(jsonable_encoder(result))

    for label in result["labels"]:
        assert type(label) is int