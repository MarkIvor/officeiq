from collections import Counter

import pytest

from judge import WEIGHTS, WEIGHT_SUM
from loader import QUICK_MODE_IDS, load_yaml

BENCH_FILES = {"ru": "benchmark.yaml", "en": "benchmark.en.yaml"}


def load_benchmark(data_dir, lang):
    return load_yaml(data_dir / BENCH_FILES[lang])["questions"]


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_benchmark_has_exactly_100_questions(data_dir, lang):
    assert len(load_benchmark(data_dir, lang)) == 100


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_benchmark_ids_are_unique(data_dir, lang):
    ids = [q["id"] for q in load_benchmark(data_dir, lang)]
    assert len(ids) == 100
    assert len(set(ids)) == 100


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_benchmark_10_categories_with_10_questions_each(data_dir, lang):
    counts = Counter(q["category"] for q in load_benchmark(data_dir, lang))
    assert len(counts) == 10
    assert set(counts.values()) == {10}


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_benchmark_difficulties_are_valid(data_dir, lang):
    for q in load_benchmark(data_dir, lang):
        assert q["difficulty"] in {"easy", "medium", "hard"}


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_benchmark_prompts_non_empty(data_dir, lang):
    for q in load_benchmark(data_dir, lang):
        assert isinstance(q["prompt"], str)
        assert q["prompt"].strip()


def test_ru_en_ids_in_same_order(data_dir):
    ru = load_benchmark(data_dir, "ru")
    en = load_benchmark(data_dir, "en")
    assert [q["id"] for q in ru] == [q["id"] for q in en]


def test_ru_en_category_and_difficulty_parity(data_dir):
    ru = load_benchmark(data_dir, "ru")
    en = load_benchmark(data_dir, "en")
    for a, b in zip(ru, en):
        assert a["category"] == b["category"]
        assert a["difficulty"] == b["difficulty"]


def test_quick_mode_ids_shape(data_dir):
    assert len(QUICK_MODE_IDS) == 20
    assert len(set(QUICK_MODE_IDS)) == 20
    ru = {q["id"]: q for q in load_benchmark(data_dir, "ru")}
    en = {q["id"]: q for q in load_benchmark(data_dir, "en")}
    for qid in QUICK_MODE_IDS:
        assert qid in ru
        assert qid in en
    per_cat = Counter(ru[qid]["category"] for qid in QUICK_MODE_IDS)
    assert len(per_cat) == 10
    assert set(per_cat.values()) == {2}


def test_rubric_has_10_criteria_matching_weights(data_dir):
    rubric = load_yaml(data_dir / "rubric.yaml")
    criteria = rubric["criteria"]
    assert len(criteria) == 10
    assert {c["id"] for c in criteria} == set(WEIGHTS.keys())
    assert all(c["weight"] > 0 for c in criteria)
    assert sum(c["weight"] for c in criteria) == pytest.approx(WEIGHT_SUM)
    for c in criteria:
        assert c["weight"] == pytest.approx(WEIGHTS[c["id"]])


@pytest.mark.parametrize(
    "key",
    [
        "judge_system_prompt",
        "judge_user_template",
        "stress_judge_system_prompt",
        "stress_judge_user_template",
        "judge_system_prompt_en",
        "judge_user_template_en",
        "stress_judge_system_prompt_en",
        "stress_judge_user_template_en",
    ],
)
def test_rubric_templates_exist_and_non_empty(data_dir, key):
    rubric = load_yaml(data_dir / "rubric.yaml")
    assert key in rubric
    assert isinstance(rubric[key], str)
    assert rubric[key].strip()


@pytest.mark.parametrize("key", ["judge_user_template", "judge_user_template_en"])
def test_rubric_judge_user_template_placeholders(data_dir, key):
    template = load_yaml(data_dir / "rubric.yaml")[key]
    for placeholder in ("{category}", "{difficulty}", "{prompt}", "{response}"):
        assert placeholder in template


@pytest.mark.parametrize("key", ["stress_judge_user_template", "stress_judge_user_template_en"])
def test_rubric_stress_user_template_placeholders(data_dir, key):
    template = load_yaml(data_dir / "rubric.yaml")[key]
    for placeholder in ("{category}", "{difficulty}", "{prompt}", "{transcript}"):
        assert placeholder in template
