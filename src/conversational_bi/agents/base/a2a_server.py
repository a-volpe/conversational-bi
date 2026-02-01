"""A2A server wrapper for data agents."""

import json
from collections.abc import Callable
from typing import Any

import structlog
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

logger = structlog.get_logger()


class A2AServer:
    """
    Simple A2A-compatible HTTP server for data agents.

    Implements the A2A protocol endpoints:
    - GET /.well-known/agent-card.json - Agent discovery
    - POST /a2a/tasks/send - Handle task requests
    """

    def __init__(
        self,
        agent_card: dict,
        query_handler: Callable[[str], Any],
    ):
        """
        Initialize the A2A server.

        Args:
            agent_card: The agent's discovery card.
            query_handler: Async function to handle queries.
        """
        self.agent_card = agent_card
        self.query_handler = query_handler
        self.app = self._create_app()

    def _create_app(self) -> Starlette:
        """Create the Starlette application with routes."""
        routes = [
            Route("/.well-known/agent-card.json", self._handle_agent_card, methods=["GET"]),
            Route("/a2a/tasks/send", self._handle_task_send, methods=["POST"]),
            Route("/health", self._handle_health, methods=["GET"]),
        ]
        return Starlette(routes=routes)

    async def _handle_agent_card(self, request: Request) -> JSONResponse:
        """Return the agent card for discovery."""
        return JSONResponse(self.agent_card)

    async def _handle_health(self, request: Request) -> JSONResponse:
        """Health check endpoint."""
        return JSONResponse({"status": "healthy", "agent": self.agent_card.get("name")})

    async def _handle_task_send(self, request: Request) -> JSONResponse:
        """
        Handle A2A task/send requests.

        Expected format (JSON-RPC 2.0):
        {
            "jsonrpc": "2.0",
            "id": "...",
            "method": "tasks/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": "..."}]
                }
            }
        }
        """
        try:
            body = await request.json()

            # Validate JSON-RPC structure
            if body.get("jsonrpc") != "2.0":
                return self._error_response(body.get("id"), -32600, "Invalid Request")

            if body.get("method") != "tasks/send":
                return self._error_response(body.get("id"), -32601, "Method not found")

            # Extract message text
            params = body.get("params", {})
            message = params.get("message", {})
            parts = message.get("parts", [])

            query_text = None
            for part in parts:
                if part.get("type") == "text" or part.get("kind") == "text":
                    query_text = part.get("text")
                    break

            if not query_text:
                return self._error_response(body.get("id"), -32602, "Invalid params: no text found")

            logger.info("task_received", query=query_text[:50])

            # Process the query
            result = await self.query_handler(query_text)

            # Format A2A response
            return self._success_response(body.get("id"), result)

        except json.JSONDecodeError:
            return self._error_response(None, -32700, "Parse error")
        except Exception as e:
            logger.error("task_failed", error=str(e))
            return self._error_response(body.get("id") if "body" in dir() else None, -32603, str(e))

    def _success_response(self, request_id: str | None, result: Any) -> JSONResponse:
        """Format successful JSON-RPC response."""
        # Convert QueryResult to A2A format
        artifacts = []

        if hasattr(result, "success"):
            parts = []
            if result.text:
                parts.append({"type": "text", "text": result.text})
            if result.data:
                parts.append({"type": "data", "data": {"rows": result.data}})
            if result.error:
                parts.append({"type": "text", "text": f"Error: {result.error}"})

            artifacts.append({
                "artifactId": "result",
                "name": "Query Result",
                "parts": parts,
            })
        else:
            artifacts.append({
                "artifactId": "result",
                "name": "Query Result",
                "parts": [{"type": "text", "text": str(result)}],
            })

        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "status": "completed",
                "artifacts": artifacts,
            },
        })

    def _error_response(
        self,
        request_id: str | None,
        code: int,
        message: str,
    ) -> JSONResponse:
        """Format error JSON-RPC response."""
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        })


def run_a2a_server(
    agent_card: dict,
    query_handler: Callable[[str], Any],
    host: str = "0.0.0.0",
    port: int = 8000,
) -> None:
    """
    Run the A2A server.

    Args:
        agent_card: The agent's discovery card.
        query_handler: Async function to handle queries.
        host: Host to bind to.
        port: Port to bind to.
    """
    import uvicorn

    server = A2AServer(agent_card, query_handler)
    uvicorn.run(server.app, host=host, port=port)
