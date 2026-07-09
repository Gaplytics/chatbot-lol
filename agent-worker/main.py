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
from prompts import get_system_prompt

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gaply-worker")


# ---------------------------------------------------------------------------
# Suggestion generation — RAG-grounded
# ---------------------------------------------------------------------------
async def _generate_suggestions(last_reply: str, agent: GaplyAgent, room: rtc.Room):
    """
    Generates 3 follow-up question chips that are:
    - Grounded in the actual knowledge base (RAG retrieval first)
    - Relevant to the current conversation topic
    - Not repeating questions the user already asked
    """
    try:
        # ── Step 1: Build a rich query from recent context ──────────────────
        recent_msgs = agent._conversation_history[-4:] if agent._conversation_history else []
        rag_query = " ".join([m["content"][:100] for m in recent_msgs]) + " " + last_reply[:150]

        # ── Step 2: Retrieve what the KB actually knows about this topic ────
        # This is the key step — suggestions will be constrained to this content
        kb_chunks = await agent._retriever.retrieve(rag_query.strip(), top_k=6)

        # ── Step 3: Collect questions user already asked (no repeats) ───────
        asked = [
            f'- "{m["content"][:80]}"'
            for m in agent._conversation_history
            if m["role"] == "user"
        ]
        asked_str = "\n".join(asked[-8:]) if asked else "None"

        # ── Step 4: Recent conversation for context ──────────────────────────
        history_lines = [
            f"{'User' if m['role'] == 'user' else 'Bot'}: {m['content'][:120]}"
            for m in agent._conversation_history[-6:]
        ]
        history_str = "\n".join(history_lines) or "(start of conversation)"

        # ── Step 5: Generate suggestions strictly from KB content ───────────
        prompt = (
            "You generate clickable follow-up question chips for a Gaplytiq Institute chatbot.\n\n"
            "KNOWLEDGE BASE — the ONLY source of truth. The bot can ONLY answer questions covered here:\n"
            f"{kb_chunks}\n\n"
            "RECENT CONVERSATION:\n"
            f"{history_str}\n\n"
            "LAST BOT REPLY:\n"
            f"{last_reply[:300]}\n\n"
            "QUESTIONS THE USER ALREADY ASKED (do NOT suggest these):\n"
            f"{asked_str}\n\n"
            "RULES — follow them strictly:\n"
            "1. Generate EXACTLY 3 questions\n"
            "2. Every question MUST be answerable using the KNOWLEDGE BASE above — if the KB doesn't cover a topic, do NOT suggest it\n"
            "3. Questions must feel natural and relevant to what was just discussed\n"
            "4. Keep each question between 3-8 words\n"
            "5. Do NOT repeat already-asked questions\n"
            "6. Return ONLY a raw JSON array of 3 strings, no markdown, no explanation\n\n"
            'Example output: ["Who configures the tests?", "Can MBA students access coding?", "How long does approval take?"]'
        )

        client = openai_client.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,   # Low temperature = more deterministic, less hallucination
            max_tokens=100,
        )

        raw = response.choices[0].message.content.strip()
        suggestions = json.loads(raw)

        if isinstance(suggestions, list) and suggestions:
            payload = json.dumps({
                "type": "suggestions",
                "data": [str(s) for s in suggestions[:4]]
            }).encode("utf-8")
            await room.local_participant.publish_data(payload, reliable=True)
            logger.info(f"RAG-grounded suggestions sent: {suggestions[:4]}")

    except Exception as e:
        logger.warning(f"Suggestion generation skipped: {e}")



# ---------------------------------------------------------------------------
# Text-only reply (voice output OFF)
# ---------------------------------------------------------------------------
async def _text_only_reply(text: str, agent: GaplyAgent, room: rtc.Room):
    """
    Used when voice output is OFF (both typed and mic input).
    - Reads shared conversation history for memory continuity across modes.
    - Streams the reply via text_stream data packets.
    - Updates shared history with the user + assistant turns.
    - Generates suggestion chips after the reply.
    """
    try:
        # RAG retrieval
        context = await agent._retriever.retrieve(text)
        history_block = agent._build_history_block()
        system_prompt = get_system_prompt(agent._bot_name, context) + history_block
        logger.info(f"Text-only RAG retrieved ({len(context)} chars), history turns={len(agent._conversation_history)}")

        # Build messages with shared conversation history
        messages = [{"role": "system", "content": system_prompt}]
        for msg in agent._conversation_history[-20:]:  # last 10 turns for context
            messages.append({"role": msg["role"], "content": msg["content"]})
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

        # Final marker
        payload = json.dumps({
            "type": "text_stream",
            "id": message_id,
            "text": "",
            "final": True
        }).encode("utf-8")
        await room.local_participant.publish_data(payload, reliable=True)
        logger.info(f"Text-only streaming reply sent ({len(full_reply)} chars)")

        # Update shared history with both turns
        if text:
            agent.add_to_history("user", text)
        if full_reply:
            agent.add_to_history("assistant", full_reply)

        # Generate follow-up suggestions
        if full_reply:
            asyncio.ensure_future(_generate_suggestions(full_reply, agent, room))

    except Exception as e:
        logger.error(f"Error in text-only reply: {e}")
        error_id = str(uuid.uuid4())
        try:
            payload = json.dumps({"type": "text_stream", "id": error_id, "text": "Sorry, I couldn't process that right now.", "final": False}).encode("utf-8")
            await room.local_participant.publish_data(payload, reliable=True)
            payload = json.dumps({"type": "text_stream", "id": error_id, "text": "", "final": True}).encode("utf-8")
            await room.local_participant.publish_data(payload, reliable=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
async def entrypoint(ctx: JobContext):
    logger.info(f"Connecting to room {ctx.room.name}...")
    await ctx.connect()

    bot_name = os.getenv("BOT_NAME", "Gaply")
    logger.info(f"Starting agent '{bot_name}' in room {ctx.room.name}.")

    session = AgentSession()
    gaply_agent = GaplyAgent()

    # Wire callbacks into the agent
    gaply_agent._text_reply_callback = lambda text: _text_only_reply(text, gaply_agent, ctx.room)
    gaply_agent._suggestions_callback = lambda reply: _generate_suggestions(reply, gaply_agent, ctx.room)

    # Per-room voice output state — starts OFF to match UI default
    voice_output_enabled = {"value": False}

    @ctx.room.on("data_received")
    def on_data_received(data_packet: rtc.DataPacket):
        try:
            raw = data_packet.data.decode("utf-8").strip()
            if not raw:
                return

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {"type": "chat", "text": raw, "voiceResponse": True}

            msg_type = parsed.get("type", "")

            if msg_type == "settings":
                enabled = bool(parsed.get("voiceOutputEnabled", True))
                voice_output_enabled["value"] = enabled
                gaply_agent.set_voice_output(enabled)
                logger.info(f"Voice output set to: {enabled}")
                return

            if msg_type == "chat":
                text = parsed.get("text", "").strip()
                voice_response = parsed.get("voiceResponse", False) and voice_output_enabled["value"]

                if not text:
                    return

                logger.info(f"Received typed message (voiceOutput={voice_output_enabled['value']}, voiceResponse={voice_response}): {text!r}")

                if voice_response:
                    # Full pipeline: LLM + TTS
                    asyncio.ensure_future(session.generate_reply(user_input=text))
                else:
                    # Text-only streaming (uses shared history)
                    asyncio.ensure_future(_text_only_reply(text, gaply_agent, ctx.room))

        except Exception as e:
            logger.error(f"Error in data_received handler: {e}")

    await session.start(gaply_agent, room=ctx.room)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
