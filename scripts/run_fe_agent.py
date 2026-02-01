#!/usr/bin/env python
"""
Start the FE agent with Streamlit UI.

Usage:
    python scripts/run_fe_agent.py

Environment:
    OPENAI_API_KEY: OpenAI API key (required)
    STREAMLIT_PORT: Port for Streamlit UI (default: 8501)

Ensure data agents are running before starting this script.
"""

import os
import subprocess
import sys
from pathlib import Path

# Load .env file from project root
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def main():
    # Validate environment
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    # Get Streamlit port
    port = os.environ.get("STREAMLIT_PORT", "8501")

    print("Starting Conversational BI Frontend...")
    print("=" * 50)
    print(f"Streamlit UI: http://localhost:{port}")
    print("=" * 50)
    print("\nMake sure data agents are running (scripts/run_data_agents.py)")
    print()

    # Path to Streamlit app
    app_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "src",
        "conversational_bi",
        "ui",
        "app.py",
    )

    # Run Streamlit
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        app_path,
        "--server.port", port,
        "--server.headless", "true",
    ])


if __name__ == "__main__":
    main()
