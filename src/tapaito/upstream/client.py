"""Cliente HTTP compatible con OpenAI hacia el upstream configurado o hacia el mock local."""

from __future__ import annotations

from typing import Any

import httpx

from tapaito.config import settings
from tapaito.upstream.mock import generate_mock_completion


async def call_upstream_chat(
    messages: list[dict[str, Any]],
    model: str | None = None,
    temperature: float | None = 0.0,
    max_tokens: int | None = None,
    hostile_mode: str | None = None,
) -> dict[str, Any]:
    """Envia los mensajes (ya enmascarados) al upstream real o al mock offline."""
    target_model = model or settings.upstream_model
    base_url = settings.upstream_base_url.strip()

    if base_url.lower() in ("mock", "", "local-mock") or hostile_mode is not None:
        return generate_mock_completion(
            messages=messages,
            model=target_model,
            hostile_mode=hostile_mode,
        )

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if settings.upstream_api_key and settings.upstream_api_key != "mock-key":
        headers["Authorization"] = f"Bearer {settings.upstream_api_key}"

    payload: dict[str, Any] = {
        "model": target_model,
        "messages": messages,
        "stream": False,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()
