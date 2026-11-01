import asyncio
import json
import time
import uuid
from datetime import datetime
from pathlib import Path

import httpx
import yaml
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
RUNNER_DIR = BASE_DIR / "runner"

import sys
sys.path.insert(0, str(RUNNER_DIR))

from client import ModelClient, ModelConfig
from judge import Judge, WEIGHTS
from report import generate_report
from loader import load_questions as _load_questions, load_rubric as _load_rubric
from simulator import run_stress, build_stress_run_data
from optimizer import collect_fixes, synthesize_prompt

from fastapi.staticfiles import StaticFiles

app = FastAPI(title="OfficeIQ Bench")
RESULTS_DIR.mkdir(exist_ok=True)
app.mount("/ui", StaticFiles(directory=BASE_DIR / "ui"), name="ui")

_active_runs: dict[str, asyncio.Event] = {}

UI_MSGS = {
    "querying": ("Опрашиваем модель...", "Querying model..."),
    "judging": ("Судья оценивает...", "Judge is scoring..."),
    "init": ("Инициализация...", "Initializing..."),
    "cancelled": ("Остановлено", "Stopped"),
    "cancelled_user": ("Прогон остановлен пользователем", "Run stopped by user"),
    "no_models": ("Нет конфигураций моделей", "No model configurations"),
    "ab_a": ("Запускаем Промпт A...", "Running Prompt A..."),
    "ab_b": ("Запускаем Промпт B...", "Running Prompt B..."),
    "at_base": ("Базовый прогон...", "Base run..."),
    "at_fixes": ("Собираем рекомендации судьи...", "Collecting judge recommendations..."),
    "at_synth": ("Синтезируем улучшенный промпт...", "Synthesizing an improved prompt..."),
    "at_ab": ("A/B проверка нового промпта...", "A/B validation of the new prompt..."),
    "at_iter": ("Итерация", "Iteration"),
    "cs_run": ("Прогон", "Run"),
    "cs_phase": ("прогонов", "runs"),
    "stress_query": ("Стресс-диалоги...", "Stress dialogues..."),
    "stress_judge": ("Судья читает стенограммы...", "Judge is reading transcripts..."),
    "run_error": ("Ошибка", "Error"),
    "failed_q": ("вопросов не прошли", "questions failed"),
    "excluded": ("исключено после 5 попыток", "excluded after 5 attempts"),
    "concurrency_reduced": ("Авто-снижение параллелизма до", "Auto-reduced concurrency to"),
    "due_to_errors": ("из-за ошибок", "due to errors"),
}


def S(lang: str, key: str) -> str:
    pair = UI_MSGS.get(key)
    if not pair:
        return key
    return pair[0] if lang == "ru" else pair[1]


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_questions(categories: list = None, limit: int = None, mode: str = None, question_ids: list = None, lang: str = "ru") -> list[dict]:
    return _load_questions(DATA_DIR, categories=categories, limit=limit, mode=mode, question_ids=question_ids, lang=lang)


def load_rubric() -> dict:
    return _load_rubric(DATA_DIR)


def get_all_results() -> list[dict]:
    results = []
    for f in sorted(RESULTS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
            results.append({
                "filename": f.name,
                "model_name": data["meta"]["model_name"],
                "overall_score": data["summary"]["overall_score"],
                "total_questions": data["meta"]["total_questions"],
                "answered": data["meta"]["answered"],
                "run_at": data["meta"]["run_at"],
                "category_scores": data["summary"]["category_scores"],
                "criteria_scores": data["summary"]["criteria_scores"],
                "coverage": data["meta"].get("coverage", data["meta"].get("answered", 0)),
                "skipped": data["meta"].get("skipped", []),
                "mode": data["meta"].get("mode", "full"),
                "lang": data["meta"].get("lang", "ru"),
            })
        except Exception:
            pass
    return results


def build_run_data(config: dict, responses: list, scores: list, questions: list, mode: str = "full", lang: str = "ru") -> dict:
    q_map = {q["id"]: q for q in questions}
    r_map = {r.question_id: r for r in responses}
    s_map = {s.question_id: s for s in scores}

    items = []
    skipped_ids = []

    for qid, q in q_map.items():
        r = r_map.get(qid)
        s = s_map.get(qid)
        is_skipped = r and r.error and r.attempts >= 5
        if is_skipped:
            skipped_ids.append(qid)
        items.append({
            "id": qid,
            "category": q["category"],
            "difficulty": q["difficulty"],
            "prompt": q.get("prompt", ""),
            "response": r.response if r else "",
            "latency_ms": r.latency_ms if r else 0,
            "attempts": r.attempts if r else 1,
            "response_error": r.error if r else "not run",
            "skipped": is_skipped,
            "scores": s.scores if s else {},
            "weighted_total": s.weighted_total if s else 0.0,
            "reasoning": s.reasoning if s else {},
            "analysis": s.analysis if s else "",
            "ideal_answer": s.ideal_answer if s else "",
            "prompt_fix": s.prompt_fix if s else "",
            "judge_error": s.error if s else None,
        })

    valid_items = [i for i in items if not i["judge_error"] and not i["skipped"]]
    all_weighted = [i["weighted_total"] for i in valid_items]
    overall = round(sum(all_weighted) / len(all_weighted), 2) if all_weighted else 0.0

    cat_scores: dict[str, list] = {}
    for item in valid_items:
        cat = item["category"]
        cat_scores.setdefault(cat, [])
        cat_scores[cat].append(item["weighted_total"])

    category_summary = {
        cat: round(sum(vals) / len(vals), 2) if vals else 0.0
        for cat, vals in cat_scores.items()
    }

    criteria_summary = {}
    for criterion in WEIGHTS:
        vals = [i["scores"].get(criterion, 0) for i in valid_items if i["scores"]]
        criteria_summary[criterion] = round(sum(vals) / len(vals), 2) if vals else 0.0

    prompt_fixes = {}
    for item in items:
        if item.get("prompt_fix") and item["category"]:
            cat = item["category"]
            if cat not in prompt_fixes:
                prompt_fixes[cat] = []
            prompt_fixes[cat].append(item["prompt_fix"])

    answered_count = len([r for r in responses if not r.error])
    coverage = len(valid_items)

    return {
        "meta": {
            "model_name": config.get("name", config.get("model", "unknown")),
            "model_id": config.get("model"),
            "base_url": config.get("base_url"),
            "system_prompt": config.get("system_prompt"),
            "run_at": datetime.now().isoformat(),
            "total_questions": len(questions),
            "answered": answered_count,
            "coverage": coverage,
            "skipped": skipped_ids,
            "judge_errors": len([s for s in scores if s.error]),
            "mode": mode,
            "lang": lang,
        },
        "summary": {
            "overall_score": overall,
            "category_scores": category_summary,
            "criteria_scores": criteria_summary,
            "prompt_fixes": prompt_fixes,
        },
        "items": items,
    }


def save_run(run_data: dict) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = run_data["meta"]["model_name"].replace(" ", "_").replace("/", "-")
    mode = run_data["meta"].get("mode", "full")
    suffix = f"_{mode}" if mode != "full" else ""
    result_path = RESULTS_DIR / f"{safe_name}{suffix}_{ts}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(run_data, f, ensure_ascii=False, indent=2)
    report_path = result_path.with_suffix(".html")
    generate_report([run_data], report_path)
    return result_path


async def fire_webhook(url: str, data: dict):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json=data)
    except Exception:
        pass


async def run_single_model(
    ws: WebSocket,
    cfg: dict,
    model_idx: int,
    model_total: int,
    questions: list,
    rubric: dict,
    judge_cfg: dict,
    run_id: str,
    cancel_event: asyncio.Event,
    mode: str = "full",
    lang: str = "ru",
    ui_lang: str = "ru",
):
    total = len(questions)

    async def send(event: str, data: dict):
        try:
            await ws.send_json({"event": event, "run_id": run_id, "model_idx": model_idx, **data})
        except Exception:
            pass

    model_name = cfg.get("name", cfg.get("model", "unknown"))
    await send("model_start", {
        "model_name": model_name,
        "model_idx": model_idx,
        "model_total": model_total,
        "total": total,
    })

    model_config = ModelConfig(
        name=model_name,
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        system_prompt=cfg.get("system_prompt"),
        timeout=cfg.get("timeout", 60),
        concurrency=cfg.get("concurrency", 5),
    )

    client = ModelClient(model_config)
    responses_done = [0]
    responses_collected = []

    def on_concurrency_reduced(new_conc: int):
        asyncio.get_event_loop().create_task(send("concurrency_reduced", {
            "new_concurrency": new_conc,
            "message": f"⚠ {S(ui_lang, 'concurrency_reduced')} {new_conc} {S(ui_lang, 'due_to_errors')}",
        }))

    client.set_concurrency_reduced_cb(on_concurrency_reduced)

    def on_response(r):
        if cancel_event.is_set():
            return
        responses_collected.append(r)
        responses_done[0] += 1
        preview = ""
        if r.response:
            preview = r.response.strip().replace("\n", " ")[:150]
        asyncio.get_event_loop().create_task(send("response", {
            "done": responses_done[0],
            "total": total,
            "question_id": r.question_id,
            "category": r.category,
            "difficulty": r.difficulty,
            "error": r.error,
            "latency_ms": r.latency_ms,
            "attempts": r.attempts,
            "preview": preview,
        }))

    await send("phase", {"phase": "querying", "message": f"[{model_name}] {S(ui_lang, 'querying')}"})

    try:
        responses = await client.run(questions, progress_cb=on_response, max_attempts=5)
    except asyncio.CancelledError:
        await send("cancelled", {"message": f"[{model_name}] {S(ui_lang, 'cancelled')}"})
        return None

    if cancel_event.is_set():
        await send("cancelled", {"message": f"[{model_name}] {S(ui_lang, 'cancelled')}"})
        return None

    failed = [r for r in responses if r.error]
    skipped_ids = [r.question_id for r in responses if r.error and r.attempts >= 5]

    if failed:
        await send("phase", {"phase": "querying", "message": f"[{model_name}] {len(failed)} {S(ui_lang, 'failed_q')} ({len(skipped_ids)} {S(ui_lang, 'excluded')})"})

    await send("phase", {"phase": "judging", "message": f"[{model_name}] {S(ui_lang, 'judging')}"})

    judge_concurrency = judge_cfg.get("concurrency", 3)
    judge = Judge(
        api_key=judge_cfg["api_key"],
        model=judge_cfg["model"],
        base_url=judge_cfg["base_url"],
        concurrency=judge_concurrency,
    )
    scores_done = [0]

    def on_score(s):
        if cancel_event.is_set():
            return
        scores_done[0] += 1
        asyncio.get_event_loop().create_task(send("score", {
            "done": scores_done[0],
            "total": total,
            "question_id": s.question_id,
            "weighted_total": s.weighted_total,
            "error": s.error,
        }))

    try:
        scores = await judge.run(
            responses,
            system_prompt=rubric["judge_system_prompt" + ("_en" if lang == "en" else "")],
            user_template=rubric["judge_user_template" + ("_en" if lang == "en" else "")],
            progress_cb=on_score,
            cancel_event=cancel_event,
        )
    except asyncio.CancelledError:
        await send("cancelled", {"message": f"[{model_name}] {S(ui_lang, 'cancelled')}"})
        return None

    if cancel_event.is_set():
        await send("cancelled", {"message": f"[{model_name}] {S(ui_lang, 'cancelled')}"})
        return None

    run_data = build_run_data(cfg, responses, scores, questions, mode=mode, lang=lang)
    result_path = save_run(run_data)

    prompt_fixes_list = []
    for cat, fixes in run_data["summary"].get("prompt_fixes", {}).items():
        if fixes:
            prompt_fixes_list.append({"category": cat, "fix": fixes[0]})

    await send("model_done", {
        "model_name": model_name,
        "overall_score": run_data["summary"]["overall_score"],
        "category_scores": run_data["summary"]["category_scores"],
        "criteria_scores": run_data["summary"]["criteria_scores"],
        "filename": result_path.name,
        "answered": run_data["meta"]["answered"],
        "coverage": run_data["meta"]["coverage"],
        "skipped": run_data["meta"]["skipped"],
        "total": total,
        "prompt_fixes": prompt_fixes_list[:5],
    })

    return run_data


async def run_benchmark_ws(ws: WebSocket, payload: dict, run_id: str, cancel_event: asyncio.Event):
    async def send(event: str, data: dict):
        try:
            await ws.send_json({"event": event, "run_id": run_id, **data})
        except Exception:
            pass

    models = payload.get("models", [])
    if not models:
        await send("error", {"message": S(payload.get("ui_lang", "ru"), "no_models")})
        return

    judge_cfg = {
        "api_key": payload.get("judge_key", ""),
        "model": payload.get("judge_model", "gpt-4o"),
        "base_url": payload.get("judge_base_url", "https://api.openai.com/v1"),
        "concurrency": int(payload.get("judge_concurrency", 3)),
    }

    mode = payload.get("mode", "full")
    lang = payload.get("lang", "ru")
    ui_lang = payload.get("ui_lang", "ru")
    categories = payload.get("categories") or None
    limit = payload.get("limit") or None
    question_ids = payload.get("question_ids") or None
    questions = load_questions(categories=categories, limit=limit, mode=mode, question_ids=question_ids, lang=lang)
    rubric = load_rubric()
    webhook_url = payload.get("webhook_url") or None

    await send("start", {"total_models": len(models), "total_questions": len(questions), "mode": mode, "lang": lang})

    all_runs = []
    for idx, cfg in enumerate(models):
        if cancel_event.is_set():
            await send("cancelled", {"message": S(ui_lang, "cancelled_user")})
            return
        try:
            run_data = await run_single_model(
                ws, cfg, idx, len(models), questions, rubric, judge_cfg, run_id, cancel_event, mode=mode, lang=lang, ui_lang=ui_lang
            )
            if run_data:
                all_runs.append(run_data)
        except Exception as e:
            await send("error", {"message": f"[{cfg.get('name', 'model')}] {S(ui_lang, 'run_error')}: {str(e)}"})

    if cancel_event.is_set():
        await send("cancelled", {"message": S(ui_lang, "cancelled_user")})
        return

    await send("all_done", {
        "total_models": len(models),
        "filenames": [r["meta"]["model_name"].replace(" ", "_").replace("/", "-") for r in all_runs],
    })

    if webhook_url and all_runs:
        summary_payload = {
            "run_id": run_id,
            "completed_at": datetime.now().isoformat(),
            "models": [
                {
                    "name": r["meta"]["model_name"],
                    "overall_score": r["summary"]["overall_score"],
                    "coverage": f"{r['meta']['coverage']}/{r['meta']['total_questions']}",
                    "category_scores": r["summary"]["category_scores"],
                }
                for r in all_runs
            ],
        }
        asyncio.create_task(fire_webhook(webhook_url, summary_payload))


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = BASE_DIR / "ui" / "index.html"
    with open(html_path, encoding="utf-8") as f:
        return f.read()


@app.get("/api/results")
async def api_results():
    return JSONResponse(get_all_results())


@app.get("/api/results/{filename}")
async def api_result_detail(filename: str):
    path = RESULTS_DIR / filename
    if not path.exists() or not filename.endswith(".json"):
        return JSONResponse({"error": "not found"}, status_code=404)
    with open(path, encoding="utf-8") as f:
        return JSONResponse(json.load(f))


@app.get("/api/results/{filename}/report")
async def api_result_report(filename: str):
    report_name = filename.replace(".json", ".html")
    path = RESULTS_DIR / report_name
    if not path.exists():
        return JSONResponse({"error": "report not found"}, status_code=404)
    with open(path, encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/api/questions/stats")
async def api_questions_stats():
    data = load_yaml(DATA_DIR / "benchmark.yaml")
    questions = data["questions"]
    categories: dict[str, int] = {}
    difficulties: dict[str, int] = {}
    for q in questions:
        categories[q["category"]] = categories.get(q["category"], 0) + 1
        difficulties[q["difficulty"]] = difficulties.get(q["difficulty"], 0) + 1
    return JSONResponse({"total": len(questions), "categories": categories, "difficulties": difficulties})


@app.get("/api/questions/all")
async def api_questions_all():
    data = load_yaml(DATA_DIR / "benchmark.yaml")
    return JSONResponse({"questions": data["questions"]})


@app.delete("/api/results/{filename}")
async def api_delete_result(filename: str):
    if not filename.endswith(".json"):
        return JSONResponse({"error": "invalid"}, status_code=400)
    for ext in [".json", ".html"]:
        p = RESULTS_DIR / filename.replace(".json", ext)
        if p.exists():
            p.unlink()
    return JSONResponse({"ok": True})


@app.post("/api/compare")
async def api_compare(body: dict):
    filenames = body.get("filenames", [])
    runs = []
    for fn in filenames:
        p = RESULTS_DIR / fn
        if p.exists():
            with open(p, encoding="utf-8") as f:
                runs.append(json.load(f))
    if len(runs) < 2:
        return JSONResponse({"error": "need at least 2 runs"}, status_code=400)
    return JSONResponse({"runs": [r["summary"] | {"meta": r["meta"]} for r in runs]})


@app.post("/api/speed-test")
async def api_speed_test(body: dict):
    cfg = body.get("model", {})
    if not cfg.get("api_key") or not cfg.get("model"):
        return JSONResponse({"error": "Нужны api_key и model"}, status_code=400)

    questions = load_questions(limit=5)
    results = []

    for concurrency in [1, 2, 4, 8]:
        model_config = ModelConfig(
            name=cfg.get("name", "test"),
            base_url=cfg.get("base_url", "https://api.openai.com/v1"),
            api_key=cfg["api_key"],
            model=cfg["model"],
            system_prompt=cfg.get("system_prompt"),
            timeout=cfg.get("timeout", 60),
            concurrency=concurrency,
        )
        client = ModelClient(model_config)
        t_start = time.monotonic()
        try:
            responses = await client.run(questions, max_attempts=1)
            elapsed = time.monotonic() - t_start
            answered = len([r for r in responses if not r.error])
            throughput = round(answered / elapsed, 2) if elapsed > 0 else 0
            avg_latency = round(sum(r.latency_ms for r in responses) / len(responses)) if responses else 0
            results.append({
                "concurrency": concurrency,
                "elapsed_s": round(elapsed, 2),
                "throughput_qps": throughput,
                "avg_latency_ms": avg_latency,
                "answered": answered,
            })
        except Exception as e:
            results.append({"concurrency": concurrency, "error": str(e), "throughput_qps": 0})

    best = max(results, key=lambda x: x.get("throughput_qps", 0))
    recommendation = best["concurrency"]

    return JSONResponse({
        "results": results,
        "recommended_concurrency": recommendation,
        "summary": f"Оптимальный параллелизм: {recommendation} потоков ({best.get('throughput_qps', 0)} вопр/сек)",
    })


@app.websocket("/ws/run")
async def ws_run(ws: WebSocket):
    await ws.accept()
    run_id = None
    cancel_event = asyncio.Event()

    async def listen_for_cancel():
        try:
            while True:
                msg = await ws.receive_json()
                if msg.get("type") == "cancel":
                    cancel_event.set()
                    break
        except Exception:
            cancel_event.set()

    try:
        payload = await ws.receive_json()
        run_id = str(uuid.uuid4())[:8]
        _active_runs[run_id] = cancel_event

        cancel_task = asyncio.create_task(listen_for_cancel())

        try:
            await run_benchmark_ws(ws, payload, run_id, cancel_event)
        except Exception as e:
            try:
                await ws.send_json({"event": "error", "run_id": run_id, "message": str(e)})
            except Exception:
                pass
        finally:
            cancel_task.cancel()
            _active_runs.pop(run_id, None)

    except WebSocketDisconnect:
        cancel_event.set()
        if run_id:
            _active_runs.pop(run_id, None)


def compute_ab_delta(run_a: dict, run_b: dict) -> dict:
    score_a = run_a["summary"]["overall_score"]
    score_b = run_b["summary"]["overall_score"]
    delta = round(score_b - score_a, 2)

    cat_delta = {}
    for cat in run_a["summary"]["category_scores"]:
        va = run_a["summary"]["category_scores"].get(cat, 0)
        vb = run_b["summary"]["category_scores"].get(cat, 0)
        cat_delta[cat] = round(vb - va, 2)

    crit_delta = {}
    for crit in run_a["summary"]["criteria_scores"]:
        va = run_a["summary"]["criteria_scores"].get(crit, 0)
        vb = run_b["summary"]["criteria_scores"].get(crit, 0)
        crit_delta[crit] = round(vb - va, 2)

    item_deltas = []
    r_a_map = {i["id"]: i for i in run_a["items"]}
    for item_b in run_b["items"]:
        item_a = r_a_map.get(item_b["id"])
        if item_a:
            d = round(item_b["weighted_total"] - item_a["weighted_total"], 2)
            item_deltas.append({
                "id": item_b["id"],
                "category": item_b["category"],
                "difficulty": item_b["difficulty"],
                "prompt": item_b.get("prompt","")[:100],
                "score_a": item_a["weighted_total"],
                "score_b": item_b["weighted_total"],
                "delta": d,
            })
    item_deltas.sort(key=lambda x: abs(x["delta"]), reverse=True)

    winner = "B" if delta > 0 else ("A" if delta < 0 else "tie")

    return {
        "score_a": score_a,
        "score_b": score_b,
        "delta": delta,
        "winner": winner,
        "cat_delta": cat_delta,
        "crit_delta": crit_delta,
        "item_deltas": item_deltas[:20],
    }


@app.websocket("/ws/ab")
async def ws_ab(ws: WebSocket):
    """Prompt Lab A/B: run same model with two system prompts, stream delta."""
    await ws.accept()
    cancel_event = asyncio.Event()

    async def listen_for_cancel():
        try:
            while True:
                msg = await ws.receive_json()
                if msg.get("type") == "cancel":
                    cancel_event.set()
                    break
        except Exception:
            cancel_event.set()

    async def send(event: str, data: dict):
        try:
            await ws.send_json({"event": event, **data})
        except Exception:
            pass

    try:
        payload = await ws.receive_json()
        cancel_task = asyncio.create_task(listen_for_cancel())

        prompt_a = payload.get("prompt_a", "")
        prompt_b = payload.get("prompt_b", "")
        base_cfg = payload.get("model", {})
        lang = payload.get("lang", "ru")
        ui_lang = payload.get("ui_lang", "ru")
        judge_cfg = {
            "api_key": payload.get("judge_key", ""),
            "model": payload.get("judge_model", "gpt-4o"),
            "base_url": payload.get("judge_base_url", "https://api.openai.com/v1"),
            "concurrency": int(payload.get("judge_concurrency", 3)),
        }
        mode = payload.get("mode", "quick")
        question_ids = payload.get("question_ids") or None
        questions = load_questions(mode=mode, question_ids=question_ids, lang=lang)
        rubric = load_rubric()

        await send("ab_start", {"total": len(questions), "mode": mode, "lang": lang})

        run_id_a = str(uuid.uuid4())[:8]
        run_id_b = str(uuid.uuid4())[:8]

        cfg_a = dict(base_cfg); cfg_a["name"] = "Промпт A" if ui_lang == "ru" else "Prompt A"; cfg_a["system_prompt"] = prompt_a
        cfg_b = dict(base_cfg); cfg_b["name"] = "Промпт B" if ui_lang == "ru" else "Prompt B"; cfg_b["system_prompt"] = prompt_b

        await send("ab_phase", {"phase": "a", "message": S(ui_lang, "ab_a")})
        run_a = await run_single_model(ws, cfg_a, 0, 2, questions, rubric, judge_cfg, run_id_a, cancel_event, mode="ab_a", lang=lang, ui_lang=ui_lang)
        if cancel_event.is_set() or not run_a:
            await send("ab_cancelled", {}); return

        await send("ab_phase", {"phase": "b", "message": S(ui_lang, "ab_b")})
        run_b = await run_single_model(ws, cfg_b, 1, 2, questions, rubric, judge_cfg, run_id_b, cancel_event, mode="ab_b", lang=lang, ui_lang=ui_lang)
        if cancel_event.is_set() or not run_b:
            await send("ab_cancelled", {}); return

        delta_data = compute_ab_delta(run_a, run_b)

        await send("ab_done", {
            **delta_data,
            "filename_a": run_id_a,
            "filename_b": run_id_b,
        })

        cancel_task.cancel()

    except WebSocketDisconnect:
        cancel_event.set()
    except Exception as e:
        try:
            await ws.send_json({"event": "ab_error", "message": str(e)})
        except Exception:
            pass


@app.websocket("/ws/stress")
async def ws_stress(ws: WebSocket):
    """Multi-turn Stress Simulator: scripted provocateur, 3 escalating turns."""
    await ws.accept()
    cancel_event = asyncio.Event()

    async def listen_for_cancel():
        try:
            while True:
                msg = await ws.receive_json()
                if msg.get("type") == "cancel":
                    cancel_event.set()
                    break
        except Exception:
            cancel_event.set()

    async def send(event: str, data: dict):
        try:
            await ws.send_json({"event": event, **data})
        except Exception:
            pass

    try:
        payload = await ws.receive_json()
        cancel_task = asyncio.create_task(listen_for_cancel())

        base_cfg = dict(payload.get("model", {}))
        lang = payload.get("lang", "ru")
        ui_lang = payload.get("ui_lang", "ru")
        judge_cfg = {
            "api_key": payload.get("judge_key", ""),
            "model": payload.get("judge_model", "gpt-4o"),
            "base_url": payload.get("judge_base_url", "https://api.openai.com/v1"),
            "concurrency": int(payload.get("judge_concurrency", 3)),
        }

        questions = load_questions(mode="quick", lang=lang)
        rubric = load_rubric()

        await send("stress_start", {"total": len(questions), "lang": lang})

        model_config = ModelConfig(
            name=base_cfg.get("name", base_cfg.get("model", "unknown")),
            base_url=base_cfg.get("base_url", "https://api.openai.com/v1"),
            api_key=base_cfg.get("api_key", ""),
            model=base_cfg.get("model", ""),
            system_prompt=base_cfg.get("system_prompt"),
            timeout=base_cfg.get("timeout", 90),
            concurrency=base_cfg.get("concurrency", 5),
        )
        client = ModelClient(model_config)

        done_counter = [0]

        def on_progress(r):
            done_counter[0] += 1
            asyncio.get_event_loop().create_task(send("stress_progress", {
                "done": done_counter[0],
                "total": len(questions),
            }))

        await send("phase", {"phase": "querying", "message": S(ui_lang, "stress_query")})
        stress_results = await run_stress(client, questions, lang=lang, progress_cb=on_progress, cancel_event=cancel_event)

        if cancel_event.is_set():
            await send("stress_cancelled", {}); return

        judge = Judge(
            api_key=judge_cfg["api_key"],
            model=judge_cfg["model"],
            base_url=judge_cfg["base_url"],
            concurrency=judge_cfg["concurrency"],
        )
        scoring_done = [0]

        def on_score(s):
            scoring_done[0] += 1
            asyncio.get_event_loop().create_task(send("stress_scoring", {
                "done": scoring_done[0], "total": len(stress_results),
            }))

        scores = await judge.run_transcripts(
            stress_results,
            system_prompt=rubric["stress_judge_system_prompt" + ("_en" if lang == "en" else "")],
            user_template=rubric["stress_judge_user_template" + ("_en" if lang == "en" else "")],
            lang=lang,
            progress_cb=on_score,
            cancel_event=cancel_event,
        )

        if cancel_event.is_set():
            await send("stress_cancelled", {}); return

        run_data = build_stress_run_data(base_cfg, stress_results, scores, questions, mode="stress", lang=lang)
        result_path = save_run(run_data)

        cancel_task.cancel()
        await send("stress_done", {
            "filename": result_path.name,
            "lang": lang,
            "summary": run_data["summary"],
        })

    except WebSocketDisconnect:
        cancel_event.set()
    except Exception as e:
        try:
            await ws.send_json({"event": "stress_error", "message": str(e)})
        except Exception:
            pass


@app.websocket("/ws/consistency")
async def ws_consistency(ws: WebSocket):
    """Consistency Test: run same 5 questions 3 times, report variance."""
    await ws.accept()
    cancel_event = asyncio.Event()

    async def send(event: str, data: dict):
        try:
            await ws.send_json({"event": event, **data})
        except Exception:
            pass

    try:
        payload = await ws.receive_json()
        base_cfg = dict(payload.get("model", {}))
        lang = payload.get("lang", "ru")
        ui_lang = payload.get("ui_lang", "ru")
        judge_cfg = {
            "api_key": payload.get("judge_key", ""),
            "model": payload.get("judge_model", "gpt-4o"),
            "base_url": payload.get("judge_base_url", "https://api.openai.com/v1"),
            "concurrency": int(payload.get("judge_concurrency", 3)),
        }

        questions = load_questions(limit=5, lang=lang)
        rubric = load_rubric()
        runs_data = []

        await send("consistency_start", {"total_runs": 3, "questions": len(questions)})

        for run_idx in range(3):
            if cancel_event.is_set(): break
            await send("consistency_phase", {"run": run_idx + 1, "message": f"{S(ui_lang, 'cs_run')} {run_idx + 1}/3..."})
            cfg = dict(base_cfg); cfg["name"] = f"Run {run_idx+1}"
            run_data = await run_single_model(ws, cfg, run_idx, 3, questions, rubric, judge_cfg,
                                               str(uuid.uuid4())[:8], cancel_event, mode="consistency", lang=lang, ui_lang=ui_lang)
            if run_data:
                runs_data.append(run_data)

        if len(runs_data) < 2:
            await send("consistency_error", {"message": "Not enough runs" if ui_lang == "en" else "Недостаточно прогонов"}); return

        scores = [r["summary"]["overall_score"] for r in runs_data]
        avg = round(sum(scores) / len(scores), 2)
        variance = round(max(scores) - min(scores), 2)
        stability_key = "high" if variance < 0.5 else ("mid" if variance < 1.5 else "low")
        stability = {"high": ("Высокая", "High"), "mid": ("Средняя", "Medium"), "low": ("Низкая", "Low")}[stability_key][0 if ui_lang == "ru" else 1]

        q_scores = {}
        for run in runs_data:
            for item in run["items"]:
                q_scores.setdefault(item["id"], [])
                q_scores[item["id"]].append(item["weighted_total"])

        q_variance = []
        for qid, vals in q_scores.items():
            if len(vals) >= 2:
                q_variance.append({
                    "id": qid,
                    "scores": vals,
                    "avg": round(sum(vals)/len(vals), 2),
                    "variance": round(max(vals) - min(vals), 2),
                })
        q_variance.sort(key=lambda x: x["variance"], reverse=True)

        await send("consistency_done", {
            "runs": len(runs_data),
            "scores": scores,
            "avg": avg,
            "variance": variance,
            "stability": stability,
            "stability_key": stability_key,
            "q_variance": q_variance,
        })

    except WebSocketDisconnect:
        cancel_event.set()
    except Exception as e:
        try:
            await ws.send_json({"event": "consistency_error", "message": str(e)})
        except Exception:
            pass


@app.websocket("/ws/autotune")
async def ws_autotune(ws: WebSocket):
    """Auto-Prompt Optimizer: judge fixes -> synthesize new prompt -> A/B validate -> repeat."""
    await ws.accept()
    cancel_event = asyncio.Event()

    async def listen_for_cancel():
        try:
            while True:
                msg = await ws.receive_json()
                if msg.get("type") == "cancel":
                    cancel_event.set()
                    break
        except Exception:
            cancel_event.set()

    async def send(event: str, data: dict):
        try:
            await ws.send_json({"event": event, **data})
        except Exception:
            pass

    try:
        payload = await ws.receive_json()
        cancel_task = asyncio.create_task(listen_for_cancel())

        base_cfg = dict(payload.get("model", {}))
        prompt_a = payload.get("prompt_a", "")
        use_run = payload.get("use_run") or None
        iterations = max(1, min(3, int(payload.get("iterations", 1))))
        lang = payload.get("lang", "ru")
        ui_lang = payload.get("ui_lang", "ru")
        mode = payload.get("mode", "quick")
        judge_cfg = {
            "api_key": payload.get("judge_key", ""),
            "model": payload.get("judge_model", "gpt-4o"),
            "base_url": payload.get("judge_base_url", "https://api.openai.com/v1"),
            "concurrency": int(payload.get("judge_concurrency", 3)),
        }
        questions = load_questions(mode=mode, lang=lang)
        rubric = load_rubric()

        await send("autotune_start", {"total": len(questions), "iterations": iterations, "lang": lang})

        run_a = None
        fixes = []

        if use_run:
            path = RESULTS_DIR / use_run
            if path.exists() and use_run.endswith(".json"):
                with open(path, encoding="utf-8") as f:
                    run_a = json.load(f)
                await send("autotune_phase", {"message": f"{S(ui_lang, 'at_fixes')} ({use_run})"})
        if run_a:
            fixes = collect_fixes(run_a)
        else:
            await send("autotune_phase", {"message": S(ui_lang, "at_base")})
            cfg_a = dict(base_cfg)
            cfg_a["name"] = base_cfg.get("name", "Auto-Tune base")
            cfg_a["system_prompt"] = prompt_a
            run_a = await run_single_model(
                ws, cfg_a, 0, 2, questions, rubric, judge_cfg,
                str(uuid.uuid4())[:8], cancel_event, mode="autotune_a", lang=lang, ui_lang=ui_lang,
            )
            if cancel_event.is_set() or not run_a:
                await send("autotune_cancelled", {}); return
            fixes = collect_fixes(run_a)

        if not fixes:
            await send("autotune_error", {"message": S(ui_lang, "at_no_fixes") if ui_lang == "en" else "Судья не нашёл рекомендаций — попробуй другой прогон или модель"})
            return
        await send("autotune_fixes", {"count": len(fixes)})

        current_prompt = prompt_a if not use_run else (run_a["meta"].get("system_prompt") or prompt_a)
        base_score = run_a["summary"]["overall_score"]
        history = []
        best_prompt = current_prompt
        best_score = base_score

        for it in range(1, iterations + 1):
            if cancel_event.is_set():
                await send("autotune_cancelled", {}); return

            await send("autotune_phase", {"message": f"{S(ui_lang, 'at_synth')} ({S(ui_lang, 'at_iter')} {it})"})
            synth_prompt, synth_err = await synthesize_prompt(judge_cfg, current_prompt, fixes, lang=lang)
            if synth_err or not synth_prompt:
                await send("autotune_error", {"message": f"Synth error: {synth_err}"})
                return
            await send("autotune_synth", {"preview": synth_prompt[:120].replace(chr(10), ' ')})

            cfg_b = dict(base_cfg)
            cfg_b["name"] = f"Auto-Tune v{it}"
            cfg_b["system_prompt"] = synth_prompt

            await send("autotune_phase", {"message": f"{S(ui_lang, 'at_ab')} ({S(ui_lang, 'at_iter')} {it})"})
            run_b = await run_single_model(
                ws, cfg_b, 1, 2, questions, rubric, judge_cfg,
                str(uuid.uuid4())[:8], cancel_event, mode=f"autotune_b{it}", lang=lang, ui_lang=ui_lang,
            )
            if cancel_event.is_set() or not run_b:
                await send("autotune_cancelled", {}); return

            delta_data = compute_ab_delta(run_a, run_b)
            score_b = delta_data["score_b"]
            history.append({"iter": it, "score": score_b, "delta": delta_data["delta"]})
            await send("autotune_iter", {"iter": it, "score": score_b, "delta": delta_data["delta"]})

            if delta_data["delta"] > 0:
                current_prompt = synth_prompt
                run_a = run_b
                best_prompt = synth_prompt
                best_score = score_b
                fixes = collect_fixes(run_b)
                if not fixes:
                    break
            else:
                break

        cancel_task.cancel()
        await send("autotune_done", {
            "final_prompt": best_prompt,
            "score_a": base_score,
            "score_b": best_score,
            "delta": round(best_score - base_score, 2),
            "iterations_used": len(history),
            "history": history,
        })

    except WebSocketDisconnect:
        cancel_event.set()
    except Exception as e:
        try:
            await ws.send_json({"event": "autotune_error", "message": str(e)})
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=7860, reload=False)
