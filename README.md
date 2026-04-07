# Multi-Agent Productivity Assistant

A **multi-agent AI productivity assistant** built with Python/FastAPI that coordinates specialized sub-agents to help users manage tasks, schedules, and information.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI REST API                      │
├─────────────────────────────────────────────────────────┤
│                   Primary Agent (LangChain)              │
│            Routes requests to sub-agents                 │
├──────────────────────┬──────────────────────────────────┤
│   Calendar Agent     │         Task Agent                │
│  (Google Calendar)   │    (DB-backed Task Manager)       │
├──────────────────────┴──────────────────────────────────┤
│              PostgreSQL (SQLAlchemy ORM)                 │
└─────────────────────────────────────────────────────────┘
```

## Features

- **Primary Agent** – Orchestrates multi-step workflows and routes requests to sub-agents
- **Calendar Agent** – Manages Google Calendar events (CRUD + free-slot finding)
- **Task Agent** – Creates, updates, and queries tasks with priorities and deadlines
- **REST API** – FastAPI endpoints with Pydantic validation and OpenAPI docs
- **Database** – PostgreSQL-backed storage for tasks, schedules, and users
- **Docker** – Containerized for easy local dev and Cloud Run deployment

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | App info |
| GET | `/health` | Health check |
| GET | `/api/v1/tasks` | List tasks |
| POST | `/api/v1/tasks` | Create task |
| GET | `/api/v1/tasks/{id}` | Get task |
| PATCH | `/api/v1/tasks/{id}` | Update task |
| DELETE | `/api/v1/tasks/{id}` | Delete task |
| GET | `/api/v1/tasks/user/{user_id}/summary` | Task summary |
| GET | `/api/v1/tasks/user/{user_id}/overdue` | Overdue tasks |
| GET | `/api/v1/schedules` | List schedules |
| POST | `/api/v1/schedules` | Create schedule |
| GET | `/api/v1/schedules/{id}` | Get schedule |
| PATCH | `/api/v1/schedules/{id}` | Update schedule |
| DELETE | `/api/v1/schedules/{id}` | Delete schedule |
| POST | `/api/v1/schedules/find-slot` | Find available time slot |
| POST | `/api/v1/agents/ask` | Natural language query |
| POST | `/api/v1/workflows/execute` | Execute multi-step workflow |
| POST | `/api/v1/agents/reset` | Reset conversation history |

## Quick Start

### Local Development

1. **Clone and configure:**
   ```bash
   cp .env.example .env
   # Edit .env with your OpenAI and Google API credentials
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start with Docker Compose (recommended):**
   ```bash
   docker-compose up --build
   ```

4. **Or run directly** (requires a running PostgreSQL instance):
   ```bash
   uvicorn app.main:app --reload
   ```

5. **Visit the API docs:** http://localhost:8000/docs

### Running Tests

```bash
pytest tests/ -v
```

## Project Structure

```
multi-agent-productivity-assistant/
├── app/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Configuration management
│   ├── models/                    # SQLAlchemy database models
│   │   ├── user.py
│   │   ├── task.py
│   │   └── schedule.py
│   ├── schemas/                   # Pydantic request/response schemas
│   │   ├── user.py
│   │   ├── task.py
│   │   └── schedule.py
│   ├── database/                  # Database setup & session management
│   │   └── db.py
│   ├── agents/                    # Multi-agent orchestration (LangChain)
│   │   ├── primary_agent.py       # Orchestrator
│   │   ├── calendar_agent.py      # Calendar sub-agent
│   │   ├── task_agent.py          # Task sub-agent
│   │   └── tools.py               # LangChain tool definitions
│   ├── integrations/              # External API wrappers
│   │   ├── google_calendar.py     # Google Calendar API
│   │   └── task_manager.py        # DB-backed task manager
│   ├── routes/                    # FastAPI route handlers
│   │   ├── tasks.py
│   │   ├── schedules.py
│   │   └── agents.py
│   └── utils/
│       ├── logger.py
│       └── validators.py
├── tests/
│   ├── test_agents.py
│   ├── test_integrations.py
│   └── test_routes.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Configuration

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `OPENAI_API_KEY` | OpenAI API key for LangChain agents |
| `OPENAI_MODEL` | Model to use (default: `gpt-4o`) |
| `GOOGLE_CLIENT_ID` | Google OAuth2 Client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth2 Client Secret |
| `SECRET_KEY` | App secret key |
| `LOG_LEVEL` | Logging level (default: `INFO`) |

## Deployment (Google Cloud Run)

```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/productivity-assistant
gcloud run deploy productivity-assistant \
  --image gcr.io/PROJECT_ID/productivity-assistant \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars DATABASE_URL=...,OPENAI_API_KEY=...
```
