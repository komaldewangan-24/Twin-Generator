"""Assistant backends and the "point at it in 3D" behaviour, with no network."""

import json
from types import SimpleNamespace

import httpx
import pytest

from app.core.config import settings
from app.services import chat, llm
from app.services.capacity import compute_capacity

DETECTIONS = [
    {"class": "tv", "count": 1, "positions": [{"x": 1.3, "z": 1.0, "confidence": 0.9, "world": [0.1, 0.2, 0.3]}]},
    {"class": "chair", "count": 2, "positions": [{"x": 2.0, "z": 2.0, "confidence": 0.8}, {"x": 3.0, "z": 2.5, "confidence": 0.7}]},
]
PROJECT = SimpleNamespace(detections_json=json.dumps({"detections": DETECTIONS, "meta": {"unit": "m"}}))
ANALYTICS = {
    "seating_capacity": compute_capacity(DETECTIONS),
    "rooms": {"count": 1, "details": [{"label": 0, "objects": 3, "bounds": [1, 1, 3, 2.5]}]},
    "area": {"calibration": None, "unit_area": None},
    "layout": {"width_m": 4.7, "depth_m": 3.7, "area_m2": 14.2, "ceiling_height_m": 2.3, "source": "estimated"},
}


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _configure(monkeypatch, **values):
    for key, value in {"LLM_PROVIDER": "", "LLM_MODEL": "", "LLM_BASE_URL": "", "GEMINI_API_KEY": "",
                       "LLM_API_KEY": "", **values}.items():
        monkeypatch.setattr(settings, key, value)


def test_no_provider_means_rules(monkeypatch):
    _configure(monkeypatch)
    assert llm.provider() is None


def test_generic_keys_in_the_environment_are_never_picked_up(monkeypatch):
    """Regression: a shell-wide ANTHROPIC_API_KEY made the app send scan data to
    Anthropic without the user choosing it. Only LLM_PROVIDER selects a provider."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ambient")
    monkeypatch.setenv("OPENAI_API_KEY", "ambient")
    _configure(monkeypatch, LLM_API_KEY="somekey")        # a key alone, with no provider chosen
    assert llm.provider() is None
    _configure(monkeypatch, GEMINI_API_KEY="legacy")      # the old documented setting still works
    assert llm.provider() == "gemini"


def test_anthropic_request_shape_and_parsing(monkeypatch):
    _configure(monkeypatch, LLM_PROVIDER="anthropic", LLM_API_KEY="secret")
    seen = {}

    def handler(request):
        seen.update(url=str(request.url), key=request.headers["x-api-key"], body=json.loads(request.content))
        return httpx.Response(200, json={"content": [{"type": "text", "text": "Two chairs."}]})

    assert llm.complete("be brief", "how many chairs?", client=_client(handler)) == "Two chairs."
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["key"] == "secret"
    assert seen["body"]["system"] == "be brief"
    assert seen["body"]["model"] == "claude-haiku-5-5"
    assert seen["body"]["messages"] == [{"role": "user", "content": "how many chairs?"}]


def test_ollama_uses_local_endpoint_without_a_key(monkeypatch):
    _configure(monkeypatch, LLM_PROVIDER="ollama", LLM_MODEL="llama3.2")
    seen = {}

    def handler(request):
        seen.update(url=str(request.url), auth=request.headers.get("authorization"), body=json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "Hello"}}]})

    assert llm.complete("sys", "hi", client=_client(handler)) == "Hello"
    assert seen["url"] == "http://localhost:11434/v1/chat/completions"
    assert seen["auth"] is None
    assert seen["body"]["model"] == "llama3.2"


def test_provider_errors_become_llm_error(monkeypatch):
    _configure(monkeypatch, LLM_PROVIDER="anthropic", LLM_API_KEY="k")
    with pytest.raises(llm.LLMError):
        llm.complete("s", "p", client=_client(lambda r: httpx.Response(500, json={"error": "boom"})))


def test_model_reply_focus_line_becomes_a_pointer(monkeypatch):
    monkeypatch.setattr(llm, "provider", lambda: "openai")
    monkeypatch.setattr(llm, "complete", lambda system, prompt, client=None: "The second chair is by the window.\nFOCUS: chair 2")
    result = chat.answer("show me the second chair", PROJECT, ANALYTICS)
    assert result["answer"] == "The second chair is by the window."
    assert result["focus"] == {"class": "chair", "index": 1}


def test_focus_naming_a_missing_object_is_ignored(monkeypatch):
    monkeypatch.setattr(llm, "provider", lambda: "openai")
    monkeypatch.setattr(llm, "complete", lambda system, prompt, client=None: "Here.\nFOCUS: couch 1")
    assert chat.answer("where is the couch", PROJECT, ANALYTICS)["focus"] is None


def test_when_the_model_fails_rules_still_answer(monkeypatch):
    monkeypatch.setattr(llm, "provider", lambda: "openai")

    def boom(system, prompt, client=None):
        raise llm.LLMError("down")

    monkeypatch.setattr(llm, "complete", boom)
    result = chat.answer("How many chairs?", PROJECT, ANALYTICS)
    assert "chair: 2" in result["answer"] and "built-in rules" in result["answer"]


def test_rules_answer_where_questions_and_point_at_the_object(monkeypatch):
    _configure(monkeypatch)
    result = chat.answer("Where is the TV?", PROJECT, ANALYTICS)
    assert "TV is about 1.3 m" in result["answer"] and "3D" in result["answer"]
    assert result["focus"] == {"class": "tv", "index": 0}
    assert chat.answer("How many chairs are there?", PROJECT, ANALYTICS)["focus"] is None
    assert "did not find any couch" in chat.answer("Where is the couch?", PROJECT, ANALYTICS)["answer"]


def test_chat_counts_win_over_room_keywords():
    """'How many chairs are in the room?' must answer with chairs, not zones."""
    import json
    from types import SimpleNamespace

    from app.services.chat import _rule_based_answer

    det = [{"class": "chair", "count": 4, "positions": [{"x": .1, "z": .1, "confidence": .9}] * 4}]
    project = SimpleNamespace(detections_json=json.dumps({"detections": det}))
    analytics = {"seating_capacity": compute_capacity(det), "rooms": {"count": 1, "details": [{"label": 0, "objects": 4}]}, "area": {"calibration": None, "unit_area": None}}
    answer = _rule_based_answer("How many chairs are in the room?", project, analytics)
    assert "chair: 4" in answer


def test_chat_free_space_picks_emptiest_zone():
    import json
    from types import SimpleNamespace

    from app.services.chat import _rule_based_answer

    project = SimpleNamespace(detections_json=json.dumps({"detections": []}))
    analytics = {"seating_capacity": compute_capacity([]), "rooms": {"count": 2, "details": [{"label": 0, "objects": 9}, {"label": 1, "objects": 2}]}, "area": {"calibration": None, "unit_area": None}}
    answer = _rule_based_answer("Which room has the most free space?", project, analytics)
    assert "Z2" in answer


def test_chat_answers_counts_and_room_size_together():
    import json
    from types import SimpleNamespace

    from app.services.chat import _rule_based_answer

    det = [{"class": "chair", "count": 2, "positions": [{"x": 1, "z": 1, "confidence": .9}] * 2}]
    project = SimpleNamespace(detections_json=json.dumps({"detections": det}))
    layout = {"width_m": 4.7, "depth_m": 3.7, "area_m2": 14.2, "ceiling_height_m": 2.3, "source": "estimated"}
    analytics = {"seating_capacity": compute_capacity(det), "rooms": {"count": 1, "details": []}, "layout": layout, "area": {"calibration": None, "unit_area": None}}
    answer = _rule_based_answer("How big is the room and how many chairs?", project, analytics)
    assert "chair: 2" in answer and "4.7" in answer and "3.7" in answer


def test_the_assistant_knows_doors_windows_and_lights(monkeypatch):
    """The open-vocabulary classes are answerable by name, in the singular and the plural."""
    _configure(monkeypatch)
    detections = [
        {"class": "window", "count": 2, "positions": [{"x": 0.3, "z": 1.8, "confidence": 0.1, "world": [1, 2, 3]}, {"x": 2.0, "z": 3.7, "confidence": 0.1}]},
        {"class": "door", "count": 1, "positions": [{"x": 4.7, "z": 1.0, "confidence": 0.1}]},
    ]
    project = SimpleNamespace(detections_json=json.dumps({"detections": detections, "meta": {"unit": "m"}}))
    analytics = dict(ANALYTICS, layout=dict(ANALYTICS["layout"], scale_factor=2.0))

    counted = chat.answer("How many windows are there?", project, analytics)["answer"]
    assert "window: 2" in counted
    where = chat.answer("Where is the door?", project, analytics)
    assert "9.4 m across" in where["answer"]                 # 4.7 m at the estimate, doubled by the saved scale
    assert where["focus"] == {"class": "door", "index": 0}
