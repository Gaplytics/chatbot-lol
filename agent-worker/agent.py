import os
import logging
import json
import asyncio
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
    Subclasses Agent to hook into the 1.6.4 lifecycle methods
    (on_enter, on_user_turn_completed) instead of the old
    VoicePipelineAgent callback API.
    """

    def __init__(self):
        bot_name = os.getenv("BOT_NAME", "Gaply")
        initial_system_prompt = get_system_prompt(bot_name, "No context loaded yet.")

        # Collect @function_tool methods from GaplytiqAPI instance
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

    async def on_enter(self) -> None:
        """Send the initial greeting when the agent first joins the room."""
        await self.session.say(
            f"Hello! I am {self._bot_name}, your Gaplytiq Institute assistant. How can I help you today?",
            allow_interruptions=True,
        )

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        """
        Called just before the LLM generates a reply.
        Injects RAG context into the system prompt so the model has
        relevant institute information for this specific question.
        """
        user_text = ""
        if isinstance(new_message.content, str):
            user_text = new_message.content
        elif isinstance(new_message.content, list):
            for part in new_message.content:
                if hasattr(part, "text"):
                    user_text += part.text

        if user_text:
            logger.info(f"Retrieving RAG context for: {user_text}")
            context = await self._retriever.retrieve(user_text)

            # Replace the system prompt with the context-enriched version
            updated_prompt = get_system_prompt(self._bot_name, context)
            await self.update_instructions(updated_prompt)
