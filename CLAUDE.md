# Conversational BI

Conversational Business Intelligence application using the A2A (Agent-to-Agent) protocol with a multi-agent architecture.

## Architecture

```
┌─────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│  Streamlit  │────▶│   Orchestrator      │────▶│   Data Agents    │
│     UI      │     │   Agent (:8000)     │     │  (A2A Protocol)  │
└─────────────┘     └─────────────────────┘     └──────────────────┘
                              │                         │
                              ▼                         ▼
                    ┌─────────────────┐        ┌──────────────┐
                    │  OpenAI LLM     │        │ Neon Postgres│
                    │ (Query Analysis)│        │  (Database)  │
                    └─────────────────┘        └──────────────┘
```

### Data Agents
- **Customers Agent** (`:8001`) - Handles customer-related queries
- **Orders Agent** (`:8002`) - Handles order and revenue queries
- **Products Agent** (`:8003`) - Handles product catalog queries

Each data agent:
1. Receives natural language queries via A2A protocol
2. Uses LLM to generate SQL with validation
3. Executes against its designated table
4. Returns structured results

### Orchestrator Agent
- Discovers data agents via A2A protocol
- Analyzes queries to determine which agents to involve
- Executes sub-queries in parallel
- Aggregates results from multiple agents

## Project Structure

```
src/conversational_bi/
├── agents/
│   ├── base/              # A2A server implementation
│   ├── data_agents/       # Customers, Orders, Products agents
│   │   └── base_data_agent.py  # Common data agent logic
│   └── orchestrator/      # Query planning and coordination
├── common/                # Config, exceptions, SQL validator
├── database/              # PostgreSQL connection pool
├── llm/                   # OpenAI client and prompts
└── ui/                    # Streamlit application
```

## Development

### Setup
```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows

# Install dependencies
pip install -e ".[dev]"

# Copy environment file
cp .env.example .env
# Edit .env with your credentials
```

### Running the Application
```bash
# Start all data agents
python scripts/run_agents.py

# In a separate terminal, run the UI
streamlit run src/conversational_bi/ui/app.py
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/conversational_bi --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_sql_validator.py
```

### Linting and Type Checking
```bash
# Format and lint
ruff check src tests --fix
ruff format src tests

# Type check
mypy src
```

## Key Patterns

- **SQL Validation**: All generated SQL is validated before execution via `SQLValidator` to prevent injection attacks
- **A2A Protocol**: Agents communicate using JSON-RPC 2.0 with Agent Cards for discovery
- **Async/Await**: All database and HTTP operations are async
- **Pydantic Settings**: Configuration loaded from environment variables

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Neon PostgreSQL connection string |
| `OPENAI_API_KEY` | OpenAI API key for LLM |
| `CUSTOMERS_AGENT_PORT` | Port for customers agent (default: 8001) |
| `ORDERS_AGENT_PORT` | Port for orders agent (default: 8002) |
| `PRODUCTS_AGENT_PORT` | Port for products agent (default: 8003) |
