import logging
import os
import json
import asyncio
import uuid
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import cli, WorkerOptions, JobContext
from livekit.agents.voice import AgentSession
import openai as openai_client
from agent import GaplyAgent

# Load environment variables from .env
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gaply-worker")


async def _text_only_reply(text: str, agent: GaplyAgent, room: rtc.Room):
    """
    Handle a typed message when the user has voice response DISABLED.
    Calls the LLM directly (no TTS), then publishes the reply as a
    {type: "text_reply", text: "..."} data packet so the widget shows it.
    The GaplyAgent's RAG context + system prompt are used via update_instructions
    so on_user_turn_completed still fires correctly on the next voice turn.
    """
    try:
        # --- RAG retrieval (same as voice path's on_user_turn_completed) ---
        # Text-only path must fetch knowledge the same way voice does,
        # otherwise the LLM gets "No context loaded yet." and always falls back.
        from prompts import get_system_prompt
        context = await agent._retriever.retrieve(text)
        system_prompt = get_system_prompt(agent._bot_name, context)
        logger.info(f"Text-only RAG retrieved ({len(context)} chars)")

        # Build message history for continuity across typed turns
        messages = [{"role": "system", "content": system_prompt}]
        messages.append({"role": "user", "content": text})

        client = openai_client.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        stream = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.0,
            stream=True,
        )
        
        message_id = str(uuid.uuid4())
        full_reply = ""
        
        async for chunk in stream:
            chunk_text = chunk.choices[0].delta.content
            if chunk_text:
                full_reply += chunk_text
                payload = json.dumps({
                    "type": "text_stream",
                    "id": message_id,
                    "text": chunk_text,
                    "final": False
                }).encode("utf-8")
                await room.local_participant.publish_data(payload, reliable=True)
                
        # Send final marker
        payload = json.dumps({
            "type": "text_stream",
            "id": message_id,
            "text": "",
            "final": True
        }).encode("utf-8")
        await room.local_participant.publish_data(payload, reliable=True)
        
        logger.info(f"Text-only streaming reply sent ({len(full_reply)} chars)")

    except Exception as e:
        logger.error(f"Error in text-only reply: {e}")
        # Send a fallback error message so the UI isn't blank and isProcessing is cleared
        error_id = str(uuid.uuid4())
        try:
            # First chunk with error text
            payload = json.dumps({"type": "text_stream", "id": error_id, "text": "Sorry, I couldn't process that right now.", "final": False}).encode("utf-8")
            await room.local_participant.publish_data(payload, reliable=True)
            # Then final marker to unlock the UI
            payload = json.dumps({"type": "text_stream", "id": error_id, "text": "", "final": True}).encode("utf-8")
            await room.local_participant.publish_data(payload, reliable=True)
        except Exception:
            pass


async def entrypoint(ctx: JobContext):
    """
    LiveKit worker entrypoint. Triggered when a new room is ready for an agent.
    """
    logger.info(f"Connecting to room {ctx.room.name}...")
    await ctx.connect()

    bot_name = os.getenv("BOT_NAME", "Gaply")
    logger.info(f"Starting agent '{bot_name}' in room {ctx.room.name}.")

    session = AgentSession()
    gaply_agent = GaplyAgent()

    # Wire up the text-only reply callback so agent.py can call it for mic input
    # when voice output is OFF (avoids unnecessary Deepgram TTS calls)
    gaply_agent._text_reply_callback = lambda text: _text_only_reply(text, gaply_agent, ctx.room)

    # Per-room setting: matches the UI default (OFF).
    # Updated by the settings data-channel message whenever the user toggles.
    voice_output_enabled = {"value": False}

    # -----------------------------------------------------------------------
    # Handle typed text AND settings updates from the widget's data channel.
    # Payload formats:
    #   {"type": "chat", "text": "...", "voiceResponse": bool}
    #   {"type": "settings", "voiceOutputEnabled": bool}
    # -----------------------------------------------------------------------
    @ctx.room.on("data_received")
    def on_data_received(data_packet: rtc.DataPacket):
        try:
            raw = data_packet.data.decode("utf-8").strip()
            if not raw:
                return

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                # Legacy raw text – treat as voice-response text message
                parsed = {"type": "chat", "text": raw, "voiceResponse": True}

            msg_type = parsed.get("type", "")

            if msg_type == "settings":
                # User toggled "Bot Voice Output" in the UI
                enabled = bool(parsed.get("voiceOutputEnabled", True))
                voice_output_enabled["value"] = enabled
                gaply_agent.set_voice_output(enabled)
                logger.info(f"Voice output set to: {enabled}")
                return

            if msg_type == "chat":
                text = parsed.get("text", "").strip()
                # honour the per-message flag BUT also respect the global toggle
                voice_response = parsed.get("voiceResponse", False) and voice_output_enabled["value"]

                if not text:
                    return

                logger.info(f"Received typed message (voiceOutput={voice_output_enabled['value']}, voiceResponse={voice_response}): {text!r}")

                if voice_response:
                    # Full pipeline: LLM + TTS, transcription shows in widget
                    asyncio.ensure_future(session.generate_reply(user_input=text))
                else:
                    # Text-only: direct LLM call, reply via data channel
                    asyncio.ensure_future(
                        _text_only_reply(text, gaply_agent, ctx.room)
                    )

        except Exception as e:
            logger.error(f"Error in data_received handler: {e}")

    # Start the session — binds to room, fires on_enter (greeting)
    await session.start(gaply_agent, room=ctx.room)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
