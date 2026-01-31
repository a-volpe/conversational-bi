"""Run all data agents and the orchestrator."""

import asyncio
import multiprocessing
import signal
import sys

import uvicorn

from conversational_bi.agents.base.a2a_server import A2AServer
from conversational_bi.agents.data_agents.customers_agent.agent import (
    CustomersAgent,
    create_customers_agent_card,
)
from conversational_bi.agents.data_agents.orders_agent.agent import (
    OrdersAgent,
    create_orders_agent_card,
)
from conversational_bi.agents.data_agents.products_agent.agent import (
    ProductsAgent,
    create_products_agent_card,
)
from conversational_bi.common.config import get_settings
from conversational_bi.database.connection import DatabasePool
from conversational_bi.llm.openai_client import OpenAIClient


def run_customers_agent():
    """Run the customers agent."""
    settings = get_settings()
    port = settings.customers_agent_port

    async def setup_and_run():
        # Setup database and LLM
        db = DatabasePool()
        await db.connect()
        llm = OpenAIClient()

        # Create agent
        agent = CustomersAgent(db.pool, llm)
        agent_card = create_customers_agent_card(f"http://localhost:{port}")

        # Create and run server
        server = A2AServer(agent_card, agent.process_query)
        config = uvicorn.Config(server.app, host="0.0.0.0", port=port, log_level="info")
        server_instance = uvicorn.Server(config)
        await server_instance.serve()

    asyncio.run(setup_and_run())


def run_orders_agent():
    """Run the orders agent."""
    settings = get_settings()
    port = settings.orders_agent_port

    async def setup_and_run():
        db = DatabasePool()
        await db.connect()
        llm = OpenAIClient()

        agent = OrdersAgent(db.pool, llm)
        agent_card = create_orders_agent_card(f"http://localhost:{port}")

        server = A2AServer(agent_card, agent.process_query)
        config = uvicorn.Config(server.app, host="0.0.0.0", port=port, log_level="info")
        server_instance = uvicorn.Server(config)
        await server_instance.serve()

    asyncio.run(setup_and_run())


def run_products_agent():
    """Run the products agent."""
    settings = get_settings()
    port = settings.products_agent_port

    async def setup_and_run():
        db = DatabasePool()
        await db.connect()
        llm = OpenAIClient()

        agent = ProductsAgent(db.pool, llm)
        agent_card = create_products_agent_card(f"http://localhost:{port}")

        server = A2AServer(agent_card, agent.process_query)
        config = uvicorn.Config(server.app, host="0.0.0.0", port=port, log_level="info")
        server_instance = uvicorn.Server(config)
        await server_instance.serve()

    asyncio.run(setup_and_run())


def main():
    """Run all agents in separate processes."""
    print("Starting Conversational BI Agents...")
    print("=" * 50)

    settings = get_settings()
    print(f"Customers Agent: http://localhost:{settings.customers_agent_port}")
    print(f"Orders Agent:    http://localhost:{settings.orders_agent_port}")
    print(f"Products Agent:  http://localhost:{settings.products_agent_port}")
    print("=" * 50)
    print("Press Ctrl+C to stop all agents")
    print()

    # Create processes for each agent
    processes = [
        multiprocessing.Process(target=run_customers_agent, name="customers-agent"),
        multiprocessing.Process(target=run_orders_agent, name="orders-agent"),
        multiprocessing.Process(target=run_products_agent, name="products-agent"),
    ]

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
        print(f"Started {p.name}")

    # Wait for all processes
    for p in processes:
        p.join()


if __name__ == "__main__":
    main()
