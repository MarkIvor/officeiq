import asyncio
import time
from dataclasses import dataclass
from typing import Optional, Callable

import httpx


@dataclass
class ModelConfig:
    name: str
    base_url: str
    api_key: str
    model: str
    system_prompt: Optional[str] = None
    timeout: int = 60
    concurrency: int = 5
    limit: Optional[int] = None
    categories: Optional[list] = None


@dataclass
class ModelResponse:
    question_id: str
    category: str
    difficulty: str
    prompt: str
    response: str
    latency_ms: int
    error: Optional[str] = None
    attempts: int = 1


class ModelClient:
    def __init__(self, config: ModelConfig):
        self.config = config
        self._semaphore = asyncio.Semaphore(config.concurrency)
        self._current_concurrency = config.concurrency
        self._recent_errors: list[bool] = []
        self._concurrency_reduced_cb: Optional[Callable] = None

    def set_concurrency_reduced_cb(self, cb: Callable):
        self._concurrency_reduced_cb = cb

    def _record_result(self, is_error: bool):
        self._recent_errors.append(is_error)
        if len(self._recent_errors) > 10:
            self._recent_errors.pop(0)

    def _should_reduce_concurrency(self) -> bool:
        if len(self._recent_errors) < 5:
            return False
        error_rate = sum(self._recent_errors) / len(self._recent_errors)
        return error_rate >= 0.4 and self._current_concurrency > 1

    async def _reduce_concurrency(self):
        new_conc = max(1, self._current_concurrency // 2)
        if new_conc < self._current_concurrency:
            self._current_concurrency = new_conc
            self._semaphore = asyncio.Semaphore(new_conc)
            self._recent_errors.clear()
            if self._concurrency_reduced_cb:
                self._concurrency_reduced_cb(new_conc)

    async def _call_once(
        self,
        client: httpx.AsyncClient,
        question: dict,
        timeout: int,
    ) -> tuple[str, Optional[str]]:
        messages = []
        if self.config.system_prompt:
            messages.append({"role": "system", "content": self.config.system_prompt})
        messages.append({"role": "user", "content": question["prompt"]})

        async with self._semaphore:
            resp = await client.post(
                f"{self.config.base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.config.model,
                    "messages": messages,
                    "temperature": 0.3,
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"], None

    async def _call(
        self,
        client: httpx.AsyncClient,
        question: dict,
        max_attempts: int = 5,
        base_timeout: Optional[int] = None,
    ) -> ModelResponse:
        if base_timeout is None:
            base_timeout = self.config.timeout

        start = time.monotonic()
        error = None
        response_text = ""
        attempts = 0

        timeouts = [base_timeout, int(base_timeout * 1.5), int(base_timeout * 2), int(base_timeout * 2.5), int(base_timeout * 3)]

        for attempt in range(max_attempts):
            attempts = attempt + 1
            error = None
            response_text = ""
            t = timeouts[min(attempt, len(timeouts) - 1)]

            try:
                response_text, error = await self._call_once(client, question, t)
                if not error:
                    self._record_result(False)
                    break
            except httpx.HTTPStatusError as e:
                error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                self._record_result(True)
                if e.response.status_code in (429, 500, 502, 503, 504):
                    if self._should_reduce_concurrency():
                        await self._reduce_concurrency()
                    backoff = min(2 ** attempt, 30)
                    await asyncio.sleep(backoff)
                    continue
                break
            except httpx.TimeoutException:
                error = f"Timeout after {t}s (attempt {attempt + 1}/{max_attempts})"
                self._record_result(True)
                if self._should_reduce_concurrency():
                    await self._reduce_concurrency()
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2)
                continue
            except Exception as e:
                error = str(e)
                self._record_result(True)
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2)
                continue

        latency_ms = int((time.monotonic() - start) * 1000)

        return ModelResponse(
            question_id=question["id"],
            category=question["category"],
            difficulty=question["difficulty"],
            prompt=question["prompt"],
            response=response_text,
            latency_ms=latency_ms,
            error=error,
            attempts=attempts,
        )

    async def run(
        self,
        questions: list[dict],
        progress_cb=None,
        max_attempts: int = 5,
        base_timeout: Optional[int] = None,
    ) -> list[ModelResponse]:
        async with httpx.AsyncClient() as client:
            tasks = [self._call(client, q, max_attempts, base_timeout) for q in questions]
            results = []
            for coro in asyncio.as_completed(tasks):
                result = await coro
                results.append(result)
                if progress_cb:
                    progress_cb(result)
            return sorted(results, key=lambda r: r.question_id)
