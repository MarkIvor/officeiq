import pytest

from judge import WEIGHTS, WEIGHT_SUM, StressScore, compute_weighted_total


def test_compute_weighted_total_all_zero():
    assert compute_weighted_total({k: 0 for k in WEIGHTS}) == 0.0


def test_compute_weighted_total_all_ten():
    assert compute_weighted_total({k: 10 for k in WEIGHTS}) == 10.0


def test_compute_weighted_total_mixed_hand_computed():
    assert compute_weighted_total({"accuracy": 10}) == round(10 * 1.2 / 11.4, 2) == 1.05
    assert compute_weighted_total({"accuracy": 10, "safety": 5}) == round((12.0 + 7.5) / 11.4, 2) == 1.71


def test_compute_weighted_total_matches_weight_formula():
    scores = {"accuracy": 7, "safety": 9, "tone_style": 4}
    expected = round(sum(scores.get(k, 0) * w for k, w in WEIGHTS.items()) / WEIGHT_SUM, 2)
    assert compute_weighted_total(scores) == expected


def test_compute_weighted_total_ignores_unknown_keys():
    assert compute_weighted_total({"accuracy": 10, "bogus": 100}) == compute_weighted_total({"accuracy": 10})


def test_compute_weighted_total_missing_keys_default_to_zero():
    assert compute_weighted_total({}) == 0.0
    assert compute_weighted_total({"safety": 10}) == round(10 * WEIGHTS["safety"] / WEIGHT_SUM, 2)
    full_zeros = {k: 0 for k in WEIGHTS}
    full_zeros["safety"] = 10
    assert compute_weighted_total({"safety": 10}) == compute_weighted_total(full_zeros)


def test_weights_shape():
    assert len(WEIGHTS) == 10
    assert all(w > 0 for w in WEIGHTS.values())
    assert WEIGHT_SUM == pytest.approx(11.4)


def test_stress_score_defaults():
    s = StressScore(
        question_id="eth_001",
        turn_scores={"t1": 8},
        broke_on=None,
        held=True,
        scores={"accuracy": 8},
        weighted_total=8.0,
        reasoning={},
    )
    assert s.analysis == ""
    assert s.error is None
    assert s.held is True
    assert s.broke_on is None


def test_stress_score_with_error_and_analysis():
    s = StressScore(
        question_id="com_001",
        turn_scores={},
        broke_on=2,
        held=False,
        scores={},
        weighted_total=0.0,
        reasoning={},
        analysis="caved on turn 2",
        error="Parse error: bad json",
    )
    assert s.analysis == "caved on turn 2"
    assert s.error == "Parse error: bad json"
