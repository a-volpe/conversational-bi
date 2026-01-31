"""Streamlit UI for the conversational BI application."""

import asyncio
from typing import Any

import pandas as pd
import streamlit as st

from conversational_bi.fe_agent.agent import FEAgent


def get_fe_agent() -> FEAgent:
    """Get or create the FE agent."""
    if "fe_agent" not in st.session_state:
        st.session_state.fe_agent = FEAgent()
    return st.session_state.fe_agent


async def process_query(query: str, chat_history: list[dict]) -> dict[str, Any]:
    """Process a query through the FE agent."""
    agent = get_fe_agent()

    # Convert chat history format
    history = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in chat_history
        if msg["role"] in ("user", "assistant")
    ]

    result = await agent.query(query, history)

    return {
        "response": result["response"],
        "intermediate_steps": result.get("intermediate_steps", []),
    }


async def get_available_agents() -> list[dict]:
    """Get list of available data agents."""
    agent = get_fe_agent()
    return await agent.get_available_agents()


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Conversational BI",
        page_icon="chart_with_upwards_trend",
        layout="wide",
    )

    st.title("Conversational BI")
    st.caption("Ask questions about your business data in natural language")

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "data" in message and message["data"]:
                try:
                    df = pd.DataFrame(message["data"])
                    st.dataframe(df, use_container_width=True)
                except Exception:
                    pass

    # Chat input
    if prompt := st.chat_input("Ask a question about your data..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Display assistant response
        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                try:
                    # Process the query
                    result = asyncio.run(
                        process_query(prompt, st.session_state.messages[:-1])
                    )

                    response = result["response"]
                    st.markdown(response)

                    # Extract and display any data from intermediate steps
                    data_to_show = None
                    for step in result.get("intermediate_steps", []):
                        output = step.get("output", "")
                        if "Data (" in output and "rows" in output:
                            # Try to parse data from tool output
                            try:
                                # Look for data in the output
                                import re
                                import ast
                                matches = re.findall(r"\{[^{}]+\}", output)
                                if matches:
                                    data_to_show = [ast.literal_eval(m) for m in matches[:10]]
                            except Exception:
                                pass

                    if data_to_show:
                        df = pd.DataFrame(data_to_show)
                        st.dataframe(df, use_container_width=True)

                    # Add to chat history
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response,
                        "data": data_to_show,
                    })

                except Exception as e:
                    error_msg = f"An error occurred: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg,
                    })

    # Sidebar
    with st.sidebar:
        st.header("Example Queries")

        example_queries = [
            "How many customers do we have?",
            "What is our total revenue?",
            "Show customer count by region",
            "Top 5 products by price",
            "Average order value",
            "Orders by status",
            "Products with low stock",
        ]

        for query in example_queries:
            if st.button(query, key=query):
                st.session_state.messages.append({"role": "user", "content": query})
                st.rerun()

        st.divider()

        # Available agents
        st.header("Data Agents")
        try:
            agents = asyncio.run(get_available_agents())
            if agents:
                for agent in agents:
                    with st.expander(agent["name"]):
                        st.write(agent["description"])
                        st.caption(f"Skills: {', '.join(agent['skills'][:3])}")
            else:
                st.warning("No agents connected")
                st.caption("Make sure data agents are running")
        except Exception as e:
            st.error(f"Could not connect to agents: {e}")

        st.divider()

        if st.button("Clear Chat"):
            st.session_state.messages = []
            if "fe_agent" in st.session_state:
                del st.session_state.fe_agent
            st.rerun()


if __name__ == "__main__":
    main()
