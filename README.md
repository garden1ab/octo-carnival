# Multi-Agent LLM Orchestration System

A production-ready Python application implementing a **multi-agent LLM orchestration system** using FastAPI, asyncio, and provider-agnostic API clients.

```
User Prompt + Files
        │
        ▼
┌───────────────────┐
│  Controller LLM   │  ← Decomposes task into SubTasks
└────────┬──────────┘
         │  dispatches concurrently
    ┌────┴────┐────────────┐
    ▼         ▼            ▼
┌────────┐ ┌────────┐ ┌────────┐
│Agent 1 │ │Agent 2 │ │Agent N │  ← Each uses any LLM provider
└────────┘ └────────┘ └────────┘
    │         │            │
    └────┬────┘────────────┘
         ▼
┌───────────────────┐
│  Controller LLM   │  ← Synthesises final answer
└───────────────────┘
         │
         ▼
   Final Response
```

---

## Project Structure

```
multi-agent-llm/
├── main.py               # FastAPI server entrypoint
├── controller.py         # Main Controller LLM — decompose, dispatch, synthesise
├── config.py             # Environment-based configuration loader
├── schemas.py            # Pydantic models for inter-agent message passing
├── document_handler.py   # File upload, text extraction, and chunking
├── agents/
│   ├── __init__.py
│   └── worker.py         # WorkerAgent — executes a single SubTask
├── api_clients/
│   ├── __init__.py
│   ├── base.py           # BaseLLMClient ABC with retry logic
│   ├── anthropic_client.py
│   ├── openai_client.py  # Also handles OpenAI-compatible endpoints
│   ├── local_client.py   # Ollama / LM Studio / vLLM
│   └── factory.py        # build_client() factory function
├── uploads/              # Runtime upload storage (auto-created)
├── requirements.txt
├── Dockerfile
└── .env.example
```

---

## Quick Start

### 1. Clone & configure

```bash
git clone <repo-url> && cd multi-agent-llm
cp .env.example .env
# Edit .env — add your API keys and agent definitions
```

### 2. Run locally (Python 3.11+)

```bash
pip install -r requirements.txt
python main.py
# Server starts at http://localhost:8000
```

### 3. API docs

Open **http://localhost:8000/docs** for the interactive Swagger UI.

---

## Docker

### Build the image

```bash
docker build -t multi-agent-llm:latest .
```

### Run the container

Pass API keys and agent config as environment variables:

```bash
docker run -d \
  --name orchestrator \
  -p 8000:8000 \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  -e OPENAI_API_KEY="sk-..." \
  -e CONTROLLER_PROVIDER="anthropic" \
  -e CONTROLLER_MODEL="claude-sonnet-4-20250514" \
  -e AGENT_1_ID="researcher" \
  -e AGENT_1_PROVIDER="anthropic" \
  -e AGENT_1_MODEL="claude-haiku-4-5-20251001" \
  -e AGENT_2_ID="analyst" \
  -e AGENT_2_PROVIDER="openai" \
  -e AGENT_2_MODEL="gpt-4o-mini" \
  multi-agent-llm:latest
```

Or use an env file:

```bash
docker run -d --name orchestrator -p 8000:8000 --env-file .env multi-agent-llm:latest
```

### With Docker Compose

```yaml
# docker-compose.yml
version: "3.9"
services:
  orchestrator:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./uploads:/app/uploads
```

```bash
docker compose up -d
```

---

## API Usage

### Health check

```bash
curl http://localhost:8000/health
```

### Plain text prompt

```bash
curl -X POST http://localhost:8000/orchestrate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Explain the causes and effects of climate change"}'
```

### Prompt with file uploads

```bash
curl -X POST http://localhost:8000/orchestrate/with-files \
  -F "prompt=Summarise and analyse the attached report" \
  -F "files=@./my_report.pdf" \
  -F "files=@./appendix.docx"
```

### Response shape

```json
{
  "session_id": "uuid",
  "status": "completed",
  "final_answer": "...",
  "sub_task_count": 2,
  "agent_responses": [
    {
      "task_id": "uuid",
      "agent_id": "researcher",
      "status": "completed",
      "result": "...",
      "token_usage": {"input": 412, "output": 308},
      "duration_seconds": 3.12
    }
  ],
  "total_duration_seconds": 5.4
}
```

---

## Configuring Agents

Agents are defined via numbered environment variables. The system discovers them automatically at startup.

```
AGENT_<N>_ID         Unique agent identifier
AGENT_<N>_PROVIDER   anthropic | openai | openai_compat | local
AGENT_<N>_MODEL      Model name (e.g. claude-haiku-4-5-20251001, gpt-4o-mini, llama3)
AGENT_<N>_BASE_URL   Override base URL (for openai_compat / local)
AGENT_<N>_API_KEY    Per-agent API key (falls back to shared ANTHROPIC_API_KEY / OPENAI_API_KEY)
AGENT_<N>_MAX_TOKENS Default: 2048
AGENT_<N>_TEMPERATURE Default: 0.7
AGENT_<N>_TIMEOUT    Seconds. Default: 60
AGENT_<N>_MAX_RETRIES Default: 3
```

Example — three agents with different providers:

```env
AGENT_1_ID=fast-summarizer
AGENT_1_PROVIDER=anthropic
AGENT_1_MODEL=claude-haiku-4-5-20251001

AGENT_2_ID=deep-analyst
AGENT_2_PROVIDER=openai
AGENT_2_MODEL=gpt-4o

AGENT_3_ID=local-coder
AGENT_3_PROVIDER=local
AGENT_3_MODEL=codellama
AGENT_3_BASE_URL=http://localhost:11434/v1
```

---

## Supported Document Types

| Extension | Library         |
|-----------|-----------------|
| `.pdf`    | pdfminer.six    |
| `.docx`   | python-docx     |
| `.html`   | BeautifulSoup4  |
| `.csv`    | stdlib csv      |
| `.txt` `.md` and others | UTF-8 read |

Large documents are automatically chunked. Chunk size and overlap are configured via `CHUNK_SIZE` and `CHUNK_OVERLAP`.

---

## Adding a New LLM Provider

1. Create `api_clients/myprovider_client.py` — subclass `BaseLLMClient`, implement `_complete_impl()`.
2. Register it in `api_clients/factory.py` `build_client()` under a new provider label.
3. Set `AGENT_N_PROVIDER=myprovider` in your `.env`.

No other changes are needed.

---

## Environment Variable Reference

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Listen port |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR |
| `UPLOAD_DIR` | `./uploads` | Directory for saved uploads |
| `CHUNK_SIZE` | `3000` | Characters per document chunk |
| `CHUNK_OVERLAP` | `200` | Overlap between chunks |
| `MAX_CONCURRENT_AGENTS` | `5` | Max simultaneous agent calls |
| `CONTROLLER_PROVIDER` | `anthropic` | Controller LLM provider |
| `CONTROLLER_MODEL` | `claude-sonnet-4-20250514` | Controller model |
| `ANTHROPIC_API_KEY` | — | Shared Anthropic key |
| `OPENAI_API_KEY` | — | Shared OpenAI key |
