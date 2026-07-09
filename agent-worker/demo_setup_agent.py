import os
import logging
import json
from livekit.agents.voice import Agent
from livekit.plugins import deepgram
import asyncio

logger = logging.getLogger("demo-setup-agent")

class DemoSetupAgent(Agent):
    """
    Zero-LLM setup agent. Only speaks when explicitly told to by the frontend.
    All state transitions are controlled by the frontend.
    No hallucination risk.
    """
    def __init__(self):
        super().__init__(
            instructions="You are a silent TTS speaker. Only speak what you are told to speak. Never improvise.",
            stt=None,          # NO microphone input
            llm=None,          # NO LLM calls
            tts=deepgram.TTS(model=os.getenv("BOT_VOICE", "aura-2-luna-en")),
        )

    async def on_enter(self) -> None:
        """Fires when the agent connects. Do not speak yet."""
        logger.info("DemoSetupAgent connected. Waiting for frontend commands.")

    async def _handle_speak_command(self, text: str):
        logger.info(f"DemoSetupAgent speaking: {text}")
        await self.session.say(text, allow_interruptions=False)
