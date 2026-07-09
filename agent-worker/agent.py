import os
import logging
import json
import asyncio
import uuid
from typing import AsyncIterable, Callable, Optional, List, Dict
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

    Shared memory works across voice ON/OFF modes via _conversation_history,
    which is injected into the system prompt on every turn.
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

        # Starts OFF to match the UI default.
        self._voice_output_enabled: bool = False

        # Callbacks wired by main.py
        self._text_reply_callback: Optional[Callable] = None
        self._suggestions_callback: Optional[Callable] = None

        # Shared conversation history — preserved across voice ON/OFF mode switches
        # Format: [{"role": "user"|"assistant", "content": str}, ...]
        self._conversation_history: List[Dict[str, str]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_voice_output(self, enabled: bool) -> None:
        self._voice_output_enabled = enabled
        logger.info(f"Agent voice output set to: {enabled}")

    def add_to_history(self, role: str, content: str) -> None:
        """Append a turn to the shared conversation history (called by main.py)."""
        self._conversation_history.append({"role": role, "content": content})
        # Keep history bounded to last 40 messages (~20 turns)
        if len(self._conversation_history) > 40:
            self._conversation_history = self._conversation_history[-40:]

    def _build_history_block(self) -> str:
        """Return a compact history string for injecting into the system prompt."""
        if not self._conversation_history:
            return ""
        lines = []
        for msg in self._conversation_history[-12:]:  # last 6 turns
            role = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"{role}: {msg['content'][:300]}")
        return "\n\nPrevious conversation (for memory continuity):\n" + "\n".join(lines)

    # ------------------------------------------------------------------
    # Pipeline node overrides
    # ------------------------------------------------------------------

    async def llm_node(self, *args, **kwargs) -> AsyncIterable[str]:
        """
        Voice OFF → skip pipeline LLM call entirely (text_reply_callback handles it).
        Voice ON  → run normal LLM, capture reply for shared history + suggestions.
        """
        if not self._voice_output_enabled:
            return  # Yield nothing → tts_node gets nothing too

        full_reply = ""
        async for chunk in Agent.default.llm_node(self, *args, **kwargs):
            # Extract text from ChatChunk for history; yield the original chunk object
            try:
                if hasattr(chunk, 'choices') and chunk.choices:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, 'content') and delta.content:
                        full_reply += delta.content
            except Exception:
                pass
            yield chunk  # Always yield original ChatChunk — pipeline needs this type

        if full_reply:
            self.add_to_history("assistant", full_reply)
            logger.info(f"Voice LLM reply captured ({len(full_reply)} chars)")
            if self._suggestions_callback:
                asyncio.ensure_future(self._suggestions_callback(full_reply))

    async def tts_node(self, input: AsyncIterable[str], model_settings) -> AsyncIterable[bytes]:
        if not self._voice_output_enabled:
            async for _ in input:
                pass
            return
        async for frame in Agent.default.tts_node(self, input, model_settings):
            yield frame

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    async def on_enter(self) -> None:
        """
        Fires when the bot connects to the room.

        Always sends the greeting as a text bubble (works even when Voice Output is OFF).
        If Voice Output is ON, the bot will also speak the greeting aloud via TTS.

        --- HOW TO DISABLE THE GREETING ---
        To make the bot silent on connect (user starts the conversation first), simply
        comment out or remove everything inside this method and replace it with `pass`:

            async def on_enter(self) -> None:
                pass  # Bot connects silently

        To also control TTS on startup, see INITIAL_VOICE_OUTPUT in main.py (voice_output_enabled).
        """
        # ── 1. Customise the greeting message here ──────────────────────────
        greeting_text = (
            f"Hello! I'm {self._bot_name}, your Gaplytiq Institute assistant. "
            "How can I help you today? 👋"
        )

        # ── 2. Always send greeting as a chat text bubble ────────────────────
        #    Wait briefly so the frontend DataReceived listener is ready before
        #    we publish — without this the packet can arrive before React mounts.
        await asyncio.sleep(1.5)
        room = self.session.room_io.room
        message_id = str(uuid.uuid4())
        payload = json.dumps({
            "type": "text_stream",
            "id": message_id,
            "text": greeting_text,
            "final": False
        }).encode("utf-8")
        await room.local_participant.publish_data(payload, reliable=True)
        # Send final marker so the frontend knows the bubble is complete
        payload = json.dumps({
            "type": "text_stream",
            "id": message_id,
            "text": "",
            "final": True
        }).encode("utf-8")
        await room.local_participant.publish_data(payload, reliable=True)

        # ── 3. Generate follow-up suggestion chips for the greeting ──────────
        if self._suggestions_callback:
            asyncio.ensure_future(self._suggestions_callback(greeting_text))

        # ── 4. Also speak aloud if Voice Output is ON ────────────────────────
        if self._voice_output_enabled:
            await self.session.say(greeting_text, allow_interruptions=True)

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        # Extract transcribed user text from mic input
        user_text = ""
        if isinstance(new_message.content, str):
            user_text = new_message.content
        elif isinstance(new_message.content, list):
            for part in new_message.content:
                if hasattr(part, "text"):
                    user_text += part.text
                elif isinstance(part, str):
                    user_text += part

        logger.info(f"on_user_turn_completed: voice_output={self._voice_output_enabled}, text={user_text!r}")

        # RAG retrieval
        context = "No context loaded yet."
        if user_text:
            context = await self._retriever.retrieve(user_text)

        # Build system prompt + inject shared history for cross-mode memory
        history_block = self._build_history_block()
        updated_prompt = get_system_prompt(self._bot_name, context) + history_block
        await self.update_instructions(updated_prompt)

        if user_text:
            if self._voice_output_enabled:
                # Voice ON: track user turn now; llm_node will track assistant reply
                self.add_to_history("user", user_text)
            else:
                # Voice OFF: text_reply_callback handles both user + assistant history
                if self._text_reply_callback:
                    logger.info("Voice OFF — routing mic input to text-only reply")
                    asyncio.ensure_future(self._text_reply_callback(user_text))
