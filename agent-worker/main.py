import logging
import os
import json
import asyncio
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import cli, WorkerOptions, JobContext
from livekit.agents.voice import AgentSession
import openai as openai_client
from agent import GaplyAgent
from demo_setup_agent import DemoSetupAgent

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
        tenant_name = "Gaplytiq Labs" if agent._tenant_id == "labs" else "Gaplytiq Enterprise" if agent._tenant_id == "enterprise" else "Gaplytiq Institute"
        prompt = (
            f"You generate clickable follow-up suggestion chips for a {tenant_name} chatbot.\n\n"
            "KNOWLEDGE BASE — the ONLY source of truth:\n"
            f"{kb_chunks}\n\n"
            "CURRENT PAGE CONTEXT:\n"
            f"The user is currently on this page: '{agent._current_page_title}' (URL: {agent._current_url})\n\n"
            "RECENT CONVERSATION:\n"
            f"{history_str}\n\n"
            "LAST BOT REPLY:\n"
            f"{last_reply[:300]}\n\n"
            "QUESTIONS THE USER ALREADY ASKED (do NOT suggest these):\n"
            f"{asked_str}\n\n"
            "RULES — follow them strictly:\n"
            "1. Generate EXACTLY 3 short phrases (3-8 words each).\n"
            "2. If the LAST BOT REPLY asks a direct question, your suggestions MUST be natural ANSWERS to that question.\n"
            "3. If this is the start of the conversation (no recent conversation), generate 3 suggestions of actions the user can take SPECIFICALLY on the CURRENT PAGE.\n"
            "4. Otherwise, generate relevant follow-up QUESTIONS the user might want to ask next based on the KNOWLEDGE BASE.\n"
            "5. Keep them conversational and highly relevant to what was just discussed or their current page.\n"
            "6. Return ONLY a raw JSON array of 3 strings, no markdown, no explanation.\n\n"
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
# Entrypoint
# ---------------------------------------------------------------------------
async def entrypoint(ctx: JobContext):
    logger.info(f"Connecting to room {ctx.room.name}...")
    await ctx.connect()

    bot_name = os.getenv("BOT_NAME", "Gaply")
    logger.info(f"Starting agent '{bot_name}' in room {ctx.room.name}.")

    tenant_id = "CRITICAL_ERROR_NO_TENANT_ID" # Loud error fallback
    # Find the user participant and extract the tenant_id from their secure token metadata
    for p in ctx.room.remote_participants.values():
        if p.metadata:
            try:
                meta = json.loads(p.metadata)
                if "tenant_id" in meta:
                    raw_tenant = meta["tenant_id"].lower()
                    
                    # Normalize tenant ID if it's a URL to prevent filename errors
                    if "labs.gaplytiq.com" in raw_tenant or raw_tenant == "labs":
                        tenant_id = "labs"
                    elif "institute" in raw_tenant:
                        tenant_id = "institutes"
                    elif "enterprise" in raw_tenant:
                        tenant_id = "enterprise"
                    else:
                        tenant_id = raw_tenant
                        
                    break
            except Exception:
                pass

    logger.info(f"Detected Tenant ID: {tenant_id}")

    session = AgentSession()
    
    # ── ROUTING: Setup Agent vs Chatbot Agent ──
    if ctx.room.name.startswith("demo-setup-"):
        logger.info("Routing to DemoSetupAgent for setup flow.")
        agent = DemoSetupAgent()
        
        @ctx.room.on("data_received")
        def on_data_received(data_packet: rtc.DataPacket):
            try:
                raw = data_packet.data.decode("utf-8").strip()
                if not raw: return
                parsed = json.loads(raw)
                msg_type = parsed.get("type", "")
                
                if msg_type == "speak_command":
                    text = parsed.get("text", "")
                    if text:
                        asyncio.ensure_future(agent._handle_speak_command(text))
            except Exception as e:
                logger.error(f"Error in DemoSetupAgent data handler: {e}")
                
        await session.start(agent, room=ctx.room)
        return
        
    # ── STANDARD CHATBOT ──
    gaply_agent = GaplyAgent(tenant_id=tenant_id)

    # Wire suggestions callback into the agent.
    # NOTE: there is no more _text_reply_callback — every chat message (typed
    # or spoken) now flows through session.generate_reply() -> GaplyAgent's
    # unified llm_node, so tools and text streaming behave identically
    # whether Voice Output is ON or OFF. Voice Output only gates tts_node.
    gaply_agent._suggestions_callback = lambda reply: _generate_suggestions(reply, gaply_agent, ctx.room)

    async def _safe_generate_reply(text: str):
        """
        Wraps session.generate_reply so exceptions are actually logged.
        asyncio.ensure_future() on its own swallows exceptions until GC —
        this makes failures visible immediately in the logs.
        """
        try:
            await session.generate_reply(user_input=text)
        except Exception:
            logger.exception(f"generate_reply failed for input: {text!r}")

    @ctx.room.on("data_received")
    def on_data_received(data_packet: rtc.DataPacket):
        try:
            raw = data_packet.data.decode("utf-8").strip()
            if not raw:
                return

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {"type": "chat", "text": raw}

            msg_type = parsed.get("type", "")

            if msg_type == "settings":
                enabled = bool(parsed.get("voiceOutputEnabled", True))
                gaply_agent.set_voice_output(enabled)
                logger.info(f"Voice output set to: {enabled}")
                return

            if msg_type == "page_context":
                url = parsed.get("current_url", "")
                title = parsed.get("page_title", "")
                gaply_agent._current_url = url
                gaply_agent._current_page_title = title
                logger.info(f"Page context updated: {title} — {url}")
                return

            if msg_type == "chat":
                text = parsed.get("text", "").strip()
                if not text:
                    return

                logger.info(f"Received typed message: {text!r}")

                # Single unified pipeline for typed AND spoken input.
                # GaplyAgent.llm_node always runs (tools always available)
                # and streams text_stream packets; tts_node internally
                # decides whether to actually speak, based on
                # gaply_agent._voice_output_enabled. No duplicate LLM call,
                # no wasted tokens.
                asyncio.ensure_future(_safe_generate_reply(text))

        except Exception as e:
            logger.error(f"Error in data_received handler: {e}")

    await session.start(gaply_agent, room=ctx.room)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))