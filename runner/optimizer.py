"""Auto-Prompt Optimizer.

Closes the loop: judge recommendations from a run are fed to a synthesizer
model (the judge model itself), which rewrites the system prompt; the new
prompt is then validated in an A/B run. See /ws/autotune in server.py.
"""
from typing import Optional

import httpx

SYNTH_SYSTEM = {
    "ru": (
        "Ты — инженер системных промптов для корпоративных AI-ассистентов. "
        "Тебе дают текущий системный промпт и список конкретных рекомендаций, "
        "которые LLM-судья составил по итогам бенчмарка, где этот промпт работал. "
        "Твоя задача — переписать системный промпт так, чтобы устранить слабые места.\n\n"
        "ПРАВИЛА:\n"
        "- Верни ТОЛЬКО текст нового системного промпта, без пояснений, без markdown-заборов.\n"
        "- Сохрани всё рабочее из текущего промпта: роль, язык ответов, формат.\n"
        "- Встрой рекомендации как чёткие поведенческие инструкции, не механическим списком.\n"
        "- Промпт должен быть самодостаточным: модель видит только его.\n"
        "- Не раздувай: максимум 2 раза длиннее исходного."
    ),
    "en": (
        "You are a system-prompt engineer for corporate AI assistants. "
        "You receive the current system prompt and a list of concrete recommendations "
        "produced by an LLM judge after a benchmark run where this prompt was used. "
        "Rewrite the system prompt to fix the weak spots.\n\n"
        "RULES:\n"
        "- Return ONLY the text of the new system prompt. No explanations, no markdown fences.\n"
        "- Keep everything that works in the current prompt: role, response language, format.\n"
        "- Weave the recommendations in as clear behavioral instructions, not a mechanical list.\n"
        "- The prompt must be self-contained: the model sees only it.\n"
        "- Don't bloat it: at most 2x the original length."
    ),
}

SYNTH_USER = {
    "ru": (
        "ТЕКУЩИЙ СИСТЕМНЫЙ ПРОМПТ:\n---\n{current}\n---\n\n"
        "РЕКОМЕНДАЦИИ СУДЬИ ПО СЛАБЫМ МЕСТАМ:\n{fixes}\n\n"
        "Перепиши системный промпт с учётом рекомендаций. Верни только текст промпта."
    ),
    "en": (
        "CURRENT SYSTEM PROMPT:\n---\n{current}\n---\n\n"
        "JUDGE RECOMMENDATIONS FOR WEAK SPOTS:\n{fixes}\n\n"
        "Rewrite the system prompt with the recommendations in mind. Return only the prompt text."
    ),
}


def strip_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        first_nl = t.find("\n")
        if first_nl != -1:
            t = t[first_nl + 1:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def collect_fixes(run_data: dict, cap: int = 15) -> list:
    """Deduplicated prompt_fix recommendations from a finished run."""
    seen = set()
    fixes = []
    summary_fixes = (run_data.get("summary") or {}).get("prompt_fixes") or {}
    for cat, arr in summary_fixes.items():
        for fix in arr or []:
            key = str(fix).strip().lower()
            if key and key not in seen:
                seen.add(key)
                fixes.append({"category": cat, "fix": str(fix).strip()})
    for item in run_data.get("items") or []:
        fix = (item or {}).get("prompt_fix")
        cat = (item or {}).get("category", "")
        key = str(fix).strip().lower() if fix else ""
        if key and key not in seen:
            seen.add(key)
            fixes.append({"category": cat, "fix": str(fix).strip()})
    return fixes[:cap]


def build_synth_messages(current_prompt: str, fixes: list, lang: str = "ru") -> list:
    fixes_text = "\n".join(
        f"- [{f.get('category', 'general')}] {f['fix']}" for f in fixes
    ) or "- (нет конкретных рекомендаций; усиль промпт по своему усмотрению)"
    user = SYNTH_USER.get(lang, SYNTH_USER["ru"]).format(
        current=current_prompt or "(пусто — промпт не задан, создай с нуля)",
        fixes=fixes_text,
    )
    return [
        {"role": "system", "content": SYNTH_SYSTEM.get(lang, SYNTH_SYSTEM["ru"])},
        {"role": "user", "content": user},
    ]


async def synthesize_prompt(
    judge_cfg: dict,
    current_prompt: str,
    fixes: list,
    lang: str = "ru",
    http_client: Optional[httpx.AsyncClient] = None,
    timeout: int = 120,
) -> tuple[str, Optional[str]]:
    """Ask the judge model to rewrite the system prompt. Returns (new_prompt, error)."""
    messages = build_synth_messages(current_prompt, fixes, lang)
    owned = http_client is None
    client = http_client or httpx.AsyncClient()
    try:
        resp = await client.post(
            f"{judge_cfg['base_url'].rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {judge_cfg['api_key']}",
                "Content-Type": "application/json",
            },
            json={
                "model": judge_cfg["model"],
                "temperature": 0.4,
                "max_tokens": 2048,
                "messages": messages,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
        return strip_fences(raw), None
    except Exception as e:
        return "", str(e)
    finally:
        if owned:
            await client.aclose()
