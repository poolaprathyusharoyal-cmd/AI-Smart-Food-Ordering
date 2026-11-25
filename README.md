# Goodgrain | AI Smart Food Ordering & Restaurant Assistant

A full-stack learning capstone for a fictional food business. Customers can browse a live catalog, place and track simulated orders, and chat with one assistant that answers general questions, retrieves grounded restaurant information, and prepares confirmation-gated actions. Business and conversation data persist in SQL; no real payment or delivery provider is connected.

## Architecture

```mermaid
flowchart LR
    Browser[HTML / CSS / JavaScript] -->|Fetch + HTTP Basic| API[FastAPI routers]
    API --> Auth[Authentication / validation / request IDs]
    API --> Services[Business services]
    Services --> Repos[Repositories]
    Repos --> SQL[(MySQL or SQLite)]
    API --> Chat[Chat orchestration]
    Chat --> Agent[Single OpenAI tool-calling agent]
    Agent -->|fixed local endpoints + current identity| API
    Chat --> RAG[RAG retrieval]
    RAG --> Embed[OpenAI embeddings]
    Embed --> Chroma[(Persistent ChromaDB)]
    RAG --> KB[PDF / DOCX / TXT sources]
```

```mermaid
erDiagram
    USERS ||--o{ ORDERS : places
    ORDERS ||--|{ ORDER_LINES : contains
    MENU_ITEMS ||--o{ ORDER_LINES : snapshots
    USERS ||--o{ CHAT_SESSIONS : owns
    CHAT_SESSIONS ||--o{ CHAT_MESSAGES : stores
    CHAT_MESSAGES ||--o{ TOOL_RUNS : audits
    CHAT_SESSIONS ||--o{ PENDING_ACTIONS : gates
    USERS ||--o{ PENDING_ACTIONS : requests
    USERS ||--o{ DOCUMENTS : uploads
    USERS { int id PK string username UK string password_hash string role }
    MENU_ITEMS { int id PK string name decimal price int portions boolean is_active }
    ORDERS { int id PK int user_id FK string status decimal total string idempotency_key }
    ORDER_LINES { int id PK int order_id FK int item_id FK int quantity decimal unit_price }
    CHAT_SESSIONS { int id PK int user_id FK string title }
    CHAT_MESSAGES { int id PK int session_id FK int seq_no string role string mode json metadata }
    TOOL_RUNS { int id PK int message_id FK string tool_name string status json result }
    PENDING_ACTIONS { int id PK int session_id FK int user_id FK string status json payload }
    DOCUMENTS { int id PK string filename string sha256 int version string status }
```

Routers own HTTP validation and identity, services own business rules and transaction boundaries, repositories own SQL reads, and the AI/RAG layers call the same business APIs or retrieval services. SQLAlchemy `create_all` initializes tables on startup. Conditional inventory updates and a conditional order-status claim protect checkout and cancellation; unit prices are snapshotted on each order line.

## Project Structure

```text
capstone/
  main.py
  config/          settings and SQLAlchemy configuration
  controllers/     catalog, orders, admin, auth, chat, document routes
  services/        catalog, order, auth, chat business logic
  repositories/    catalog and order data access
  models/          SQLAlchemy entities
  schemas/         Pydantic request/response validation
  security/        HTTP Basic and admin authorization
  agents/          one OpenAI tool-calling agent and allowlisted tools
  rag/             extraction, chunking, embeddings, retrieval
  frontend/        responsive HTML, CSS, Fetch client
  knowledge_base/  fictional menu, allergy and policy sources
  tests/           API, business, RAG and agent tests
```

## Stack

Python 3.12+, FastAPI, Pydantic, SQLAlchemy 2, MySQL/PyMySQL or SQLite, Argon2, OpenAI Python SDK, ChromaDB, PyMuPDF, python-docx, HTTPX and pytest. The project defaults to SQLite so it starts without a database service; set `DATABASE_URL` to MySQL for MySQL-backed runs. Tests use isolated temporary SQLite files and make no external API calls.

## Database and Environment

The environment running this project has no MySQL client/server configured, so SQLite is the runnable default. To use MySQL, create a database and application account, then set a URL such as:

```text
mysql+pymysql://food_app:your-password@127.0.0.1:3306/smart_food
```

Create the database with a MySQL client you have installed:

```sql
CREATE DATABASE smart_food CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'food_app'@'localhost' IDENTIFIED BY 'change-this-password';
GRANT ALL PRIVILEGES ON smart_food.* TO 'food_app'@'localhost';
```

Copy `.env.example` to `.env` and set `DATABASE_URL`. Optional GenAI settings are `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL`, `CHROMA_PATH`, and `INTERNAL_API_BASE_URL`; update the internal base URL if the app runs on a non-default port. Never commit `.env`; credentials are not placed in browser storage.

## Install and Run

From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

Open the storefront at <http://127.0.0.1:8000>, the OpenAPI interface at <http://127.0.0.1:8000/docs>, and health at <http://127.0.0.1:8000/health>. Basic auth is used for protected endpoints. The frontend keeps the demo credentials in memory only; refresh requires signing in again.

## Demo Accounts

- Customer: `customer1` / `Customer123!`
- Customer: `customer2` / `Customer123!`
- Administrator: `admin` / `Admin123!`

The startup seed creates ten fictional dishes, the two requested price points (Masala Dosa ₹90 and Paneer Biryani ₹180), and three sample orders. Seed inserts are idempotent. Change these demo passwords before exposing the app beyond localhost.

## API Outline

- `GET /api/menu_items` and `GET /api/menu_items/{id}` are public; catalog create/update/disable requires admin.
- `POST /api/orders` requires Basic auth and an `Idempotency-Key` header. Customers can only list/read/cancel their own orders.
- `PATCH /api/admin/orders/{id}/status` is admin-only and enforces forward status transitions.
- `POST /api/documents` accepts admin-uploaded PDF, DOCX or TXT up to 10 MB.
- `/api/chat/sessions`, `/api/chat/sessions/{id}/messages`, and `/api/chat/actions/{id}/confirm` are owner-scoped and persisted.
- Responses use validation and safe error messages; each request includes an `X-Request-ID` response header. Swagger is generated at `/docs`.

## OpenAI, RAG and Agent

With no `OPENAI_API_KEY`, the app remains usable: general chat responds with a setup notice, while policy questions use local keyword retrieval and include source citations. With a key, general messages go to the configured OpenAI model, embeddings use `text-embedding-3-small`, and chunks are indexed in persistent ChromaDB. Upload extracts PDF pages, DOCX text or TXT, chunks at 700 characters with 100-character overlap, and retrieves up to four sources. If no source matches, the assistant must say the policy cannot be verified.

There is one agent and seven allowlisted tools: `search_menu_items`, `get_menu_item`, `check_availability`, `create_order`, `get_order_status`, `cancel_order`, and `retrieve_policy`. Read tools call fixed local API paths through HTTPX and use the signed-in user's credentials supplied by the server, never by the model. Create/cancel calls create a ten-minute persisted proposal. The UI shows exact order lines, quoted price, total or cancellation details. Confirmation rechecks current price, stock, ownership and status; rejection performs no mutation. OpenAI tool loops and HTTP calls have finite limits/timeouts.

## Tests

```bash
python -m pytest -q
```

The suite covers catalog validation and roles, authentication, ownership, order snapshots/idempotency/cancellation, concurrent last-portion claims, chat persistence and ownership, pending action rejection/confirmation/replay/stale price, RAG citations, tool allowlisting and OpenAI failure handling. Tests use temporary SQLite databases and mock model responses. MySQL-specific deployment should additionally run the suite against a dedicated MySQL test database before production use.

## Scope and Safety

This is fictional demo software, not a payment, delivery, medical or allergen-safety service. Ingredient documents explicitly warn that cross-contact cannot be ruled out. HTTP Basic must be protected by HTTPS outside localhost. Add rate limiting, operational monitoring, schema migrations and managed secret storage before production deployment.
