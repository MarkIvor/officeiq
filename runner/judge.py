import asyncio
import json
from dataclasses import dataclass, field
from typing import Optional

import httpx


@dataclass
class JudgeScore:
    question_id: str
    scores: dict[str, int]
    weighted_total: float
    reasoning: dict[str, str]
    analysis: str = ""
    ideal_answer: str = ""
    prompt_fix: str = ""
    error: Optional[str] = None


WEIGHTS = {
    "accuracy": 1.2,
    "completeness": 1.1,
    "instruction_following": 1.3,
    "practicality": 1.2,
    "tone_style": 1.0,
    "structure": 0.9,
    "conciseness": 0.9,
    "safety": 1.5,
    "ethical_soundness": 1.3,
    "autonomy": 1.0,
}

WEIGHT_SUM = sum(WEIGHTS.values())


def compute_weighted_total(scores: dict[str, int]) -> float:
    total = sum(scores.get(k, 0) * w for k, w in WEIGHTS.items())
    return round(total / WEIGHT_SUM, 2)


class Judge:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        concurrency: int = 3,
        timeout: int = 90,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._semaphore = asyncio.Semaphore(concurrency)
        self.timeout = timeout

    def _build_user_prompt(self, template: str, response) -> str:
        return template.format(
            category=response.category,
            difficulty=response.difficulty,
            prompt=response.prompt,
            response=response.response if response.response else "[Ответ отсутствует — ошибка запроса]",
        )

    async def _judge_one(
        self,
        client: httpx.AsyncClient,
        response,
        system_prompt: str,
        user_template: str,
        retries: int = 2,
    ) -> JudgeScore:
        if response.error and not response.response:
            return JudgeScore(
                question_id=response.question_id,
                scores={k: 0 for k in WEIGHTS},
                weighted_total=0.0,
                reasoning={
                    "strengths": "",
                    "weaknesses": f"Ответ не получен: {response.error}",
                    "notable": "",
                },
                error=response.error,
            )

        user_content = self._build_user_prompt(user_template, response)
        error = None
        raw = ""

        for attempt in range(retries):
            error = None
            raw = ""
            try:
                async with self._semaphore:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.model,
                            "temperature": 0.0,
                            "max_tokens": 2048,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_content},
                            ],
                        },
                        timeout=self.timeout,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    raw = data["choices"][0]["message"]["content"].strip()
                    break
            except httpx.HTTPStatusError as e:
                error = f"Judge HTTP {e.response.status_code}: {e.response.text[:200]}"
                if e.response.status_code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                break
            except Exception as e:
                error = str(e)
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                break

        if error and not raw:
            return JudgeScore(
                question_id=response.question_id,
                scores={k: 0 for k in WEIGHTS},
                weighted_total=0.0,
                reasoning={"strengths": "", "weaknesses": error, "notable": ""},
                error=error,
            )

        try:
            json_start = raw.find("{")
            json_end = raw.rfind("}") + 1
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")
            parsed = json.loads(raw[json_start:json_end])
            scores = {k: int(v) for k, v in parsed["scores"].items()}
            weighted = compute_weighted_total(scores)
            return JudgeScore(
                question_id=response.question_id,
                scores=scores,
                weighted_total=weighted,
                reasoning=parsed.get("reasoning", {}),
                analysis=parsed.get("analysis", ""),
                ideal_answer=parsed.get("ideal_answer", ""),
                prompt_fix=parsed.get("prompt_fix", ""),
            )
        except Exception as e:
            return JudgeScore(
                question_id=response.question_id,
                scores={k: 0 for k in WEIGHTS},
                weighted_total=0.0,
                reasoning={"strengths": "", "weaknesses": f"JSON parse error: {e}", "notable": raw[:300]},
                error=f"Parse error: {e}",
            )

    async def run(
        self,
        responses: list,
        system_prompt: str,
        user_template: str,
        progress_cb=None,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> list[JudgeScore]:
        async with httpx.AsyncClient() as client:
            tasks = [
                self._judge_one(client, r, system_prompt, user_template)
                for r in responses
            ]
            results = []
            for coro in asyncio.as_completed(tasks):
                if cancel_event and cancel_event.is_set():
                    break
                result = await coro
                results.append(result)
                if progress_cb:
                    progress_cb(result)
            return sorted(results, key=lambda s: s.question_id)
