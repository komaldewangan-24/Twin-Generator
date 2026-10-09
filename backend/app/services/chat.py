"""AI assistant: answers questions about the digital twin.

Primary path: Gemini API (free tier) grounded on objects.json + analytics so
it cannot hallucinate counts.
Fallback path (no API key / offline demo): deterministic rule-based answers
using the exact same JSON — everything still works without internet.
"""

import json
import logging
import re

from app.core.config import settings
from app.services import analytics as analytics_service
from app.services import llm
from app.services.capacity import compute_capacity

log = logging.getLogger("uvicorn.error")

RULE_BASED_CLASS_SYNONYMS = {
    "chair": "chair",
    "chairs": "chair",
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
    "door": "door",
    "doors": "door",
    "window": "window",
    "windows": "window",
    "light": "light",
    "lights": "light",
    "lamp": "light",
    "lamps": "light",
    "cabinet": "cabinet",
    "cabinets": "cabinet",
    "cupboard": "cabinet",
    "cupboards": "cabinet",
    "shelf": "shelf",
    "shelves": "shelf",
    "bookshelf": "shelf",
    "bookcase": "shelf",
    "counter": "counter",
    "curtain": "curtain",
    "curtains": "curtain",
    "picture": "picture",
    "pictures": "picture",
    "painting": "picture",
}


def _summarize(project, analytics: dict) -> str:
    data = json.loads(project.detections_json) if project.detections_json else {"detections": []}
    lines = []
    for d in data.get("detections", []):
        lines.append(f"- {d['class']}: {d['count']}")
    return "\n".join(lines) or "- no objects detected"


DISPLAY_NAMES = {"tv": "TV", "dining table": "table", "potted plant": "plant", "refrigerator": "fridge"}


def _has(q: str, *words: str) -> bool:
    """Whole-word match, so "bed" doesn't fire on "bedroom" or "sit" on "situation"."""
    return any(re.search(rf"\b{re.escape(w)}\b", q) for w in words)


def _placement_tips(counts: dict[str, int]) -> str:
    tips = []
    chairs, tables, couches = counts.get("chair", 0), counts.get("dining table", 0), counts.get("couch", 0)
    if tables and chairs < tables * 2:
        tips.append(f"{tables} table(s) but only {chairs} chair(s): add chairs, or consolidate tables.")
    if chairs > tables * 6 and tables:
        tips.append("Many chairs per table: spread chairs across more tables to avoid crowding.")
    if couches and counts.get("tv", 0):
        tips.append("Face the couch toward the TV with a clear walkway behind it.")
    if counts.get("potted plant", 0) == 0:
        tips.append("No plants detected: a few along the walls add warmth without taking floor space.")
    if not tips:
        tips.append("The layout looks balanced. Keep 90 cm clear around tables for walking.")
    return "Layout ideas from the detected counts: " + " ".join(tips)


def _area_answer(analytics: dict) -> str:
    layout = analytics.get("layout")
    if layout:
        approx = "about " if layout["source"] == "estimated" else ""
        return (
            f"The room is {approx}{layout['width_m']} × {layout['depth_m']} m ({approx}{layout['area_m2']} m²) "
            f"with a ceiling around {layout['ceiling_height_m']} m."
            + (" Sizes are estimated from camera height; enter a tape measurement on the Analytics tab to correct them." if layout["source"] == "estimated" else "")
        )
    a = analytics["area"]
    if a["calibration"] and a["calibration"]["area_m2"]:
        return f"Estimated area covered by the furniture layout: about {a['calibration']['area_m2']} m²."
    if a["unit_area"]:
        return (
            f"The layout covers {a['unit_area']} scene units². "
            "Enter a known room width on the Analytics tab to convert this to square metres."
        )
    return "No area estimate yet."


def _rule_based_answer(question: str, project, analytics: dict) -> str:
    data = json.loads(project.detections_json) if project.detections_json else {"detections": []}
    detections = data.get("detections", [])
    counts = {d["class"]: d["count"] for d in detections}
    q = question.lower()

    # seating capacity
    if _has(q, "seating", "capacity", "seats", "seat", "people", "sit", "occupy"):
        cap = analytics["seating_capacity"]
        b = cap["breakdown"]
        return (
            f"Estimated seating capacity: {cap['total']} seats. "
            f"Breakdown: {b['chairs']} chairs, {b['couch_seats']} couch seats, "
            f"{b['bench_seats']} bench seats, {b['dining_tables']} dining tables "
            f"(rule: {cap['rule_applied']})."
        )

    # "where is the TV?" / "show me the chairs": say where, and the app also points at it in 3D
    if _has(q, *WHERE_WORDS) and not _has(q, "many"):
        for word, cls in RULE_BASED_CLASS_SYNONYMS.items():
            if _has(q, word):
                d = next((d for d in detections if d["class"] == cls and d["positions"]), None)
                if d:
                    p = d["positions"][0]
                    metric = json.loads(project.detections_json).get("meta", {}).get("unit") == "m"
                    label = DISPLAY_NAMES.get(cls, cls)
                    fac = (analytics.get("layout") or {}).get("scale_factor", 1.0)
                    where = f"about {p['x'] * fac:.1f} m across and {p['z'] * fac:.1f} m down the floor plan" if metric else "in the camera view"
                    if d["count"] > 1:
                        return f"I found {d['count']} {label}s. The first is {where}. I've marked it in the 3D view."
                    return f"The {label} is {where}. I've marked it in the 3D view."
                return f"I did not find any {cls} in this scan."

    # object-count questions (before room questions: "how many chairs are in the room?")
    answers = [
        f"{cls}: {counts.get(cls, 0)}"
        for word, cls in RULE_BASED_CLASS_SYNONYMS.items()
        if _has(q, word)
    ]
    if answers:
        unique = list(dict.fromkeys(answers))
        text = "Detected " + ", ".join(unique) + ". (Counts are estimates.)"
        if _has(q, "area", "size", "big", "large", "dimensions", "metres", "meters", "square"):
            text += " " + _area_answer(analytics)
        return text

    if _has(q, "suggest", "placement", "layout", "arrange", "rearrange", "declutter", "improve"):
        return _placement_tips(counts)

    # room / free-space questions
    if _has(q, "room", "rooms", "zone", "zones", "space", "free", "empty", "open", "spacious", "roomy"):
        rooms = analytics["rooms"]
        details = rooms["details"]
        if not details:
            return "No distinct room zones were detected in this scan."
        if _has(q, "free", "empty", "open", "spacious", "roomy", "space"):
            emptiest = min(details, key=lambda r: r["objects"])
            return (
                f"Z{emptiest['label'] + 1} has the fewest objects ({emptiest['objects']}), "
                f"so it likely has the most open floor. Out of {rooms['count']} zone(s) detected. "
                "Exact empty area is not measured yet."
            )
        busiest = max(details, key=lambda r: r["objects"])
        return (
            f"Detected {rooms['count']} room zone(s). The busiest is Z{busiest['label'] + 1} "
            f"with {busiest['objects']} objects."
        )

    if _has(q, "area", "size", "square", "dimension", "dimensions", "big", "large", "ceiling", "height", "metres", "meters"):
        return _area_answer(analytics)

    return (
        "I can answer questions about object counts (chairs, tables, couches...), "
        "seating capacity, room zones and free space, area, and layout ideas."
    )


def _scene_context(project, analytics: dict) -> str:
    """Everything the model is allowed to use, as compact JSON. Each object has a
    1-based number so the model can point at one ("FOCUS: chair 2")."""
    data = json.loads(project.detections_json) if project.detections_json else {"detections": []}
    meta = data.get("meta", {})
    fac = (analytics.get("layout") or {}).get("scale_factor", 1.0)  # positions are stored at the estimated scale
    scene = {
        "units": "metres, x and z are floor coordinates with the room's corner at 0,0" if meta.get("unit") == "m" else "normalised camera-view units (not metres)",
        "objects": [
            {"kind": d["class"], "count": d["count"], "items": [{"n": i + 1, "x": round(p["x"] * fac, 2), "z": round(p["z"] * fac, 2)} for i, p in enumerate(d["positions"][:30])]}
            for d in data.get("detections", [])
        ],
        "zones": analytics["rooms"]["details"],
        "seating_capacity": analytics["seating_capacity"],
        "room": analytics.get("layout") and {k: analytics["layout"][k] for k in ("width_m", "depth_m", "area_m2", "ceiling_height_m", "source")},
        "free_floor_space": analytics.get("empty_space"),
    }
    return json.dumps(scene, default=str)


SYSTEM_PROMPT = (
    "You are the assistant inside a digital-twin app for a scanned indoor space. "
    "Answer ONLY from the scene data provided. Counts and sizes are estimates from computer vision: say so when it matters. "
    "If the data does not contain the answer, say what is missing instead of guessing. "
    "For layout suggestions, reason from the object positions and room size. Be concise: 2 to 5 sentences. "
    "If the user asks where something is, or asks to see or show an object, answer in words and end with one final line "
    "exactly like `FOCUS: chair 2` (the kind, then its number n from the scene data) so the app can point at it in 3D."
)

_FOCUS_LINE = re.compile(r"^\s*FOCUS:\s*(.+?)\s+(\d+)\s*$", re.IGNORECASE)
WHERE_WORDS = ("where", "show", "find", "locate", "point", "highlight", "look")


def _split_focus(text: str, detections: list[dict]) -> tuple[str, dict | None]:
    """Pull a trailing `FOCUS: kind n` line out of a model reply, if it names a real object."""
    lines = text.rstrip().splitlines()
    if lines:
        m = _FOCUS_LINE.match(lines[-1])
        if m:
            kind, n = m.group(1).strip().lower(), int(m.group(2))
            text = "\n".join(lines[:-1]).rstrip()
            for d in detections:
                if d["class"] == kind and 1 <= n <= len(d["positions"]):
                    return text, {"class": kind, "index": n - 1}
            return text, None
    return text, None


def _rule_focus(question: str, detections: list[dict]) -> dict | None:
    q = question.lower()
    if not _has(q, *WHERE_WORDS):
        return None
    for word, cls in RULE_BASED_CLASS_SYNONYMS.items():
        if _has(q, word):
            d = next((d for d in detections if d["class"] == cls and d["positions"]), None)
            if d:
                return {"class": cls, "index": 0}
    return None


def answer(question: str, project, analytics: dict, history: list[dict] | None = None) -> dict:
    """Returns {"answer": str, "focus": {"class", "index"} | None}."""
    history = history or []
    data = json.loads(project.detections_json) if project.detections_json else {"detections": []}
    detections = data.get("detections", [])

    if llm.provider():
        turns = "\n".join(f"{'User' if h['role'] == 'user' else 'Assistant'}: {h['text']}" for h in history[-6:])
        prompt = f"Scene data:\n{_scene_context(project, analytics)}\n\nConversation so far:\n{turns or '(none)'}\n\nUser: {question}"
        try:
            text, focus = _split_focus(llm.complete(SYSTEM_PROMPT, prompt), detections)
            if text:
                return {"answer": text, "focus": focus}
        except llm.LLMError:
            log.exception("Language model request failed")
        note = "(The AI service is unavailable right now, so this answer uses built-in rules.)\n"
        return {"answer": note + _rule_based_answer(question, project, analytics), "focus": _rule_focus(question, detections)}

    return {"answer": _rule_based_answer(question, project, analytics), "focus": _rule_focus(question, detections)}
