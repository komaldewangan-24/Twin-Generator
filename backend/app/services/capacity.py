"""Deterministic seating-capacity estimator (own module, viva-friendly).

Rules (documented in report):
  - each chair              → 1 seat, but when tables exist, chairs are capped
                              at the seats the tables can serve:
                              tables × 4 + counters × 2 (chairs with no table are
                              usually misdetections or stacked spares)
  - each couch              → 3 seats, each bench → 2 seats (these are not tied
                              to a dining table, so they are never capped)
"""

SEATS_PER_COUCH = 3
SEATS_PER_BENCH = 2
SEATS_PER_DINING_TABLE = 4
SEATS_PER_COUNTER = 2


def _count_by_class(detections: list[dict], *names: str) -> int:
    total = 0
    for d in detections or []:
        if d.get("class") in names:
            total += d.get("count", 0)
    return total


def compute_capacity(detections: list[dict]) -> dict:
    chairs = _count_by_class(detections, "chair")
    couches = _count_by_class(detections, "couch")
    benches = _count_by_class(detections, "bench")
    tables = _count_by_class(detections, "dining table")
    counters = _count_by_class(detections, "counter")  # not in COCO yet; a sink is not seating
    beds = _count_by_class(detections, "bed")

    surface_cap = (tables * SEATS_PER_DINING_TABLE) + (counters * SEATS_PER_COUNTER)
    chair_seats = min(chairs, surface_cap) if (tables or counters) else chairs
    capacity = chair_seats + (couches * SEATS_PER_COUCH) + (benches * SEATS_PER_BENCH)

    return {
        "total": capacity,
        "breakdown": {
            "chairs": chairs,
            "couch_seats": couches * SEATS_PER_COUCH,
            "bench_seats": benches * SEATS_PER_BENCH,
            "dining_tables": tables,
            "counters": counters,
        },
        "rule_applied": "chairs capped by table seats, plus couch and bench seats" if (tables or counters) else "all chairs, plus couch and bench seats",
        "beds_not_counted": beds,
    }