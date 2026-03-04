# FastAPI RealWorld API

Production-grade backend implementation of the [RealWorld spec](https://github.com/gothinkster/realworld) using FastAPI.

[![API spec](https://github.com/nsidnev/fastapi-realworld-example-app/workflows/API%20spec/badge.svg)](https://github.com/nsidnev/fastapi-realworld-example-app)
[![Tests](https://github.com/nsidnev/fastapi-realworld-example-app/workflows/Tests/badge.svg)](https://github.com/nsidnev/fastapi-realworld-example-app)
[![codecov](https://codecov.io/gh/nsidnev/fastapi-realworld-example-app/branch/master/graph/badge.svg)](https://codecov.io/gh/nsidnev/fastapi-realworld-example-app)
[![License](https://img.shields.io/github/license/Naereen/StrapDown.js.svg)](https://github.com/nsidnev/fastapi-realworld-example-app/blob/master/LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

## Features

- **JWT authentication** - Secure token-based auth
- **Full CRUD** - Articles, comments, profiles, tags, users
- **AI Agent endpoint** (NEW) - Natural language interface powered by LangChain + OpenAI
  - Example: `"Create an article about Python in 2026"` → automatically calls the articles create endpoint
  - Query articles, users, profiles, comments using plain English
- Production-ready error handling and validation

## Quick Start

### Using Docker (Recommended)
```bash
# Create .env file (or copy .env.example)
cat > .env << EOF
APP_ENV=dev
DATABASE_URL=postgresql://postgres:postgres@db:5432/rwdb
SECRET_KEY=$(openssl rand -hex 32)
OPENAI_API_KEY=your_openai_key_here
EOF

# Start services
docker-compose up -d db
docker-compose up -d app
```

Application runs on `http://localhost:8000`

### Manual Setup

1. **Start PostgreSQL:**
```bash
export POSTGRES_DB=rwdb POSTGRES_PORT=5432 POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
docker run --name pgdb --rm -e POSTGRES_USER="$POSTGRES_USER" \
  -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  -e POSTGRES_DB="$POSTGRES_DB" -p 5432:5432 postgres
```

2. **Install dependencies:**
```bash
git clone https://github.com/nsidnev/fastapi-realworld-example-app
cd fastapi-realworld-example-app
poetry install
poetry shell
```

3. **Configure environment:**
```bash
cat > .env << EOF
APP_ENV=dev
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rwdb
SECRET_KEY=$(openssl rand -hex 32)
OPENAI_API_KEY=your_openai_key_here
EOF
```

4. **Run migrations and start:**
```bash
alembic upgrade head
uvicorn app.main:app --reload
```

## AI Agent Usage

The `/api/agent` endpoint accepts natural language queries.

**Read-only query (no auth required):**
```bash
curl -X POST "http://localhost:8000/api/agent" \
  -H "Content-Type: application/json" \
  -d '{"query": "show me the latest articles"}'
```

**Write operations (requires JWT token):**
```bash
curl -X POST "http://localhost:8000/api/agent" \
  -H "Content-Type: application/json" \
  -H "Authorization: Token YOUR_JWT_TOKEN" \
  -d '{"query": "create an article about FastAPI and LangChain"}'
```

**Get your JWT token:**
```bash
# Register user
curl -X POST "http://localhost:8000/api/users" \
  -H "Content-Type: application/json" \
  -d '{"user": {"username": "test", "email": "test@test.com", "password": "test123"}}'

# Login
curl -X POST "http://localhost:8000/api/users/login" \
  -H "Content-Type: application/json" \
  -d '{"user": {"email": "test@test.com", "password": "test123"}}'
```

## API Documentation

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

## Running Tests
```bash
# Set test database URL
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rwdb_test

# Run all tests
pytest

# Run specific test
pytest tests/test_api/test_routes/test_users.py::test_user_can_not_take_already_used_credentials

# With coverage
pytest --cov=app
```

## Project Structure
```
app/
├── api/              # Web layer
│   ├── dependencies/ # Route dependencies
│   ├── errors/       # Error handlers
│   └── routes/       # API endpoints
├── core/             # Config, startup, logging
├── db/               # Database layer
│   ├── migrations/   # Alembic migrations
│   └── repositories/ # CRUD operations
├── models/           # Pydantic models
│   ├── domain/       # Core domain models
│   └── schemas/      # Request/response schemas
├── resources/        # Response strings
├── services/         # Business logic
└── main.py           # Application entry point
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `APP_ENV` | Environment (dev/prod) | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `SECRET_KEY` | JWT signing key | Yes |
| `OPENAI_API_KEY` | OpenAI API key for agent | Only for `/api/agent` |

## Troubleshooting

**Docker PostgreSQL connection issues:**

If you see `could not connect to server: No such file or directory`, ensure `DATABASE_URL` in `.env` uses `db` as hostname:
```
DATABASE_URL=postgresql://postgres:postgres@db:5432/rwdb
```

For local development, use `localhost` instead.

## License

MIT License - see LICENSE file for details.

---

**Note:** This is a fork with AI agent functionality added. Original repository is not actively maintained but serves as a complete FastAPI/RealWorld implementation reference.