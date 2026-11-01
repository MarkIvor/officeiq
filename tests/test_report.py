from report import generate_report


def test_generate_report_single_run(tmp_path, run_factory):
    run = run_factory("TestModel X", 7.53)
    out = tmp_path / "report.html"

    generate_report([run], out)

    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert "TestModel X" in html
    assert "7.53" in html
    assert "type: 'radar'" in html
    assert "type: 'bar'" in html
    assert "radarDatasets" in html
    assert "Отчёт: TestModel X" in html


def test_generate_report_contains_item_details(tmp_path, run_factory):
    run = run_factory("TestModel X", 7.5)
    out = tmp_path / "report.html"

    generate_report([run], out)

    html = out.read_text(encoding="utf-8")
    assert "eth_001" in html
    assert "How to refuse an unethical request?" in html
    assert "clear position" in html
    assert html.startswith("<!DOCTYPE html>")


def test_generate_report_compare_mode(tmp_path, run_factory):
    runs = [run_factory("Model A", 7.5), run_factory("Model B", 8.2)]
    out = tmp_path / "compare.html"

    generate_report(runs, out)

    html = out.read_text(encoding="utf-8")
    assert "Сравнение моделей" in html
    assert "Model A" in html
    assert "Model B" in html
