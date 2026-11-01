import json

import build_leaderboard as lb


def test_load_runs_reads_fake_runs(fake_runs_dir):
    runs = lb.load_runs(fake_runs_dir)
    assert len(runs) == 3
    names = sorted(r["name"] for r in runs)
    assert names == ["Model A", "Model A", "Model B"]
    scores = {r["name"]: r["score"] for r in runs}
    assert scores["Model A"] in (6.0, 7.5)
    assert scores["Model B"] == 8.2


def test_load_runs_excludes_ab_mode(fake_runs_dir, run_factory):
    (fake_runs_dir / "ab.json").write_text(
        json.dumps(run_factory("Model A", 9.9, mode="ab_a"), ensure_ascii=False), encoding="utf-8"
    )
    (fake_runs_dir / "ab_b.json").write_text(
        json.dumps(run_factory("Model B", 9.9, mode="ab_b"), ensure_ascii=False), encoding="utf-8"
    )
    runs = lb.load_runs(fake_runs_dir)
    assert len(runs) == 3
    assert all(r["mode"] not in ("ab_a", "ab_b") for r in runs)


def test_load_runs_missing_dir(tmp_path):
    assert lb.load_runs(tmp_path / "no_such_dir") == []


def test_best_per_model_keeps_highest_and_sorts_desc(fake_runs_dir):
    runs = lb.load_runs(fake_runs_dir)
    best = lb.best_per_model(runs, "full")
    assert len(best) == 2
    assert best[0]["name"] == "Model B"
    assert best[0]["score"] == 8.2
    assert best[1]["name"] == "Model A"
    assert best[1]["score"] == 7.5
    assert [r["score"] for r in best] == sorted((r["score"] for r in best), reverse=True)


def test_best_per_model_filters_by_mode(fake_runs_dir, run_factory):
    (fake_runs_dir / "quick.json").write_text(
        json.dumps(run_factory("Model C", 4.0, mode="quick"), ensure_ascii=False), encoding="utf-8"
    )
    runs = lb.load_runs(fake_runs_dir)
    full = lb.best_per_model(runs, "full")
    quick = lb.best_per_model(runs, "quick")
    assert [r["name"] for r in full] == ["Model B", "Model A"]
    assert [r["name"] for r in quick] == ["Model C"]


def test_build_table_markdown(fake_runs_dir):
    runs = lb.best_per_model(lb.load_runs(fake_runs_dir), "full")
    table = lb.build_table(runs, "en")
    lines = [l for l in table.splitlines() if l.strip()]
    assert all(l.startswith("|") for l in lines)
    assert "Model B" in table
    assert "Model A" in table
    assert "8.20" in table
    assert "7.50" in table
    assert lines[0].startswith("| # | Model | Score |")


def test_build_table_ru(fake_runs_dir):
    runs = lb.best_per_model(lb.load_runs(fake_runs_dir), "full")
    table = lb.build_table(runs, "ru")
    assert "| # | Модель | Балл |" in table
    assert "Model B" in table


def test_build_table_empty_quick_start_text():
    assert "quick start" in lb.build_table([], "en")
    assert "быстрый-старт" in lb.build_table([], "ru")


def test_build_readme_insert_en(fake_runs_dir):
    insert = lb.build_readme_insert(lb.load_runs(fake_runs_dir), "en")
    assert "Model Top" in insert
    assert "Full (100 questions)" in insert
    assert "Model B" in insert
    assert "8.20" in insert


def test_build_readme_insert_ru(fake_runs_dir):
    insert = lb.build_readme_insert(lb.load_runs(fake_runs_dir), "ru")
    assert "Топ моделей" in insert
    assert "Full (100 вопросов)" in insert


def test_build_readme_insert_empty_runs_quick_start():
    insert = lb.build_readme_insert([], "en")
    assert "Model Top" in insert
    assert "quick start" in insert
    insert_ru = lb.build_readme_insert([], "ru")
    assert "Топ моделей" in insert_ru
    assert "быстрый-старт" in insert_ru


def test_update_readme_replaces_between_markers(tmp_path):
    path = tmp_path / "README.md"
    original = (
        "# Title\n\nsome intro\n\n"
        + lb.MARKER_START
        + "\nold leaderboard\n"
        + lb.MARKER_END
        + "\n\nsome footer\n"
    )
    path.write_text(original, encoding="utf-8")

    assert lb.update_readme(path, "NEW LEADERBOARD") is True

    text = path.read_text(encoding="utf-8")
    assert "NEW LEADERBOARD" in text
    assert "old leaderboard" not in text
    assert text.startswith("# Title")
    assert "some intro" in text
    assert "some footer" in text
    assert lb.MARKER_START in text
    assert lb.MARKER_END in text


def test_update_readme_missing_markers_returns_false(tmp_path):
    path = tmp_path / "README.md"
    path.write_text("no markers here", encoding="utf-8")
    assert lb.update_readme(path, "X") is False
    assert path.read_text(encoding="utf-8") == "no markers here"


def test_update_readme_missing_file_returns_false(tmp_path):
    assert lb.update_readme(tmp_path / "missing.md", "X") is False


def test_build_leaderboard_md_sections(fake_runs_dir):
    md = lb.build_leaderboard_md(lb.load_runs(fake_runs_dir), "https://github.com/x/y")
    assert "## Full mode (100 questions)" in md
    assert "## Quick mode (20 questions)" in md
    assert "Model B" in md


def test_build_leaderboard_md_stress_section(fake_runs_dir, run_factory):
    stress_run = run_factory("Model S", 6.0, mode="stress")
    stress_run["summary"]["held_pct"] = 60.0
    stress_run["summary"]["resilience_avg"] = 5.5
    stress_run["summary"]["broke_distribution"] = {2: 1, 3: 2}
    (fake_runs_dir / "stress.json").write_text(json.dumps(stress_run, ensure_ascii=False), encoding="utf-8")

    md = lb.build_leaderboard_md(lb.load_runs(fake_runs_dir), "https://github.com/x/y")
    assert "## Multi-turn Stress Test" in md
    assert "Model S" in md
