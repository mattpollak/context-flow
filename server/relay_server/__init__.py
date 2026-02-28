"""relay MCP server — search Claude Code conversation history."""

import logging


def main():
    """Entry point for the relay-server CLI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    from .server import mcp
    mcp.run()
