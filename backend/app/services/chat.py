"""AI assistant: answers questions about the digital twin.

Primary path: Gemini API (free tier) grounded on objects.json + analytics so
it cannot hallucinate counts.
Fallback path (no API key / offline demo): deterministic rule-based answers
using the exact same JSON — everything still works without internet.
"""

import json

from app.core.config import settings
from app.services import analytics as analytics_service
from app.services.capacity import compute_capacity

RULE_BASED_CLASS_SYNONYMS = {
    "chair": "chair",
    "chairs": "chair",
    "seat": "chair",
    "seats": "chair",
    "couch": "couch",
    "sofa": "couch",
    "table": "dining table",
    "tables": "dining table",
    "bed": "bed",
    "beds": "bed",
    "plant": "potted plant",
    "plants": "potted plant",
    "tv": "tv",
    "television": "tv",
    "sink": "sink",
    "fridge": "refrigerator",
    "refrigerator": "refrigerator",
    "bench": "bench",
}


def _summarize(project, analytics: dict) -> str:
    data = json.loads(project.detections_json) if project.detections_json else {"detections": []}
    lines = []
    for d in data.get("detections", []):
        lines.append(f"- {d['class']}: {d['count']}")
    return "\n".join(lines) or "- no objects detected"


def _rule_based_answer(question: str, project, analytics: dict) -> str:
    data = json.loads(project.detections_json) if project.detections_json else {"detections": []}
    detections = data.get("detections", [])
    q = question.lower()

    # seating capacity
    if any(word in q for word in ("seating", "capacity", "people", "sit", "occupy")):
        cap = analytics["seating_capacity"]
        b = cap["breakdown"]
        return (
            f"Estimated seating capacity: {cap['total']} seats. "
            f"Breakdown: {b['chairs']} chairs, {b['couch_seats']} couch seats, "
            f"{b['bench_seats']} bench seats, served by {b['dining_tables']} dining "
            f"tables ({cap['rule_applied']})."
        )

    # room / space questions
    if any(word in q for word in ("room", "space", "spacious", "most free")):
        rooms = analytics["rooms"]
        if rooms["count"] == 0:
            return "No distinct room zones were detected yet."
        largest = max(rooms["details"], key=lambda r: r["objects"]) if rooms["details"] else None
        return (
            f"Detected {rooms['count']} room zone(s). The room with the most "
            f"furniture (proxy for highest usage) is room R{largest['label']} "
            f"with {largest['objects']} objects." if largest else
            f"Detected {rooms['count']} room zone(s)."
        )

    # object-count questions
    found = False
    answers = []
    for word, cls in RULE_BASED_CLASS_SYNONYMS.items():
        if word in q:
            count = next((d["count"] for d in detections if d["class"] == cls), 0)
            answers.append(f"{cls}: {count}")
            found = True
    if found:
        return "Detected: " + ", ".join(answers) + ". (Counts from YOLO aggregated over the whole scan.)"

    if any(word in q for word in ("area", "size", "square", "dimension")):
        a = analytics["area"]
        if a["calibration"] and a["calibration"]["area_m2"]:
            return f"Estimated total area covering the scanned furniture layout: ~{a['calibration']['area_m2']} m²."
        if a["unit_area"]:
            return f"Relative area occupied by furniture layout: {a['unit_area']} scene units² (provide a known room width to calibrate to meters)."
        return "No area estimate available yet."

    return (
        "I can answer about: object counts (chairs, tables, couches...), seating "
        "capacity, room zones, and area estimates for this scan."
    )


def _gemini_answer(question: str, project, analytics: dict) -> str:
    import google.generativeai as genai

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")

    context = (
        f"Digital twin scan summary (from computer vision, DO NOT invent numbers):\n"
        f"Object detections:\n{_summarize(project, analytics)}\n"
        f"Analytics: {json.dumps(analytics, default=str)}\n\n"
        f"Answer the user's question using ONLY this data. If unknown, say so."
    )
    response = model.generate_content(f"{context}\nQuestion: {question}")
    return response.text.strip()


def answer(question: str, project, analytics: dict) -> str:
    attempt = None
    if settings.GEMINI_API_KEY:
        try:
            return _gemini_answer(question, project, analytics)
        except Exception as exc:  # noqa: BLE001 - fall back on any API hiccup
            attempt = f"(Gemini unavailable: {exc})"
    fallback = _rule_based_answer(question, project, analytics)
    return fallback if attempt is None else f"{attempt}\n{fallback}"