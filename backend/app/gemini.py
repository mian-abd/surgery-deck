"""Gemini integration — event narration, multimodal verification, reporting.

Design rules (a live demo must never die because of this file):

* **Nothing here raises.** Every public function returns ``None``/a fallback on
  any failure (missing key, timeout, quota, bad JSON). Callers treat Gemini as a
  bonus layer on top of the deterministic rule engine, never a dependency.
* **Nothing here blocks the realtime loop.** Safety events are written to the DB
  immediately by the caller; ``enrich_event_bg`` then runs in the background and
  pushes the result to the dashboard over the session WebSocket.
* **One call, two answers.** Narration *and* the multimodal second opinion come
  back from a single request to halve latency and quota use.

Gemini output is stored in ``SafetyEvent.meta["gemini"]`` — ``meta`` is already a
JSON column exposed through ``EventOut``, so this needs no DB migration.
"""
from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

from .config import settings

# --- client -----------------------------------------------------------------
_client: Any = None
_client_tried = False


def _get_client():
    """Lazily build the genai client. Returns None if unavailable."""
    global _client, _client_tried
    if _client is None and not _client_tried:
        _client_tried = True
        if not (settings.gemini_enabled and settings.gemini_api_key):
            print("[gemini] disabled (no GEMINI_API_KEY) — using rule-based text")
            return None
        try:
            from google import genai

            _client = genai.Client(api_key=settings.gemini_api_key)
            print(f"[gemini] enabled — model={settings.gemini_model}")
        except Exception as exc:
            print(f"[gemini] client init failed: {exc}")
            _client = None
    return _client


def available() -> bool:
    return _get_client() is not None


def status() -> dict:
    return {
        "enabled": bool(settings.gemini_enabled and settings.gemini_api_key),
        "model": settings.gemini_model if available() else None,
    }


# --- low-level call ---------------------------------------------------------
async def _call_json(
    prompt: str, schema: dict, image_jpeg: bytes | None = None
) -> dict | None:
    """One structured-JSON generation. Returns None on any failure."""
    client = _get_client()
    if client is None:
        return None
    try:
        from google.genai import types

        parts: list[Any] = []
        if image_jpeg:
            parts.append(types.Part.from_bytes(data=image_jpeg, mime_type="image/jpeg"))
        parts.append(types.Part.from_text(text=prompt))

        resp = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=settings.gemini_model,
                contents=parts,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.2,
                ),
            ),
            timeout=settings.gemini_timeout_sec,
        )
        text = (resp.text or "").strip()
        return json.loads(text) if text else None
    except Exception as exc:
        print(f"[gemini] call failed: {type(exc).__name__}: {exc}")
        return None


# --- prompts ----------------------------------------------------------------
_CLINICAL_FRAME = (
    "You are a perioperative safety assistant reviewing an automated alert from an "
    "operating-room computer-vision monitor. The system is DECISION SUPPORT, not a "
    "diagnostic device: describe only what is observable, never state a clinical "
    "conclusion, and always defer to the human reviewer. Be concise and factual. "
    "Do not invent details that are not in the data or the image."
)

_EVENT_SCHEMA = {
    "type": "object",
    "properties": {
        "explanation": {
            "type": "string",
            "description": "1-2 sentences a circulating nurse could read at a glance.",
        },
        "recommended_action": {
            "type": "string",
            "description": "One concrete next step for the human reviewer.",
        },
        "agrees": {
            "type": "boolean",
            "description": "Does the image support the automated detection?",
        },
        "verification_reason": {
            "type": "string",
            "description": "Briefly, what in the image supports or contradicts it.",
        },
        "visual_confidence": {
            "type": "number",
            "description": "0.0-1.0 confidence that the image supports the detection.",
        },
    },
    "required": [
        "explanation",
        "recommended_action",
        "agrees",
        "verification_reason",
        "visual_confidence",
    ],
}

_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "3-5 sentence narrative safety summary of the procedure.",
        },
        "key_risks": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Up to 3 short bullets naming the main unresolved risks.",
        },
    },
    "required": ["summary", "key_risks"],
}

_ZONES_SCHEMA = {
    "type": "object",
    "properties": {
        "zones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "zone_type": {
                        "type": "string",
                        "description": "One of: sterile, nonsterile, tray, sink, patient, entry",
                    },
                    "name": {"type": "string"},
                    "polygon": {
                        "type": "array",
                        "items": {"type": "array", "items": {"type": "number"}},
                        "description": "4 [x,y] corners, each normalized 0.0-1.0.",
                    },
                    "rationale": {"type": "string"},
                },
                "required": ["zone_type", "name", "polygon"],
            },
        }
    },
    "required": ["zones"],
}


# --- capability 1 + 2: narration and multimodal verification ----------------
async def enrich_event(ctx: dict, image_jpeg: bytes | None = None) -> dict | None:
    """Explain a safety event and (with the frame) sanity-check it visually."""
    prompt = f"""{_CLINICAL_FRAME}

An automated alert fired. Structured detection data:
{json.dumps(ctx, indent=2, default=str)}

{"The attached image is the evidence frame captured at the moment of the alert." if image_jpeg else "No evidence image is available; base your answer on the data alone and set agrees=true with low visual_confidence."}

Write a short explanation for the reviewer and one recommended action. Then, if an
image is attached, judge whether it visually supports the detection (the system
uses geometric zone rules and can produce false positives from occlusion or a bad
camera angle)."""
    return await _call_json(prompt, _EVENT_SCHEMA, image_jpeg)


# --- capability 3: end-of-session summary -----------------------------------
_summary_cache: dict[str, tuple[int, dict]] = {}


async def summarize_session(session_ctx: dict, cache_key: str, event_count: int) -> dict | None:
    """Narrative safety summary for the report. Cached per (session, #events)."""
    cached = _summary_cache.get(cache_key)
    if cached and cached[0] == event_count:
        return cached[1]

    prompt = f"""{_CLINICAL_FRAME}

Here is the complete record of one monitored procedure:
{json.dumps(session_ctx, indent=2, default=str)}

Write the safety summary that belongs at the top of the end-of-session report.
State what happened, what remains unresolved, and what the team should verify
before closing. Use "possible"/"requires review" language — these are flagged
observations awaiting human confirmation, not confirmed clinical findings."""
    out = await _call_json(prompt, _SUMMARY_SCHEMA)
    if out:
        _summary_cache[cache_key] = (event_count, out)
    return out


def invalidate_summary(session_id: str) -> None:
    _summary_cache.pop(session_id, None)


# --- capability 4: zone suggestions -----------------------------------------
async def suggest_zones(image_jpeg: bytes) -> list[dict] | None:
    """Propose OR zone polygons from a frame, for the operator to accept/edit."""
    prompt = f"""{_CLINICAL_FRAME}

The attached image is a frame from an operating-room monitoring camera. Propose
rectangular zones the safety system should watch, choosing zone_type from:
sterile, nonsterile, tray, sink, patient, entry.

Only propose a zone when you can actually see the corresponding surface or
fixture. Give each polygon as 4 [x,y] corners normalized to 0.0-1.0 relative to
the image (origin at top-left). Zones must not overlap. Return an empty list if
the image is too unclear to tell."""
    out = await _call_json(prompt, _ZONES_SCHEMA, image_jpeg)
    if not out:
        return None
    zones = out.get("zones") or []
    # Defensive: keep only well-formed, in-range polygons.
    clean: list[dict] = []
    for z in zones:
        poly = z.get("polygon") or []
        if len(poly) < 3 or not all(
            isinstance(p, (list, tuple)) and len(p) == 2 for p in poly
        ):
            continue
        poly = [[min(1.0, max(0.0, float(p[0]))), min(1.0, max(0.0, float(p[1])))] for p in poly]
        clean.append(
            {
                "zone_type": str(z.get("zone_type", "")).lower(),
                "name": z.get("name") or z.get("zone_type", "zone"),
                "polygon": poly,
                "rationale": z.get("rationale", ""),
            }
        )
    return clean


# --- background scheduling --------------------------------------------------
def _schedule(coro) -> None:
    """Run a coroutine without blocking, from either sync or async callers."""
    try:
        asyncio.get_running_loop().create_task(coro)
    except RuntimeError:  # no loop in this thread (sync caller) — use a thread
        threading.Thread(target=lambda: asyncio.run(coro), daemon=True).start()


async def _enrich_and_publish(event_id: str, session_id: str, ctx: dict,
                              image_jpeg: bytes | None) -> None:
    from .db import SessionLocal
    from .models import SafetyEvent
    from .runtime import hub

    result = await enrich_event(ctx, image_jpeg)
    if not result:
        return

    # Persist into the existing JSON meta column (no migration needed).
    db = SessionLocal()
    try:
        ev = db.get(SafetyEvent, event_id)
        if ev is None:
            return
        meta = dict(ev.meta or {})
        meta["gemini"] = result
        ev.meta = meta
        db.commit()
    except Exception as exc:
        print(f"[gemini] persist failed: {exc}")
        return
    finally:
        db.close()

    invalidate_summary(session_id)
    try:
        await hub.broadcast(
            session_id, {"type": "event_update", "id": event_id, "gemini": result}
        )
    except Exception as exc:
        print(f"[gemini] broadcast failed: {exc}")


def enrich_event_bg(event_id: str, session_id: str, ctx: dict,
                    image_jpeg: bytes | None = None) -> None:
    """Fire-and-forget enrichment. Safe to call from the hot path."""
    if not available():
        return
    _schedule(_enrich_and_publish(event_id, session_id, ctx, image_jpeg))
