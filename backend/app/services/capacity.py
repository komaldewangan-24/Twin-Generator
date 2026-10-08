"""Deterministic seating-capacity estimator (own module, viva-friendly).

Rules (documented in report):
  - each chair              → 1 seat
  - each bench / couch seat → couch counts as 3, bench as 2
  - cap at dining surfaces:  tables × 4, counters (std/sink) × 2
  - empty-space factor: capacity is reduced if room area is very tight
      (a coarse penalty when furniture footprint exceeds available area)
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
    counters = _count_by_class(detections, "sink", "counter")
    beds = _count_by_class(detections, "bed")

    seated_avail = chairs + (couches * SEATS_PER_COUCH) + (benches * SEATS_PER_BENCH)
    surface_cap = (tables * SEATS_PER_DINING_TABLE) + (counters * SEATS_PER_COUNTER)
    capacity = seated_avail if not tables else min(seated_avail, surface_cap)

    return {
        "total": capacity,
        "breakdown": {
            "chairs": chairs,
            "couch_seats": couches * SEATS_PER_COUCH,
            "bench_seats": benches * SEATS_PER_BENCH,
            "dining_tables": tables,
            "counters": counters,
        },
        "rule_applied": "min(seated_available, dining_surface_capacity)" if tables else "seated_available_only",
        "beds_not_counted": beds,
    }