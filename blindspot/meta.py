"""Official Meta Chat Completions client, verified against docs on 2026-10-28.

https://dev.meta.ai/docs/protocols/chat-completions
https://dev.meta.ai/docs/structured-output
"""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import math
import random
import re
import time
import httpx


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class ModelError(Exception):
    def __init__(self, message, raw=None):
        super().__init__(message)
        self.raw = raw


def parse_result(raw, prediction=False):
    """Strict values; tolerate a single Markdown JSON fence, never guess a label."""
    def pairs(values):
        obj = {}
        for key, value in values:
            if key in obj:
                raise ValueError("Duplicate JSON key")
            obj[key] = value
        return obj
    if not isinstance(raw, str):
        raise ValueError("Response content is not text")
    cleaned = raw.strip()
    fence = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if fence:
        cleaned = fence.group(1)
    obj = json.loads(cleaned, object_pairs_hook=pairs)
    expected = {"probability_percent", "reason"} if prediction else {"valid", "confidence", "reason"}
    if not isinstance(obj, dict) or set(obj) != expected:
        raise ValueError("Missing or unexpected response fields")
    key, maximum = ("probability_percent", 100) if prediction else ("confidence", 1)
    value = obj[key]
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
        raise ValueError(f"{key} outside allowed numeric range")
    if not prediction and type(obj["valid"]) is not bool:
        raise ValueError("valid must be a JSON boolean")
    if not isinstance(obj["reason"], str) or not obj["reason"].strip() or len(obj["reason"]) > 4000:
        raise ValueError("Missing or excessive reason text")
    return obj


def response_schema(prediction):
    fields = ({"probability_percent": {"type": "number", "minimum": 0, "maximum": 100}}
              if prediction else {"valid": {"type": "boolean"}, "confidence": {"type": "number", "minimum": 0, "maximum": 1}})
    fields["reason"] = {"type": "string"}
    return {"type": "json_schema", "json_schema": {
        "name": "self_prediction" if prediction else "step_verdict",
        "schema": {"type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}}}


def build_request(settings, messages, prediction, temperature):
    return dict(model=settings.model, messages=messages, temperature=temperature,
                reasoning_effort=settings.reasoning_effort,
                max_completion_tokens=settings.max_completion_tokens, n=1, stream=False,
                response_format=response_schema(prediction))


class MetaClient:
    def __init__(self, settings, transport=None):
        self.settings = settings
        self.http = None if settings.mode == "mock" else httpx.AsyncClient(timeout=settings.timeout, transport=transport)

    async def close(self):
        if self.http:
            await self.http.aclose()

    async def complete(self, request, *, cell=None, ordinal=0, fast=False):
        started, timer = utcnow(), time.monotonic()
        if self.settings.mode == "mock":
            result = await self.mock(request, cell, ordinal, fast)
            return dict(**result, started_at=started, completed_at=utcnow(), latency_ms=round((time.monotonic()-timer)*1000),
                        returned_model="mock-simulator-v1", usage=None, raw_response=json.dumps(result), http_attempts=0)
        attempts = 0
        while True:
            attempts += 1
            try:
                response = await self.http.post(self.settings.base_url.rstrip("/") + "/chat/completions", json=request,
                                                headers={"Authorization": f"Bearer {self.settings.api_key}", "Content-Type": "application/json"})
            except httpx.HTTPError as exc:
                # Ambiguous transport failures may already have consumed credits. Do not silently repeat.
                raise ModelError(f"Meta transport error ({type(exc).__name__}); the provider may have billed this request. Inspect the saved attempt before retrying. Budgeted studies retain its reservation and do not resend it automatically.") from exc
            if response.status_code in {429, 500, 502, 503, 504} and attempts <= self.settings.retries:
                try:
                    delay = min(30, max(0, float(response.headers.get("Retry-After", 2**attempts))))
                except ValueError:
                    delay = 2**attempts
                await asyncio.sleep(delay + random.random()/2)
                continue
            if response.is_error:
                hint = "Check META_API_KEY and access to the configured model." if response.status_code in {401, 403} else "Inspect the endpoint, model, request settings or rate limit."
                raise ModelError(f"Meta HTTP {response.status_code}. {hint}")
            break
        try:
            body = response.json()
            choice = body["choices"][0]
            if choice.get("finish_reason") != "stop" or choice["message"].get("refusal"):
                raise ValueError("Response was incomplete or refused")
            result = parse_result(choice["message"]["content"], prediction=request["response_format"]["json_schema"]["name"] == "self_prediction")
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ModelError(f"Unusable model response: {exc}", raw=response.text) from exc
        return dict(**result, started_at=started, completed_at=utcnow(), latency_ms=round((time.monotonic()-timer)*1000),
                    returned_model=body.get("model"), usage=body.get("usage"), provider_response_id=body.get("id"),
                    raw_response=response.text, http_attempts=attempts)

    async def mock(self, request, cell, ordinal, fast):
        if not fast:
            await asyncio.sleep(0.07)
        h = int(hashlib.sha256(cell["id"].encode()).hexdigest()[:8], 16)
        prediction = request["response_format"]["json_schema"]["name"] == "self_prediction"
        showcase = cell["id"] == "gaussian:4:sign"
        if prediction:
            probability = (8 + h % 10) if cell["is_control"] else (92 if showcase else 73 + h % 25)
            return dict(probability_percent=probability, reason="SIMULATED forecast for the demo. No Meta model was queried.")
        target = (0.1 if cell["is_control"] else 0.2 if showcase else [0.4, 0.6, 0.8, 1.0][h % 4])
        # Stratified, reproducible fixture. Intentionally not an estimate from an AI.
        reject = ((ordinal + h % 5) % 5)/5 < target
        return dict(valid=not reject, confidence=0.9,
                    reason="SIMULATED verdict: candidate " + ("rejected" if reject else "accepted") + ". Illustrative fixture, not a model explanation.")
