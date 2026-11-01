"""Shared data loaders for benchmark questions and rubric.

Used by server.py, runner/main.py and the stress simulator so the loading
rules (quick mode, category filters, language editions) live in one place.
"""
from pathlib import Path

import yaml

QUICK_MODE_IDS = [
    "com_003", "com_007",
    "meet_005", "meet_009",
    "doc_007", "doc_008",
    "ana_008", "ana_010",
    "hr_006", "hr_009",
    "neg_006", "neg_009",
    "str_007", "str_008",
    "eth_004", "eth_008",
    "emo_004", "emo_007",
    "adv_006", "adv_010",
]

BENCHMARK_FILES = {
    "ru": "benchmark.yaml",
    "en": "benchmark.en.yaml",
}


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_questions(
    data_dir: Path,
    categories: list = None,
    limit: int = None,
    mode: str = None,
    question_ids: list = None,
    lang: str = "ru",
) -> list[dict]:
    filename = BENCHMARK_FILES.get(lang)
    if filename is None:
        raise ValueError(f"Unknown benchmark language: {lang!r} (expected 'ru' or 'en')")
    data = load_yaml(Path(data_dir) / filename)
    questions = data["questions"]

    if question_ids:
        id_set = set(question_ids)
        return [q for q in questions if q["id"] in id_set]

    if mode == "quick":
        id_set = set(QUICK_MODE_IDS)
        return [q for q in questions if q["id"] in id_set]

    if categories:
        questions = [q for q in questions if q["category"] in categories]
    if limit:
        questions = questions[:limit]
    return questions


def load_rubric(data_dir: Path) -> dict:
    return load_yaml(Path(data_dir) / "rubric.yaml")
