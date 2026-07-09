"""
pipeline.py – helper utilities for the Gaply agent pipeline.

In livekit-agents 1.6.4 the old VoicePipelineAgent callback hooks
(before_llm_cb, before_tts_cb, agent.on("agent_speech_committed")) no
longer exist.  RAG injection is handled directly inside GaplyAgent via
on_user_turn_completed(), so this file is now a thin utility module.

The suggestion-publishing helper is kept here so agent.py stays clean.
"""
import re
import json
import logging
import asyncio

logger = logging.getLogger("gaply-pipeline")


def parse_suggestions(text: str):
    """
    Strips the [SUGGESTIONS: ...] tag from the text and parses it.
    Returns (clean_text, list_of_suggestions).
    """
    suggestions = []
    clean_text = text

    match = re.search(r'\[SUGGESTIONS:\s*(.*?)\s*\]', text, flags=re.DOTALL)
    if match:
        try:
            suggestions = json.loads(match.group(1))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode suggestions JSON: {e}")

        clean_text = re.sub(r'\[SUGGESTIONS:.*?\]', '', text, flags=re.DOTALL).strip()

    return clean_text, suggestions


async def publish_suggestions(room, suggestions: list):
    """
    Publish a suggestions data message to all participants in the room.
    """
    if not suggestions:
        return
    payload = json.dumps({"type": "suggestions", "data": suggestions}).encode("utf-8")
    try:
        await room.local_participant.publish_data(payload)
    except Exception as e:
        logger.error(f"Failed to publish suggestions: {e}")
