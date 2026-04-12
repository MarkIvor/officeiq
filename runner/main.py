import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))

from client import ModelClient, ModelConfig
from judge import Judge, WEIGHTS
from report import generate_report


BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config(path: str) -> dict:
    return load_yaml(Path(path))


def load_questions(categories: list = None, limit: int = None) -> list[dict]:
    data = load_yaml(DATA_DIR / "benchmark.yaml")
    questions = data["questions"]
    if categories:
        questions = [q for q in questions if q["category"] in categories]
    if limit:
        questions = questions[:limit]
    return questions


def load_rubric() -> dict:
    return load_yaml(DATA_DIR / "rubric.yaml")


def print_progress(label: str, current: list, total: int):
    n = len(current)
    bar = "█" * (n * 20 // total) + "░" * (20 - n * 20 // total)
    print(f"\r{label} [{bar}] {n}/{total}", end="", flush=True)


def save_run(run_data: dict, name: str) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = name.replace(" ", "_").replace("/", "-")
    path = RESULTS_DIR / f"{safe_name}_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(run_data, f, ensure_ascii=False, indent=2)
    return path


def build_run_data(
    config: dict,
    responses: list,
    scores: list,
    questions: list,
) -> dict:
    q_map = {q["id"]: q for q in questions}
    r_map = {r.question_id: r for r in responses}
    s_map = {s.question_id: s for s in scores}

    items = []
    for qid, q in q_map.items():
        r = r_map.get(qid)
        s = s_map.get(qid)
        items.append({
            "id": qid,
            "category": q["category"],
            "difficulty": q["difficulty"],
            "prompt": q.get("prompt", ""),
            "response": r.response if r else "",
            "latency_ms": r.latency_ms if r else 0,
            "response_error": r.error if r else "not run",
            "scores": s.scores if s else {},
            "weighted_total": s.weighted_total if s else 0.0,
            "reasoning": s.reasoning if s else {},
            "judge_error": s.error if s else None,
        })

    all_weighted = [i["weighted_total"] for i in items if not i["judge_error"]]
    overall = round(sum(all_weighted) / len(all_weighted), 2) if all_weighted else 0.0

    cat_scores = {}
    for item in items:
        cat = item["category"]
        if cat not in cat_scores:
            cat_scores[cat] = []
        if not item["judge_error"]:
            cat_scores[cat].append(item["weighted_total"])

    category_summary = {
        cat: round(sum(vals) / len(vals), 2) if vals else 0.0
        for cat, vals in cat_scores.items()
    }

    criteria_summary = {}
    for criterion in WEIGHTS:
        vals = [i["scores"].get(criterion, 0) for i in items if i["scores"] and not i["judge_error"]]
        criteria_summary[criterion] = round(sum(vals) / len(vals), 2) if vals else 0.0

    return {
        "meta": {
            "model_name": config.get("name", config.get("model", "unknown")),
            "model_id": config.get("model"),
            "base_url": config.get("base_url"),
            "system_prompt": config.get("system_prompt"),
            "run_at": datetime.now().isoformat(),
            "total_questions": len(questions),
            "answered": len([r for r in responses if not r.error]),
            "judge_errors": len([s for s in scores if s.error]),
        },
        "summary": {
            "overall_score": overall,
            "category_scores": category_summary,
            "criteria_scores": criteria_summary,
        },
        "items": items,
    }


async def run_benchmark(args):
    if args.config:
        cfg = load_config(args.config)
    else:
        cfg = {
            "name": args.name or args.model,
            "base_url": args.base_url,
            "api_key": args.api_key,
            "model": args.model,
            "system_prompt": args.system_prompt,
        }

    if not cfg.get("api_key"):
        cfg["api_key"] = os.environ.get("MODEL_API_KEY", "")
    if not cfg.get("api_key"):
        print("ERROR: api_key не указан (--api-key или MODEL_API_KEY)")
        sys.exit(1)

    judge_key = args.judge_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not judge_key:
        print("ERROR: judge api key не указан (--judge-key или ANTHROPIC_API_KEY)")
        sys.exit(1)

    categories = cfg.get("categories") or (args.categories.split(",") if args.categories else None)
    limit = cfg.get("limit") or args.limit

    questions = load_questions(categories=categories, limit=limit)
    rubric = load_rubric()

    model_config = ModelConfig(
        name=cfg.get("name", cfg.get("model", "unknown")),
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        system_prompt=cfg.get("system_prompt"),
        timeout=cfg.get("timeout", 60),
        concurrency=cfg.get("concurrency", 5),
    )

    print(f"\nSkald Bench — {model_config.name}")
    print(f"Вопросов: {len(questions)} | Параллельность: {model_config.concurrency}")
    print("─" * 50)

    client = ModelClient(model_config)
    responses = []

    def on_response(r):
        responses.append(r)
        status = "✓" if not r.error else "✗"
        print_progress(f"Опрос модели {status}", responses, len(questions))

    responses = await client.run(questions, progress_cb=on_response)
    print(f"\n✓ Получено {len([r for r in responses if not r.error])}/{len(questions)} ответов")

    print("\nЗапуск судьи (Claude Sonnet)...")
    judge = Judge(
        api_key=judge_key,
        model=args.judge_model,
        concurrency=3,
    )
    scores = []

    def on_score(s):
        scores.append(s)
        print_progress("Оценка судьи   ", scores, len(responses))

    scores = await judge.run(
        responses,
        system_prompt=rubric["judge_system_prompt"],
        user_template=rubric["judge_user_template"],
        progress_cb=on_score,
    )
    print(f"\n✓ Оценено {len([s for s in scores if not s.error])}/{len(questions)}")

    run_data = build_run_data(cfg, responses, scores, questions)

    result_path = save_run(run_data, cfg.get("name", cfg.get("model", "run")))
    print(f"\n✓ Результаты: {result_path}")

    s = run_data["summary"]
    print(f"\n{'─'*50}")
    print(f"ИТОГ: {s['overall_score']:.2f}/10")
    print(f"{'─'*50}")
    for cat, score in sorted(s["category_scores"].items(), key=lambda x: -x[1]):
        bar = "█" * int(score) + "░" * (10 - int(score))
        print(f"  {cat:<20} {bar} {score:.2f}")

    if args.compare:
        all_runs = [run_data]
        for compare_path in args.compare:
            with open(compare_path, encoding="utf-8") as f:
                all_runs.append(json.load(f))
        report_path = result_path.with_suffix(".html")
        generate_report(all_runs, report_path)
        print(f"\n✓ HTML отчёт (сравнение): {report_path}")
    else:
        report_path = result_path.with_suffix(".html")
        generate_report([run_data], report_path)
        print(f"✓ HTML отчёт: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Skald Bench — бенчмарк AI-ассистентов для офисных задач"
    )
    parser.add_argument("--config", help="Путь к YAML-конфигу модели")
    parser.add_argument("--base-url", default="https://api.openai.com/v1")
    parser.add_argument("--api-key", help="API ключ тестируемой модели")
    parser.add_argument("--model", help="ID модели")
    parser.add_argument("--name", help="Название для отчёта")
    parser.add_argument("--system-prompt", help="Системный промпт")
    parser.add_argument("--judge-key", help="API ключ для Claude (судья)")
    parser.add_argument("--judge-model", default="claude-sonnet-4-5", help="Модель-судья")
    parser.add_argument("--categories", help="Категории через запятую")
    parser.add_argument("--limit", type=int, help="Лимит вопросов")
    parser.add_argument("--compare", nargs="+", help="JSON файлы других прогонов для сравнения")

    args = parser.parse_args()

    if not args.config and not (args.base_url and args.model):
        parser.error("Нужен --config или --base-url + --model")

    asyncio.run(run_benchmark(args))


if __name__ == "__main__":
    main()
