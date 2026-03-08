"""Minimal MCP server for testing — runs over stdio."""

import asyncio
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

app = Server("test-server")


@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="echo",
            description="Echo back the input",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Message to echo"},
                },
                "required": ["message"],
            },
        ),
        Tool(
            name="add_numbers",
            description="Add two numbers",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "integer", "description": "First number"},
                    "b": {"type": "integer", "description": "Second number"},
                },
                "required": ["a", "b"],
            },
        ),
        Tool(
            name="list_items",
            description="List items in a directory (test tool)",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"},
                    "recursive": {"type": "boolean", "description": "Recurse into subdirs"},
                },
                "required": ["path"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "echo":
        return [TextContent(type="text", text=arguments.get("message", ""))]
    if name == "add_numbers":
        result = arguments.get("a", 0) + arguments.get("b", 0)
        return [TextContent(type="text", text=str(result))]
    if name == "list_items":
        path = arguments.get("path", "/")
        recursive = arguments.get("recursive", False)
        return [TextContent(type="text", text=f'{{"path": "{path}", "recursive": {str(recursive).lower()}, "items": ["file1.txt", "file2.txt"]}}')]
    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
