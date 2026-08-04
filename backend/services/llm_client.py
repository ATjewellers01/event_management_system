"""LLM routing: Groq first for text, OpenAI as fallback.

Text-only work (enrichment synthesis, transliteration) runs on Groq's free tier
with `openai/gpt-oss-120b`, which measured as the bulk of the per-scan cost:

    OCR vision        $0.0085   must stay on OpenAI — gpt-oss is text-only
    Enrichment        $0.0216   -> Groq
    Transliteration   $0.0036   -> Groq

Groq's free tier has real rate limits, so every call falls back to OpenAI on any
failure — rate limit, timeout, malformed output. A scan must never fail just
because the free tier was busy.

Two Groq-specific details this handles:
  * Strict `json_schema` requires additionalProperties:false and a full
    `required` list on EVERY object, including nested $defs. Pydantic does not
    emit that, so schemas are rewritten before sending.
  * Groq sits behind Cloudflare, which blocks clients with unusual user agents
    (urllib gets 403 "error code: 1010"). httpx is fine.
"""

import json
import os
from typing import Optional, Type

import httpx
from pydantic import BaseModel

from backend.core.config import logger, async_client

GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Fallback model on OpenAI when Groq is unavailable.
OPENAI_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o")

GROQ_ENABLED = bool(GROQ_API_KEY)
GROQ_TIMEOUT = float(os.getenv("GROQ_TIMEOUT_SECONDS", "60"))

if GROQ_ENABLED:
    logger.info("LLM routing: text -> Groq %s, fallback OpenAI %s", GROQ_MODEL, OPENAI_MODEL)
else:
    logger.info("LLM routing: GROQ_API_KEY unset — all calls go to OpenAI %s", OPENAI_MODEL)


def _strictify(node):
    """Make a JSON schema acceptable to Groq's strict mode, in place."""
    if isinstance(node, dict):
        if node.get("type") == "object" or "properties" in node:
            node["additionalProperties"] = False
            if "properties" in node:
                node["required"] = list(node["properties"].keys())
        for value in node.values():
            _strictify(value)
    elif isinstance(node, list):
        for value in node:
            _strictify(value)
    return node


async def _groq_chat(messages: list, response_model: Optional[Type[BaseModel]] = None) -> str:
    """One Groq call. Raises on any non-200 so the caller can fall back."""
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": 0.0,
    }
    if response_model is not None:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": response_model.__name__,
                "schema": _strictify(response_model.model_json_schema()),
                "strict": True,
            },
        }

    async with httpx.AsyncClient(timeout=GROQ_TIMEOUT) as client:
        resp = await client.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json=payload,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Groq HTTP {resp.status_code}: {resp.text[:200]}")

    body = resp.json()
    usage = body.get("usage") or {}
    logger.info(
        "Groq %s ok (in=%s out=%s)",
        GROQ_MODEL, usage.get("prompt_tokens"), usage.get("completion_tokens"),
    )
    return body["choices"][0]["message"]["content"]


async def structured(messages: list, response_model: Type[BaseModel]) -> BaseModel:
    """Get a schema-validated object, Groq first then OpenAI.

    Groq output is validated here rather than trusted: strict mode is reliable in
    testing but a malformed response should fall back rather than propagate.
    """
    if GROQ_ENABLED:
        try:
            content = await _groq_chat(messages, response_model)
            return response_model.model_validate_json(content)
        except Exception as e:
            logger.warning("Groq structured call failed (%s) — falling back to OpenAI", e)

    completion = await async_client.beta.chat.completions.parse(
        model=OPENAI_MODEL,
        messages=messages,
        response_format=response_model,
        temperature=0.0,
    )
    return completion.choices[0].message.parsed


async def text(messages: list) -> str:
    """Get a plain-text completion, Groq first then OpenAI."""
    if GROQ_ENABLED:
        try:
            out = await _groq_chat(messages)
            if out and out.strip():
                return out.strip()
            logger.warning("Groq returned empty text — falling back to OpenAI")
        except Exception as e:
            logger.warning("Groq text call failed (%s) — falling back to OpenAI", e)

    completion = await async_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.0,
    )
    return (completion.choices[0].message.content or "").strip()


def status() -> dict:
    return {
        "groq_enabled": GROQ_ENABLED,
        "groq_model": GROQ_MODEL if GROQ_ENABLED else None,
        "fallback": f"openai/{OPENAI_MODEL}",
        "vision": "openai/gpt-4o (gpt-oss is text-only)",
    }
