import os
import logging
import json
import asyncio
from typing import AsyncIterable
from livekit.agents.voice import Agent
from livekit.agents import llm
from livekit.plugins import openai, deepgram, silero
from rag import RAGRetriever
from prompts import get_system_prompt
from tools import GaplytiqAPI

logger = logging.getLogger("gaply-agent")


class GaplyAgent(Agent):
    """
    Gaplytiq Institute chat agent.

    voice_output_enabled controls the TTS pipeline globally:
      - False (default): mic and text both get text-only replies, no Deepgram call.
      - True:            full voice pipeline — TTS + text for every interaction.
    """

    def __init__(self):
        bot_name = os.getenv("BOT_NAME", "Gaply")
        initial_system_prompt = get_system_prompt(bot_name, "No context loaded yet.")

        api = GaplytiqAPI()
        tools = llm.find_function_tools(api)

        super().__init__(
            instructions=initial_system_prompt,
            vad=silero.VAD.load(),
            stt=deepgram.STT(model=os.getenv("BOT_VOICE_STT_MODEL", "nova-3")),
            llm=openai.LLM(model="gpt-4o-mini", temperature=0.0),
            tts=deepgram.TTS(model=os.getenv("BOT_VOICE", "aura-2-luna-en")),
            tools=tools,
        )
        self._retriever = RAGRetriever()
        self._bot_name = bot_name

        # Starts OFF to match the UI default. main.py updates this via the
        # settings data-channel message when the user toggles the switch.
        self._voice_output_enabled: bool = False

        # Callback set by main.py so on_user_turn_completed can publish a
        # text-only streaming reply when voice output is disabled.
        self._text_reply_callback = None

    def set_voice_output(self, enabled: bool) -> None:
        """Toggle TTS output on/off. Called by main.py on every settings message."""
        self._voice_output_enabled = enabled
        logger.info(f"Agent voice output set to: {enabled}")

    # ------------------------------------------------------------------
    # Pipeline node overrides
    # ------------------------------------------------------------------

    async def llm_node(self, *args, **kwargs) -> AsyncIterable[str]:
        """
        When voice output is OFF, skip the pipeline LLM call entirely.
        _text_only_reply already makes its own OpenAI call for text display.
        Skipping here saves tokens AND lets _text_only_reply stream smoothly.
        """
        if not self._voice_output_enabled:
            return  # Yield nothing → tts_node also gets nothing
        async for chunk in Agent.default.llm_node(self, *args, **kwargs):
            yield chunk

    async def tts_node(self, input: AsyncIterable[str], model_settings) -> AsyncIterable[bytes]:
        if not self._voice_output_enabled:
            # Consume LLM text silently — no Deepgram call, no audio frames.
            async for _ in input:
                pass
            return
        # Voice ON: default TTS pipeline (Deepgram).
        async for frame in Agent.default.tts_node(self, input, model_settings):
            yield frame

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------
    async def on_enter(self) -> None:
        """Send the initial greeting when the agent first joins the room."""
        await self.session.say(
            f"Hello! I am {self._bot_name}, your Gaplytiq Institute assistant. "
            "How can I help you today?",
            allow_interruptions=True,
        )

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        # ---- DEBUG: log every time this fires ----
        logger.info(
            f"on_user_turn_completed fired | voice_output={self._voice_output_enabled} "
            f"| content type={type(new_message.content).__name__} "
            f"| content repr={repr(new_message.content)[:120]}"
        )

        # Extract the transcribed user text.
        user_text = ""
        if isinstance(new_message.content, str):
            user_text = new_message.content
        elif isinstance(new_message.content, list):
            for part in new_message.content:
                if hasattr(part, "text"):
                    user_text += part.text
                elif isinstance(part, str):
                    user_text += part

        logger.info(f"on_user_turn_completed extracted user_text={user_text!r}")

        # Always refresh RAG context.
        if user_text:
            logger.info(f"RAG lookup for mic input: {user_text!r}")
            context = await self._retriever.retrieve(user_text)
            updated_prompt = get_system_prompt(self._bot_name, context)
            await self.update_instructions(updated_prompt)

        # If voice output is OFF, publish a text-only reply via data channel.
        # tts_node will drain the LLM output without calling Deepgram.
        if not self._voice_output_enabled and user_text and self._text_reply_callback:
            logger.info("Voice OFF — sending text-only reply for mic input")
            asyncio.ensure_future(self._text_reply_callback(user_text))
