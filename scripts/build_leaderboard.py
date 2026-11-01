#!/usr/bin/env python3
"""Build the public leaderboard from results/*.json.

Outputs:
  - LEADERBOARD.md      static markdown leaderboard (English primary, Quick mode)
  - README.md / README.ru.md  top-10 table injected between markers

Run from repo root:  python scripts/build_leaderboard.py
Exits 0 even with no results (generates a placeholder).
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

EXCLUDED_MODES = {"ab_a", "ab_b", "consistency", "retry", "autotune", "autotune_a", "autotune_b1", "autotune_b2", "autotune_b3", "full"}

MEDALS = ["🥇", "🥈", "🥉"]

CATEGORY_LABELS_EN = {
    "communication": "Communication", "meetings": "Meetings", "documents": "Documents",
    "analytics": "Analytics", "hr_team": "HR & Team", "negotiations": "Negotiations",
    "stress": "Stress", "ethics": "Ethics", "emotional": "Emotional", "adversarial": "Adversarial",
}
CATEGORY_LABELS_RU = {
    "communication": "Коммуникация", "meetings": "Встречи", "documents": "Документы",
    "analytics": "Аналитика", "hr_team": "HR и команда", "negotiations": "Переговоры",
    "stress": "Стресс", "ethics": "Этика", "emotional": "Эмоции", "adversarial": "Adversarial",
}

MARKER_START = "<!-- leaderboard-start -->"
MARKER_END = "<!-- leaderboard-end -->"


def level_en(score: float) -> str:
    if score >= 9: return "Elite"
    if score >= 8: return "Strong"
    if score >= 7: return "Good"
    if score >= 6: return "Average"
    return "Weak"


def level_ru(score: float) -> str:
    if score >= 9: return "Элита"
    if score >= 8: return "Сильный"
    if score >= 7: return "Хороший"
    if score >= 6: return "Средний"
    return "Слабый"


def load_runs(results_dir: Path) -> list:
    runs = []
    if not results_dir.exists():
        return runs
    for f in sorted(results_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            meta = data.get("meta") or {}
            summary = data.get("summary") or {}
            score = summary.get("overall_score")
            if score is None or not meta.get("model_name"):
                continue
            mode = meta.get("mode", "full")
            if mode in EXCLUDED_MODES:
                continue
            coverage = meta.get("coverage")
            if coverage is None:
                coverage = meta.get("answered", 0)
            runs.append({
                "filename": f.name,
                "name": meta["model_name"],
                "score": round(float(score), 2),
                "mode": mode,
                "lang": meta.get("lang", "ru"),
                "coverage": coverage,
                "total": meta.get("total_questions", 0),
                "date": (meta.get("run_at") or "")[:10],
                "category_scores": summary.get("category_scores") or {},
                "criteria_scores": summary.get("criteria_scores") or {},
                "held_pct": summary.get("held_pct"),
                "resilience_avg": summary.get("resilience_avg"),
                "broke_distribution": summary.get("broke_distribution") or {},
            })
        except Exception:
            continue
    return runs


def best_per_model(runs: list, mode: str) -> list:
    """Best run per model name within one mode."""
    by_model = {}
    for r in [x for x in runs if x["mode"] == mode]:
        cur = by_model.get(r["name"])
        if cur is None or (r["score"], r["date"]) > (cur["score"], cur["date"]):
            by_model[r["name"]] = r
    return sorted(by_model.values(), key=lambda r: -r["score"])


def mode_label(mode: str, lang: str) -> str:
    if lang == "ru":
        return "Full (100 вопросов)" if mode == "full" else "Quick (20 вопросов)"
    return "Full (100 questions)" if mode == "full" else "Quick (20 questions)"


def _cat(run: dict, key: str) -> str:
    v = run["category_scores"].get(key)
    return f"{v:.1f}" if isinstance(v, (int, float)) else "—"


def _crit(run: dict, key: str) -> str:
    v = run["criteria_scores"].get(key)
    return f"{v:.1f}" if isinstance(v, (int, float)) else "—"


def build_table(runs: list, lang: str = "en") -> str:
    """Markdown leaderboard table for one mode."""
    if not runs:
        if lang == "ru":
            return "_Пока нет прогонов в этом режиме. Будь первым — [инструкция](README.ru.md#быстрый-старт)._"
        return "_No runs in this mode yet. Be the first — see the [quick start](README.md#quick-start)._"
    if lang == "ru":
        header = ("| # | Модель | Балл | Уровень | Безопасность | Adversarial | Охват | Язык | Дата |\n"
                  "|---|--------|------|---------|--------------|-------------|-------|------|------|\n")
        lang_tag = {"ru": "RU", "en": "EN"}
    else:
        header = ("| # | Model | Score | Level | Safety | Adversarial | Coverage | Lang | Date |\n"
                  "|---|-------|-------|-------|--------|-------------|----------|------|------|\n")
        lang_tag = {"ru": "RU", "en": "EN"}
    rows = []
    for i, r in enumerate(runs):
        medal = MEDALS[i] if i < 3 and lang != "ru" else (MEDALS[i] if i < 3 else "")
        rank = medal or str(i + 1)
        lvl = level_ru(r["score"]) if lang == "ru" else level_en(r["score"])
        rows.append(
            f"| {rank} | {r['name']} | **{r['score']:.2f}** | {lvl} "
            f"| {_crit(r, 'safety')} | {_cat(r, 'adversarial')} "
            f"| {r['coverage']}/{r['total']} | {lang_tag.get(r['lang'], r['lang'])} | {r['date']} |"
        )
    return header + "\n".join(rows) + "\n"


def build_stress_table(runs: list, lang: str = "en") -> str:
    if not runs:
        return ""
    if lang == "ru":
        header = ("| # | Модель | Стрессоустойчивость | Держалась до конца | Сдалась на ходу |\n"
                  "|---|--------|---------------------|--------------------|------------------|\n")
        held_lbl = "выдержала"
    else:
        header = ("| # | Model | Resilience | Held to the end | Caved on turn |\n"
                  "|---|-------|------------|-----------------|---------------|\n")
        held_lbl = "held"
    rows = []
    for i, r in enumerate(runs[:10]):
        rank = MEDALS[i] if i < 3 else str(i + 1)
        broke = ", ".join(f"t{k}: {v}" for k, v in sorted(r["broke_distribution"].items())) or "—"
        resilience = f"{r['resilience_avg']:.2f}" if isinstance(r["resilience_avg"], (int, float)) else "—"
        rows.append(f"| {rank} | {r['name']} | {resilience} | {r['held_pct'] or 0}% ({held_lbl}) | {broke} |")
    return header + "\n".join(rows) + "\n"


def build_leaderboard_md(runs: list, repo_url: str) -> str:
    quick = best_per_model(runs, "quick")
    stress = best_per_model(runs, "stress")
    generated = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    md = f"""# 🏆 OfficeIQ Bench — Public Leaderboard

Which LLM should you put in front of your corporate assistant **today**?
100 office scenarios · 10 criteria · LLM-as-a-judge · reproducible runs.
Русская версия таблиц — в [README.ru.md](README.ru.md).

> Скоринг: средневзвешенный балл 0–10 по 10 критериям (Safety ×1.5, Ethics ×1.3, …).
> Все прогоны — **Quick mode** (20 вопросов: 10 категорий × 2 вопроса, RU/EN = язык вопросов бенчмарка,
> судья — Claude Opus 5.5). Баллы разных языков сравнивать можно, но осторожно.

## Quick mode (20 questions)

{build_table(quick, 'en')}
"""
    if stress:
        md += f"""
## Multi-turn Stress Test

Same scenarios, but a scripted provocateur applies 3 rounds of escalating pressure
after the first answer. Judges report on which turn the model caved.

{build_stress_table(stress, 'en')}
"""
    md += f"""
## How to add your model

1. Clone the repo, `pip install -r requirements.txt`, run `python server.py`.
2. Add your model (any OpenAI-compatible API), run the benchmark.
3. Commit the `results/*.json` — CI rebuilds this page automatically.

Methodology: [README.md](README.md) · Run your own: [officeiq](https://github.com/MarkIvor/officeiq)

---
*Auto-generated by `scripts/build_leaderboard.py` at {generated}.*
"""
    return md


def build_readme_insert(runs: list, lang: str = "en") -> str:
    board = best_per_model(runs, "quick")
    if lang == "ru":
        title = f"### Топ моделей — {mode_label('quick', 'ru')}"
        note = ("Балл 0–10: средневзвешенная оценка 10 критериев, судья — Claude Opus 5.5. "
                "Полная таблица и стресс-тест — в [LEADERBOARD.md](LEADERBOARD.md).")
    else:
        title = f"### Model Top — {mode_label('quick', 'en')}"
        note = ("Score 0–10: weighted average across 10 criteria, judge — Claude Opus 5.5. "
                "Full table and the stress test — in [LEADERBOARD.md](LEADERBOARD.md).")
    return f"{title}\n\n{build_table(board[:10], lang)}\n{note}\n"


def update_readme(path: Path, insert: str) -> bool:
    if not path.exists() or MARKER_START not in path.read_text(encoding="utf-8"):
        return False
    text = path.read_text(encoding="utf-8")
    before, rest = text.split(MARKER_START, 1)
    _, after = rest.split(MARKER_END, 1)
    path.write_text(before + MARKER_START + "\n\n" + insert + "\n" + MARKER_END + after, encoding="utf-8")
    return True


def main():
    parser = argparse.ArgumentParser(description="Build public leaderboard from results/")
    parser.add_argument("--results-dir", default=None, help="directory with run JSON files")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    results_dir = Path(args.results_dir) if args.results_dir else root / "results"
    repo_url = "https://github.com/MarkIvor/officeiq"

    runs = load_runs(results_dir)

    leaderboard_md = build_leaderboard_md(runs, repo_url)
    (root / "LEADERBOARD.md").write_text(leaderboard_md, encoding="utf-8")

    en_updated = update_readme(root / "README.md", build_readme_insert(runs, "en"))
    ru_updated = update_readme(root / "README.ru.md", build_readme_insert(runs, "ru"))

    print(f"leaderboard: {len(runs)} runs -> LEADERBOARD.md; "
          f"README.md {'updated' if en_updated else 'markers missing'}, "
          f"README.ru.md {'updated' if ru_updated else 'markers missing'}")


if __name__ == "__main__":
    main()

