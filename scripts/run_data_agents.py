#!/usr/bin/env python
"""
Run all data agents as A2A servers.

Usage:
    python scripts/run_data_agents.py              # Run all agents
    python scripts/run_data_agents.py --agent customers  # Run only customers agent

Environment:
    DATABASE_URL: PostgreSQL connection string (required)
    OPENAI_API_KEY: OpenAI API key (required)
"""

import argparse
import asyncio
import multiprocessing
import os
import signal
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import uvicorn

from conversational_bi.agents.base.a2a_server import A2AServer
from conversational_bi.agents.data_agents.base_data_agent import (
    CustomersDataAgent,
    OrdersDataAgent,
    ProductsDataAgent,
)
from conversational_bi.config.loader import get_config_loader
from conversational_bi.database.connection import DatabasePool


def create_agent_runner(agent_class, agent_name: str):
    """Create a function that runs a specific agent."""

    def run_agent():
        async def setup_and_run():
            # Load config
            config_loader = get_config_loader()
            agent_config = config_loader.load_agent_config(agent_name)
            port = agent_config["agent"]["port"]

            # Setup database connection
            dsn = os.environ.get("DATABASE_URL")
            if not dsn:
                print(f"Error: DATABASE_URL not set for {agent_name} agent")
                return

            db = DatabasePool(dsn=dsn)
            await db.connect()

            try:
                # Create agent
                agent = agent_class(db.pool, config_loader=config_loader)
                agent_card = agent.get_agent_card()

                print(f"Starting {agent_card['name']} on port {port}...")

                # Create and run A2A server
                server = A2AServer(agent_card, agent.process_query)
                config = uvicorn.Config(
                    server.app,
                    host="0.0.0.0",
                    port=port,
                    log_level="info",
                )
                server_instance = uvicorn.Server(config)
                await server_instance.serve()
            finally:
                await db.close()

        asyncio.run(setup_and_run())

    return run_agent


# Agent registry
AGENTS = {
    "customers": (CustomersDataAgent, "customers"),
    "orders": (OrdersDataAgent, "orders"),
    "products": (ProductsDataAgent, "products"),
}


def main():
    parser = argparse.ArgumentParser(
        description="Run data agents as A2A servers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--agent",
        choices=list(AGENTS.keys()),
        help="Run only a specific agent",
    )
    args = parser.parse_args()

    # Validate environment
    if not os.environ.get("DATABASE_URL"):
        print("Error: DATABASE_URL environment variable not set")
        sys.exit(1)

    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    # Determine which agents to run
    if args.agent:
        agents_to_run = {args.agent: AGENTS[args.agent]}
    else:
        agents_to_run = AGENTS

    print("Starting Conversational BI Data Agents...")
    print("=" * 50)

    # Load config to show ports
    config_loader = get_config_loader()
    for name in agents_to_run:
        agent_config = config_loader.load_agent_config(name)
        port = agent_config["agent"]["port"]
        print(f"  {name.capitalize()} Agent: http://localhost:{port}")

    print("=" * 50)
    print("Press Ctrl+C to stop all agents")
    print()

    # Create processes for each agent
    processes = []
    for name, (agent_class, config_name) in agents_to_run.items():
        runner = create_agent_runner(agent_class, config_name)
        process = multiprocessing.Process(target=runner, name=f"{name}-agent")
        processes.append(process)

    def signal_handler(sig, frame):
        print("\nStopping all agents...")
        for p in processes:
            if p.is_alive():
                p.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start all processes
    for p in processes:
        p.start()

    # Wait for all processes
    for p in processes:
        p.join()


if __name__ == "__main__":
    main()
