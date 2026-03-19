from __future__ import annotations

import json
from typing import Any

import aiohttp


class OpenAIResponsesClient:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: int,
    ):
        self.session = session
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def create_json_response(self, prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "input": prompt,
            "text": {"format": {"type": "json_object"}},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with self.session.post(
            f"{self.base_url}/responses",
            headers=headers,
            json=payload,
            timeout=timeout,
        ) as resp:
            body = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"OpenAI API error {resp.status}: {body}")
        data = json.loads(body)

        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return json.loads(output_text)

        for item in data.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    return json.loads(text)

        raise RuntimeError("OpenAI response did not contain JSON text")
