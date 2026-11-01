import server
from judge import WEIGHTS


def _questions():
    return [
        {"id": "eth_001", "category": "ethics", "difficulty": "easy", "prompt": "Q1"},
        {"id": "eth_002", "category": "ethics", "difficulty": "medium", "prompt": "Q2"},
        {"id": "com_001", "category": "communication", "difficulty": "hard", "prompt": "Q3"},
    ]


def test_build_run_data_overall_and_categories(response_factory, score_factory):
    questions = _questions()
    responses = [
        response_factory("eth_001", "ethics", "easy", "Q1", response="good one"),
        response_factory("com_001", "communication", "hard", "Q3", response="good three"),
        response_factory("eth_002", "ethics", "medium", "Q2", response="", error="HTTP 500", attempts=5),
    ]
    scores = [
        score_factory("eth_001", scores={k: 10 for k in WEIGHTS}, weighted_total=10.0, prompt_fix="fix ethics"),
        score_factory("com_001", scores={k: 5 for k in WEIGHTS}, weighted_total=5.0, prompt_fix="fix com"),
        score_factory("eth_002", scores={k: 0 for k in WEIGHTS}, weighted_total=0.0, error="no answer"),
    ]
    config = {"name": "TestModel", "model": "test-model", "base_url": "http://x/v1", "system_prompt": "sp"}

    run = server.build_run_data(config, responses, scores, questions, mode="full")

    assert run["meta"]["model_name"] == "TestModel"
    assert run["meta"]["mode"] == "full"
    assert run["summary"]["overall_score"] == 7.5
    assert run["summary"]["category_scores"] == {"ethics": 10.0, "communication": 5.0}
    for criterion in WEIGHTS:
        assert run["summary"]["criteria_scores"][criterion] == 7.5


def test_build_run_data_skipped_and_meta(response_factory, score_factory):
    questions = _questions()
    responses = [
        response_factory("eth_001", "ethics", "easy", "Q1", response="good one"),
        response_factory("eth_002", "ethics", "medium", "Q2", response="", error="HTTP 500", attempts=5),
        response_factory("com_001", "communication", "hard", "Q3", response="good three"),
    ]
    scores = [
        score_factory("eth_001", scores={k: 10 for k in WEIGHTS}, weighted_total=10.0, prompt_fix="fix ethics"),
        score_factory("eth_002", scores={k: 0 for k in WEIGHTS}, weighted_total=0.0, error="no answer"),
        score_factory("com_001", scores={k: 5 for k in WEIGHTS}, weighted_total=5.0, prompt_fix="fix com"),
    ]
    config = {"name": "TestModel", "model": "test-model", "base_url": "http://x/v1", "system_prompt": "sp"}

    run = server.build_run_data(config, responses, scores, questions, mode="full")

    assert run["meta"]["skipped"] == ["eth_002"]
    assert run["meta"]["answered"] == 2
    assert run["meta"]["coverage"] == 2
    assert run["meta"]["judge_errors"] == 1
    assert run["meta"]["total_questions"] == 3

    items_by_id = {i["id"]: i for i in run["items"]}
    assert items_by_id["eth_002"]["skipped"] is True
    assert items_by_id["eth_002"]["response_error"] == "HTTP 500"
    assert not items_by_id["eth_001"]["skipped"]
    assert items_by_id["eth_001"]["response"] == "good one"
    assert items_by_id["eth_001"]["prompt_fix"] == "fix ethics"
    assert items_by_id["eth_001"]["judge_error"] is None


def test_build_run_data_prompt_fixes_aggregation(response_factory, score_factory):
    questions = _questions()
    responses = [
        response_factory("eth_001", "ethics", "easy", "Q1", response="r1"),
        response_factory("eth_002", "ethics", "medium", "Q2", response="r2"),
        response_factory("com_001", "communication", "hard", "Q3", response="r3"),
    ]
    scores = [
        score_factory("eth_001", scores={k: 8 for k in WEIGHTS}, weighted_total=8.0, prompt_fix="fix a"),
        score_factory("eth_002", scores={k: 6 for k in WEIGHTS}, weighted_total=6.0, prompt_fix="fix b"),
        score_factory("com_001", scores={k: 7 for k in WEIGHTS}, weighted_total=7.0, prompt_fix=""),
    ]
    config = {"name": "TestModel", "model": "test-model", "base_url": "http://x/v1", "system_prompt": "sp"}

    run = server.build_run_data(config, responses, scores, questions)

    assert run["summary"]["prompt_fixes"] == {"ethics": ["fix a", "fix b"]}
    assert run["summary"]["overall_score"] == 7.0


def test_build_run_data_error_low_attempts_not_skipped(response_factory, score_factory):
    questions = _questions()[:1]
    responses = [
        response_factory("eth_001", "ethics", "easy", "Q1", response="", error="HTTP 429", attempts=2),
    ]
    scores = [
        score_factory("eth_001", scores={k: 0 for k in WEIGHTS}, weighted_total=0.0, error="no answer"),
    ]
    config = {"name": "TestModel", "model": "test-model", "base_url": "http://x/v1", "system_prompt": "sp"}

    run = server.build_run_data(config, responses, scores, questions)

    assert run["meta"]["skipped"] == []
    assert run["items"][0]["skipped"] is False
    assert run["summary"]["overall_score"] == 0.0


def test_server_load_questions_quick_returns_20():
    questions = server.load_questions(mode="quick")
    assert len(questions) == 20
    assert all(q["id"].startswith(("com_", "meet_", "doc_", "ana_", "hr_", "neg_", "str_", "eth_", "emo_", "adv_")) for q in questions)
