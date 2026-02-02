# Conversational BI

Conversational Business Intelligence application using the A2A (Agent-to-Agent) protocol with a multi-agent architecture powered by LangChain.

## Claude Code Configuration

### Current vs Deprecated Patterns

**CRITICAL**: Always use current patterns. Never use deprecated patterns even if you find them in existing code.

| Current (Always Use) | Deprecated (Never Use) | Notes |
|---------------------|------------------------|-------|
| `.claude/skills/` | `.claude/commands/` | Skills directory for custom commands |
| `gpt-4.1-mini` | `gpt-4o-mini` | Latest OpenAI mini model |
| `gpt-5-mini` | `gpt-4o` | Latest OpenAI model naming |

### Guidelines for Claude Code

1. **When creating new skills**: ALWAYS place them in `.claude/skills/*.md` (not `.claude/commands/`)
2. **When referencing models**: Use the latest naming conventions (`gpt-4.1-mini`, `gpt-5-mini`)
3. **When finding deprecated patterns**: Flag them and ask the user if they want to migrate
4. **Never follow deprecated patterns**: Even if you find them in the existing codebase, use current patterns for all new work

### Maintaining CLAUDE.md

**IMPORTANT**: After completing any major implementation or bug fix, Claude MUST update this CLAUDE.md file to capture learnings and improve future behavior.

#### When to Update CLAUDE.md

- After implementing a new feature or module
- After fixing a significant bug (especially if it required non-obvious solutions)
- When discovering new patterns that should be followed or avoided
- When identifying edge cases or gotchas in the codebase
- After refactoring that changes how components interact

#### What to Document

1. **New Patterns**: Add successful patterns to the "Key Patterns" section or create subsections
2. **Deprecated Patterns**: Add to the "Current vs Deprecated Patterns" table
3. **Common Pitfalls**: Document bugs and their solutions to prevent recurrence
4. **Architecture Changes**: Update the Architecture section if structure changes
5. **New Environment Variables**: Add to the Environment Variables table
6. **New Scripts or Tools**: Document in the appropriate section

#### Example Updates

After fixing a datetime parsing bug:
```markdown
## Known Gotchas

### Datetime Handling
- Always use ISO 8601 format for datetime serialization
- Handle timezone-aware and naive datetimes separately
- Use `datetime.fromisoformat()` for parsing (supports both formats)
```

After adding a new agent:
```markdown
### Data Agents
- **New Agent** (`:800X`) - Description of what it handles
```

This self-improving documentation ensures Claude learns from each session and avoids repeating mistakes.

## Architecture

```
┌─────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│  Streamlit  │────▶│    FE Agent         │────▶│   Data Agents    │
│     UI      │     │   (LangChain)       │     │  (A2A Protocol)  │
└─────────────┘     └─────────────────────┘     └──────────────────┘
                              │                         │
                              ▼                         ▼
                    ┌─────────────────┐        ┌──────────────┐
                    │  OpenAI LLM     │        │ Neon Postgres│
                    │ (Tool Calling)  │        │  (Database)  │
                    └─────────────────┘        └──────────────┘
```

### Frontend Agent (FE Agent)
The FE Agent is a LangChain-based agent that:
- Discovers data agents via A2A protocol at startup
- Dynamically binds discovered agents as LangChain tools
- Routes user queries to appropriate data agents
- Synthesizes results from multiple agents into coherent responses
- Manages chat history and conversation context

### Data Agents
- **Customers Agent** (`:8001`) - Handles customer-related queries
- **Orders Agent** (`:8002`) - Handles order and revenue queries
- **Products Agent** (`:8003`) - Handles product catalog queries

Each data agent:
1. Receives natural language queries via A2A protocol
2. Uses LLM to generate SQL with validation
3. Executes against its designated table
4. Returns structured results with agent card for discovery

## Project Structure

```
src/conversational_bi/
├── agents/
│   ├── base/                    # A2A server implementation
│   │   └── a2a_server.py        # HTTP wrapper for A2A protocol
│   └── data_agents/             # Customers, Orders, Products agents
│       ├── base_data_agent.py   # Config-driven base class
│       ├── customers_agent/
│       ├── orders_agent/
│       └── products_agent/
├── fe_agent/                    # Frontend Agent (LangChain-based)
│   ├── agent.py                 # Main agent with tool orchestration
│   └── tools/
│       ├── discovery.py         # A2A agent discovery
│       └── a2a_client.py        # A2A HTTP client
├── config/                      # Configuration loader
│   └── loader.py                # YAML config with env var substitution
├── common/                      # Config, exceptions, SQL validator
├── database/
│   ├── connection.py            # Async PostgreSQL pool
│   └── migrations/              # Schema migrations
│       ├── runner.py            # SQL migration executor
│       └── init_schema.sql      # Initial schema
├── llm/                         # OpenAI client and prompts
└── ui/                          # Streamlit application

config/                          # YAML configuration files
├── llm.yaml                     # Global LLM settings
├── fe_agent.yaml                # FE agent discovery URLs
├── data_agents/                 # Per-agent configuration
│   ├── customers.yaml
│   ├── orders.yaml
│   └── products.yaml
└── database/
    └── schema.yaml              # Single source of truth for DB schema

scripts/
├── run_data_agents.py           # Launch all data agents
├── run_fe_agent.py              # Launch Streamlit UI
├── migrate_db.py                # Run database migrations
└── seed_data.py                 # Populate test data
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

### Database Setup
```bash
# Run migrations to create tables
python scripts/migrate_db.py

# Optionally seed test data
python scripts/seed_data.py
```

### Running the Application
```bash
# Terminal 1: Start all data agents
python scripts/run_data_agents.py

# Terminal 2: Run the Streamlit UI with FE agent
python scripts/run_fe_agent.py
# Or directly: streamlit run src/conversational_bi/ui/app.py
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

- **Config-Driven Agents**: Data agents are configured via YAML files with SQL validation rules, prompts, and skills
- **SQL Validation**: All generated SQL is validated before execution via `SQLValidator` to prevent injection attacks
- **A2A Protocol**: Agents communicate using JSON-RPC 2.0 with Agent Cards for discovery
- **LangChain Tools**: FE Agent dynamically binds discovered agents as LangChain tools
- **Async/Await**: All database and HTTP operations are async
- **Environment Variable Substitution**: YAML configs support `${VAR_NAME:default}` syntax

## Configuration

Configuration uses YAML files with environment variable substitution:

```yaml
# Example from config/data_agents/customers.yaml
agent:
  name: "Customers Data Agent"
  port: 8001
  table: customers

llm:
  model: "${OPENAI_MODEL:gpt-4.1-mini}"
  temperature: 0.0

sql_validation:
  allowed_tables: [customers]
  forbidden_keywords: [DROP, DELETE, INSERT, UPDATE, ALTER]
  max_rows: 1000
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Neon PostgreSQL connection string |
| `OPENAI_API_KEY` | OpenAI API key for LLM |
| `OPENAI_MODEL` | Model to use (default: gpt-4.1-mini) |
| `CUSTOMERS_AGENT_URL` | URL for customers agent (default: http://localhost:8001) |
| `ORDERS_AGENT_URL` | URL for orders agent (default: http://localhost:8002) |
| `PRODUCTS_AGENT_URL` | URL for products agent (default: http://localhost:8003) |
| `STREAMLIT_PORT` | Port for Streamlit UI (default: 8501) |
| `LOG_LEVEL` | Logging level (default: INFO) |

## Database Schema

The database schema is defined in `config/database/schema.yaml` as a single source of truth:

- **customers** - Customer profiles (region, segment, lifetime_value, etc.)
- **orders** - Transaction records with foreign keys to customers & products
- **products** - Product catalog with inventory and pricing
