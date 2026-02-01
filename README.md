# Conversational BI

A conversational Business Intelligence application that lets you query your data using natural language. Built with a multi-agent architecture using the A2A (Agent-to-Agent) protocol and LangChain.

## Features

- **Natural Language Queries**: Ask questions about your data in plain English
- **Multi-Agent Architecture**: Specialized agents handle different data domains (customers, orders, products)
- **A2A Protocol**: Agents discover and communicate with each other using JSON-RPC 2.0
- **SQL Safety**: All generated SQL is validated to prevent injection attacks
- **Streamlit UI**: Clean, interactive chat interface

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL database (or [Neon](https://neon.tech) serverless Postgres)
- OpenAI API key

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/conversational-bi.git
cd conversational-bi

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL and OPENAI_API_KEY
```

### Database Setup

```bash
# Run migrations to create tables
python scripts/migrate_db.py

# Seed with sample data (optional)
python scripts/seed_data.py
```

### Run the Application

```bash
# Terminal 1: Start data agents
python scripts/run_data_agents.py

# Terminal 2: Start the UI
python scripts/run_fe_agent.py
```

Open http://localhost:8501 in your browser.

## Architecture

```
┌─────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│  Streamlit  │────▶│    FE Agent         │────▶│   Data Agents    │
│     UI      │     │   (LangChain)       │     │  (A2A Protocol)  │
└─────────────┘     └─────────────────────┘     └──────────────────┘
                              │                         │
                              ▼                         ▼
                    ┌─────────────────┐        ┌──────────────┐
                    │  OpenAI LLM     │        │   PostgreSQL │
                    │ (Tool Calling)  │        │   Database   │
                    └─────────────────┘        └──────────────┘
```

### Components

- **FE Agent**: LangChain-based agent that routes queries to appropriate data agents
- **Data Agents**: Domain-specific agents that generate and execute SQL
  - Customers Agent (`:8001`) - Customer data queries
  - Orders Agent (`:8002`) - Order and revenue queries
  - Products Agent (`:8003`) - Product catalog queries

## Example Queries

- "How many customers do we have in Europe?"
- "What are our top 5 products by revenue?"
- "Show me orders from last month with status 'delivered'"
- "What is the average order value by customer segment?"

## Configuration

Configuration is managed via YAML files in the `config/` directory with environment variable substitution:

```yaml
llm:
  model: "${OPENAI_MODEL:gpt-4.1-mini}"
  temperature: 0.0
```

See [CLAUDE.md](CLAUDE.md) for detailed documentation.

## Development

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src/conversational_bi --cov-report=term-missing

# Lint and format
ruff check src tests --fix
ruff format src tests

# Type check
mypy src
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | Model to use (default: gpt-4.1-mini) |
| `CUSTOMERS_AGENT_URL` | Customers agent URL (default: http://localhost:8001) |
| `ORDERS_AGENT_URL` | Orders agent URL (default: http://localhost:8002) |
| `PRODUCTS_AGENT_URL` | Products agent URL (default: http://localhost:8003) |

## License

MIT
