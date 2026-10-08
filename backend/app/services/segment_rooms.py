"""Room segmentation via DBSCAN clustering of object floor positions.

Objects that lie close together on the floor plane are treated as belonging to
the same room zone. Points labeled -1 (noise) are corridors/unassigned space.
"""

from sklearn.cluster import DBSCAN

DEFAULT_EPS = 0.12
DEFAULT_MIN_SAMPLES = 2


def segment_rooms(objects_xy: list[tuple[float, float]], eps: float = DEFAULT_EPS, min_samples: int = DEFAULT_MIN_SAMPLES) -> dict:
    """Cluster (x, z) floor positions into rooms.

    Returns:
    {
      "rooms":   [{"label": 0, "objects": n, "bounds": [min_x, min_z, max_x, max_z]}],
      "noise":   [positions unassigned to any room],
      "count":   number of rooms
    }
    """
    n = len(objects_xy)
    if n == 0:
        return {"rooms": [], "noise": [], "count": 0}

    if n < min_samples:
        return {
            "rooms": [{
                "label": 0,
                "objects": n,
                "bounds": [_min(objects_xy, 0), _min(objects_xy, 1), _max(objects_xy, 0), _max(objects_xy, 1)],
            }],
            "noise": [],
            "count": 1,
        }

    labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(objects_xy)

    # Cast to plain ints: sklearn returns numpy.int64 which is not JSON
    # serializable by FastAPI's encoder (causes a 500 on /analytics).
    labels = [int(l) for l in labels]

    unique = sorted(l for l in set(labels) if l >= 0)
    rooms = []
    noise = []
    for label in unique:
        pts = [p for p, l in zip(objects_xy, labels) if l == label]
        rooms.append({
            "label": label,
            "objects": len(pts),
            "bounds": [_min(pts, 0), _min(pts, 1), _max(pts, 0), _max(pts, 1)],
        })
    noise = [p for p, l in zip(objects_xy, labels) if l == -1]

    return {"rooms": rooms, "noise": noise, "count": len(rooms), "labels": labels}


def _min(pts, axis):
    return round(min(p[axis] for p in pts), 4)


def _max(pts, axis):
    return round(max(p[axis] for p in pts), 4)