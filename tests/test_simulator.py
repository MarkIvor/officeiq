import asyncio

from client import ModelConfig
from judge import WEIGHTS, StressScore
from simulator import (
    GENERIC_EN,
    GENERIC_RU,
    PRESSURE_EN,
    PRESSURE_RU,
    StressResult,
    build_stress_run_data,
    pressure_turns,
    run_stress,
)


def test_pressure_ru_has_10_categories_with_3_turns():
    assert len(PRESSURE_RU) == 10
    for category, turns in PRESSURE_RU.items():
        assert len(turns) == 3
        for turn in turns:
            assert isinstance(turn, str)
            assert turn.strip()


def test_pressure_en_has_10_categories_with_3_turns():
    assert len(PRESSURE_EN) == 10
    for category, turns in PRESSURE_EN.items():
        assert len(turns) == 3
        for turn in turns:
            assert isinstance(turn, str)
            assert turn.strip()


def test_pressure_ru_en_same_categories():
    assert set(PRESSURE_RU.keys()) == set(PRESSURE_EN.keys())


def test_pressure_turns_known_category():
    assert pressure_turns("ethics") == PRESSURE_RU["ethics"]
    assert len(pressure_turns("ethics")) == 3


def test_pressure_turns_unknown_category_falls_back_to_generic():
    assert pressure_turns("no_such_category") == GENERIC_RU
    assert pressure_turns("no_such_category", lang="en") == GENERIC_EN


def test_pressure_turns_lang_en():
    assert pressure_turns("communication", lang="en") == PRESSURE_EN["communication"]


def _stress_result():
    turns = [
        {"role": "user", "content": "original prompt", "latency_ms": None, "error": None},
        {"role": "assistant", "content": "first answer", "latency_ms": 120, "error": None},
        {"role": "user", "content": "pressure one", "latency_ms": None, "error": None},
        {"role": "assistant", "content": "held answer", "latency_ms": 130, "error": None},
    ]
    return StressResult("eth_001", "ethics", "medium", "original prompt", turns)


def test_transcript_ru_labels():
    transcript = _stress_result().transcript("ru")
    assert "[ХОД 1 | ПОЛЬЗОВАТЕЛЬ]" in transcript
    assert "[ХОД 2 | ДАВЛЕНИЕ]" in transcript
    assert "ДАВЛЕНИЕ" in transcript
    assert "[ХОД 1 | АССИСТЕНТ]" in transcript
    assert "original prompt" in transcript
    assert "pressure one" in transcript


def test_transcript_en_labels():
    transcript = _stress_result().transcript("en")
    assert "[TURN 1 | USER]" in transcript
    assert "[TURN 2 | PRESSURE]" in transcript
    assert "[TURN 1 | ASSISTANT]" in transcript


class FakeClient:
    def __init__(self, system_prompt="SYS PROMPT"):
        self.config = ModelConfig(
            name="fake",
            base_url="http://localhost/v1",
            api_key="key",
            model="fake-model",
            system_prompt=system_prompt,
        )
        self.calls = []

    async def chat(self, messages, http_client=None, timeout=None):
        self.calls.append([dict(m) for m in messages])
        return ("reply", None)


def test_run_stress_full_dialogue_per_question():
    fake = FakeClient("SYS PROMPT")
    questions = [
        {"id": "eth_001", "category": "ethics", "difficulty": "easy", "prompt": "Q1"},
        {"id": "com_001", "category": "communication", "difficulty": "easy", "prompt": "Q2"},
    ]

    results = asyncio.run(run_stress(fake, questions))

    assert len(results) == 2
    assert [r.question_id for r in results] == ["com_001", "eth_001"]
    for result in results:
        assert len(result.turns) == 8
        roles = [m["role"] for m in result.turns]
        assert roles == ["user", "assistant"] * 4
        assert result.error is None
        assert all(m["content"] for m in result.turns)


def test_run_stress_messages_accumulate():
    fake = FakeClient("SYS PROMPT")
    questions = [{"id": "eth_001", "category": "ethics", "difficulty": "easy", "prompt": "Q1"}]

    asyncio.run(run_stress(fake, questions))

    assert len(fake.calls) == 4
    assert [len(c) for c in fake.calls] == [2, 4, 6, 8]
    first = fake.calls[0]
    assert first[0]["role"] == "system"
    assert first[0]["content"] == "SYS PROMPT"
    assert first[1]["role"] == "user"
    assert first[1]["content"] == "Q1"
    assert fake.calls[1][2]["role"] == "assistant"
    assert fake.calls[1][2]["content"] == "reply"
    assert fake.calls[1][3]["role"] == "user"
    assert fake.calls[1][3]["content"] == pressure_turns("ethics")[0]
    assert fake.calls[3][-1]["content"] == pressure_turns("ethics")[2]


def test_run_stress_no_system_prompt():
    fake = FakeClient(None)
    questions = [{"id": "eth_001", "category": "ethics", "difficulty": "easy", "prompt": "Q1"}]

    asyncio.run(run_stress(fake, questions))

    assert [len(c) for c in fake.calls] == [1, 3, 5, 7]
    assert fake.calls[0][0]["role"] == "user"


def _full_turns():
    turns = []
    turns.append({"role": "user", "content": "P", "latency_ms": None, "error": None})
    turns.append({"role": "assistant", "content": "a1", "latency_ms": 10, "error": None})
    for i in range(3):
        turns.append({"role": "user", "content": f"pressure {i}", "latency_ms": None, "error": None})
        turns.append({"role": "assistant", "content": f"a{i + 2}", "latency_ms": 10, "error": None})
    return turns


def test_build_stress_run_data_summary():
    questions = [
        {"id": "eth_001", "category": "ethics", "difficulty": "easy", "prompt": "P1"},
        {"id": "com_001", "category": "communication", "difficulty": "medium", "prompt": "P2"},
    ]
    results = [
        StressResult("eth_001", "ethics", "easy", "P1", _full_turns()),
        StressResult("com_001", "communication", "medium", "P2", _full_turns()),
    ]
    scores = [
        StressScore(
            question_id="eth_001",
            turn_scores={"t1": 8, "t2": 7, "t3": 7, "t4": 8},
            broke_on=None,
            held=True,
            scores={k: 8 for k in WEIGHTS},
            weighted_total=8.0,
            reasoning={},
        ),
        StressScore(
            question_id="com_001",
            turn_scores={"t1": 6, "t2": 3, "t3": 2, "t4": 2},
            broke_on=2,
            held=False,
            scores={k: 5 for k in WEIGHTS},
            weighted_total=5.0,
            reasoning={},
        ),
    ]
    config = {"name": "StressModel", "model": "m", "base_url": "http://x/v1", "system_prompt": "sp"}

    data = build_stress_run_data(config, results, scores, questions, lang="en")

    assert data["meta"]["mode"] == "stress"
    assert data["meta"]["lang"] == "en"
    assert data["meta"]["model_name"] == "StressModel"
    assert data["meta"]["total_questions"] == 2
    assert data["meta"]["answered"] == 2
    assert data["summary"]["overall_score"] == 6.5
    assert data["summary"]["held_pct"] == 50.0
    assert data["summary"]["broke_distribution"] == {2: 1}
    assert data["summary"]["resilience_avg"] == round((8 + 7 + 7 + 8 + 6 + 3 + 2 + 2) / 8, 2)
    for criterion in WEIGHTS:
        assert data["summary"]["criteria_scores"][criterion] == 6.5
    assert data["summary"]["category_scores"] == {"ethics": 8.0, "communication": 5.0}
    items_by_id = {i["id"]: i for i in data["items"]}
    assert items_by_id["eth_001"]["held"] is True
    assert items_by_id["eth_001"]["broke_on"] is None
    assert items_by_id["com_001"]["held"] is False
    assert items_by_id["com_001"]["broke_on"] == 2
    assert len(items_by_id["eth_001"]["turns"]) == 8
