import pytest

from loader import QUICK_MODE_IDS, load_questions, load_rubric


def test_load_questions_full_returns_100(data_dir):
    questions = load_questions(data_dir)
    assert len(questions) == 100


def test_load_questions_quick_mode_returns_20_matching_ids(data_dir):
    questions = load_questions(data_dir, mode="quick")
    assert len(questions) == 20
    assert {q["id"] for q in questions} == set(QUICK_MODE_IDS)


def test_load_questions_category_filter(data_dir):
    questions = load_questions(data_dir, categories=["ethics"])
    assert len(questions) == 10
    assert all(q["category"] == "ethics" for q in questions)


def test_load_questions_limit_returns_first_five_in_file_order(data_dir):
    all_questions = load_questions(data_dir)
    limited = load_questions(data_dir, limit=5)
    assert len(limited) == 5
    assert [q["id"] for q in limited] == [q["id"] for q in all_questions[:5]]


def test_load_questions_question_ids_subset(data_dir):
    questions = load_questions(data_dir, question_ids=["com_001", "eth_004"])
    assert {q["id"] for q in questions} == {"com_001", "eth_004"}


def test_load_questions_question_ids_ignores_unknown(data_dir):
    questions = load_questions(data_dir, question_ids=["com_001", "no_such_id"])
    assert {q["id"] for q in questions} == {"com_001"}


def test_load_questions_lang_en_loads_english_edition(data_dir):
    ru = load_questions(data_dir)
    en = load_questions(data_dir, lang="en")
    assert len(en) == 100
    assert [q["id"] for q in en] == [q["id"] for q in ru]
    assert any(a["prompt"] != b["prompt"] for a, b in zip(ru, en))


def test_load_questions_invalid_lang_raises(data_dir):
    with pytest.raises(ValueError):
        load_questions(data_dir, lang="fr")


def test_load_rubric_returns_criteria(data_dir):
    rubric = load_rubric(data_dir)
    assert "criteria" in rubric
    assert len(rubric["criteria"]) == 10
    assert "judge_system_prompt" in rubric
