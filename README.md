# Gaply — Gaplytiq Institute AI Chatbot

An embeddable AI chat widget powered by **LiveKit** (real-time voice), **OpenAI GPT-4o mini** (LLM), **Deepgram** (STT/TTS), and **Qdrant** (knowledge base / RAG).

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [First-Time Setup](#first-time-setup)
4. [Starting the Stack](#starting-the-stack)
5. [Embedding the Widget on a Website](#embedding-the-widget-on-a-website)
6. [Giving the Bot Knowledge](#giving-the-bot-knowledge-rag)
7. [Customising the Bot](#customising-the-bot)
8. [Production Deployment](#production-deployment)
9. [Troubleshooting](#troubleshooting)
10. [Service Reference](#service-reference)

---

## Architecture Overview

```
Browser / Website
    |  embed.iife.js (widget)
    |
    v
Caddy :8080  (single public port — reverse proxy)
    |-- /token*   -> Token API :8000  (FastAPI)
    |-- /admin*   -> Token API :8000
    `-- /*        -> Chat Widget Nginx :80

LiveKit Server :7989  (WebSocket signal + WebRTC)
    |
    `-- Agent Worker (Python)
           |-- Deepgram STT  (speech -> text)
           |-- OpenAI GPT-4o mini  (LLM)
           |-- Deepgram TTS  (text -> speech)
           `-- Qdrant RAG  (knowledge retrieval)

Redis :6380   (LiveKit internal)
Qdrant :6334  (vector database — knowledge base)
```

**One public port (8080).** Everything else is internal Docker networking.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Docker Desktop >= 4.x | Must be running |
| Docker Compose >= 2.x | Included in Docker Desktop |
| OpenAI API key | [platform.openai.com](https://platform.openai.com) |
| Deepgram API key | [console.deepgram.com](https://console.deepgram.com) |

---

## First-Time Setup

### 1. Navigate to the project

```bash
cd "d:\INTERNSHIP\Gapltiq Institutes\gaply-chatbot"
```

### 2. Create your `.env` file

```bash
copy .env.example .env
```

Open `.env` and fill in the **required** fields:

```env
# REQUIRED — your API keys
OPENAI_API_KEY=sk-...
DEEPGRAM_API_KEY=...

# LiveKit — leave as-is for local dev
LIVEKIT_URL=ws://localhost:7989
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=devsecret

# CORS — comma-separated list of origins allowed to load the widget
WIDGET_CORS_ORIGINS=http://localhost:3000,https://yourdomain.com

# Bot identity
BOT_NAME=Gaply
BOT_VOICE=aura-2-luna-en
BOT_VOICE_STT_MODEL=nova-3
```

> Leave `QDRANT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` unchanged for local development.

---

## Starting the Stack

### Start everything

```bash
docker-compose up -d
```

First run downloads images (~2-3 min). Subsequent starts take ~10 seconds.

### Check status

```bash
docker-compose ps
```

All 7 services should show `Up`:

```
NAME                          STATUS
gaply-chatbot-caddy-1         Up
gaply-chatbot-livekit-1       Up
gaply-chatbot-agent-worker-1  Up
gaply-chatbot-token-api-1     Up
gaply-chatbot-chat-widget-1   Up
gaply-chatbot-qdrant-1        Up
gaply-chatbot-redis-1         Up
```

### Verify it's working

Open **http://localhost:8080** — should return 200 (the widget JS file).

### Stop everything

```bash
docker-compose down
```

### Rebuild after code changes

```bash
# Rebuild one service (fastest)
docker-compose up -d --build agent-worker

# Rebuild widget + agent
docker-compose up -d --build agent-worker chat-widget

# Rebuild everything
docker-compose up -d --build
```

### View logs

```bash
docker-compose logs -f                              # all services
docker logs gaply-chatbot-agent-worker-1 -f         # agent only
docker logs gaply-chatbot-token-api-1 -f            # token API only
```

---

## Embedding the Widget on a Website

Add **two lines** anywhere in your HTML:

```html
<link rel="stylesheet" href="http://localhost:8080/style.css">
<script src="http://localhost:8080/embed.iife.js"></script>
<script>
  GaplyWidget.init({
    tokenUrl: "http://localhost:8080/token",
    botName: "Gaply",
    primaryColor: "#6C63FF",   // optional: brand colour
    theme: "light"             // optional: "light" or "dark"
  });
</script>
```

### For production (replace with your domain):

```html
<link rel="stylesheet" href="https://chat.yourdomain.com/style.css">
<script src="https://chat.yourdomain.com/embed.iife.js"></script>
<script>
  GaplyWidget.init({
    tokenUrl: "https://chat.yourdomain.com/token",
    botName: "Gaply",
    primaryColor: "#6C63FF"
  });
</script>
```

### Allowing your website domain (CORS)

In `.env`:

```env
WIDGET_CORS_ORIGINS=https://institute.gaplytiq.com,https://yourwebsite.com
```

Then restart:

```bash
docker-compose up -d token-api
```

### Widget UI Controls

| Control | What it does |
|---|---|
| Chat bubble (bottom-right) | Opens/closes the chat panel |
| Type + **Send** / Enter | Sends a text message |
| **🔇 / 🔊 toggle** | Voice response toggle — **🔇 = text-only reply** (default), **🔊 = bot also speaks** via TTS |
| **🎤 Mic button** | Toggles your microphone for voice input (bot always speaks back) |

> **Smart Voice Toggling**: When the Bot Voice Output is set to 🔇 OFF, the backend skips the entire voice generation pipeline (Deepgram TTS and voice LLM), falling back to a text-only stream. This dramatically saves OpenAI and Deepgram token costs and removes audio latency.

> **Shared Memory**: The bot maintains a unified conversation history across both typing and voice interactions. You can seamlessly switch between speaking and typing without the bot losing context.

> **Inline RAG Suggestions**: After every reply, the bot generates 3 context-aware, clickable follow-up questions. These suggestions are **RAG-grounded** — they are strictly generated based on what the Knowledge Base actually knows about the current topic, preventing hallucination.

---

## Giving the Bot Knowledge (RAG)

The bot searches a vector database (Qdrant) before answering. Without knowledge loaded it says *"I don't have that information right now."*

### Adding Knowledge Manually

1. Place your knowledge files (Markdown format) in the `agent-worker/knowledge/` directory. For example, edit the existing `faq.md`.
2. Run the ingestion script inside the agent container to embed and upload the files to Qdrant:

```bash
docker exec -it gaply-chatbot-agent-worker-1 python ingest.py
```

This reads the markdown files, chunks the content, embeds it with OpenAI `text-embedding-3-small`, and stores it in Qdrant.

> **Reminder:** Every time you add/edit content in `agent-worker/knowledge/faq.md`, you MUST re-run `docker exec gaply-chatbot-agent-worker-1 python ingest.py` to update the knowledge base.

*(Note: The `/admin/scrape` and `/admin/ingest` REST endpoints in the Token API are currently placeholder stubs for future Redis PubSub architecture. Use the `docker exec` method above for now.)*

---

## Customising the Bot

### Name and voice

In `.env`:

```env
BOT_NAME=Gaply
BOT_VOICE=aura-2-luna-en       # Deepgram TTS voice
BOT_VOICE_STT_MODEL=nova-3     # Deepgram STT model
```

Available voices: `aura-2-luna-en`, `aura-2-orion-en`, `aura-2-stella-en`, `aura-2-zeus-en`
Full list: [Deepgram TTS Models](https://developers.deepgram.com/docs/tts-models)

### Personality and rules

Edit `agent-worker/prompts.py` — the `SYSTEM_PROMPT_TEMPLATE` string:

- **Rule 2** — fallback message when no knowledge is found
- **Rule 6/7** — voice vs text formatting style
- **Rule 8** — suggestion chips behaviour

Rebuild after editing:

```bash
docker-compose up -d --build agent-worker
```

### LLM model

In `agent-worker/agent.py`:

```python
llm=openai.LLM(model="gpt-4o-mini", temperature=0.0),
```

Switch to `gpt-4o` for higher quality. `temperature=0.0` = fully factual, `0.7` = more creative.

### Widget primary colour

```js
GaplyWidget.init({
  tokenUrl: "...",
  primaryColor: "#FF6B6B"    // any hex colour
});
```

---

## Production Deployment

### 1. DNS

Add an `A` record: `chat.yourdomain.com` → your server's public IP.

### 2. Update Caddyfile for HTTPS

Replace `:8080 {` with your domain (Caddy auto-provisions free SSL via Let's Encrypt):

```
chat.yourdomain.com {
    handle /token* {
        reverse_proxy token-api:8000
    }
    handle /admin* {
        reverse_proxy token-api:8000
    }
    handle * {
        reverse_proxy chat-widget:80
    }
}
```

### 3. Update `.env`

```env
LIVEKIT_URL=wss://chat.yourdomain.com/rtc
WIDGET_CORS_ORIGINS=https://institute.gaplytiq.com
```

### 4. Expose WebRTC UDP ports (in docker-compose.yml)

```yaml
livekit:
  ports:
    - "7989:7989"
    - "62000-62020:62000-62020/udp"
```

### 5. Deploy

```bash
docker-compose up -d
```

---

## Troubleshooting

### Widget won't connect / stuck connecting

```bash
# Is token API healthy?
curl http://localhost:8080/health

# Has the agent registered?
docker logs gaply-chatbot-agent-worker-1 | findstr "registered worker"
```

### Bot connects but doesn't respond to messages

```bash
docker logs gaply-chatbot-agent-worker-1 --tail 50
```

Common causes:
- `OPENAI_API_KEY` missing or invalid
- `DEEPGRAM_API_KEY` missing or invalid

### Voice / mic doesn't work

- Grant microphone permission in the browser
- Mic requires `localhost` or `https://` (browsers block mic on plain `http://`)

### Bot says "I don't have that information" for everything

Knowledge base is empty. Load it:

```bash
curl -X POST http://localhost:8080/admin/scrape
```

Verify Qdrant has data:

```bash
curl http://localhost:6334/collections/gaply_knowledge
```

### CORS error in browser console

Add your site to `WIDGET_CORS_ORIGINS` and restart:

```bash
docker-compose up -d token-api
```

---

## Service Reference

| Service | Public Port | Purpose |
|---|---|---|
| `caddy` | **8080** | Single public entry point (reverse proxy) |
| `token-api` | internal :8000 | Issues LiveKit JWT tokens to the widget |
| `agent-worker` | — | AI brain: STT + LLM + TTS |
| `chat-widget` | internal :80 | Serves `embed.iife.js` |
| `livekit` | internal :7989 | WebRTC signalling |
| `qdrant` | internal :6333 | Vector DB for RAG knowledge |
| `redis` | :6380 (host) | LiveKit pub/sub backend |

### Key files

| File | Purpose |
|---|---|
| `.env` | All secrets and configuration |
| `docker-compose.yml` | Service definitions |
| `Caddyfile` | Reverse proxy routing rules |
| `livekit.yaml` | LiveKit server config |
| `agent-worker/agent.py` | Bot logic, voice pipeline, lifecycle hooks |
| `agent-worker/prompts.py` | System prompt and bot rules |
| `agent-worker/tools.py` | Live data function tools (courses, pricing, etc.) |
| `agent-worker/rag.py` | Knowledge base retrieval |
| `chat-widget/src/` | Widget React/TypeScript source code |
