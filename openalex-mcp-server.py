#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "fastmcp",
#   "httpx"
# ]
# ///
import httpx
from fastmcp import FastMCP
import os
import subprocess

# Create an HTTP client for your API
client = httpx.AsyncClient(
    base_url="https://smartbiblia.fr/api/openalex-openapi-server",
    timeout=None  # disable client-side timeouts for long-running operations
)

# Load your OpenAPI spec 
openapi_spec = httpx.get(
    "https://smartbiblia.fr/api/openalex-openapi-server/openapi.json",
    timeout=None  # avoid startup fetch timing out on slow networks
).json()

# Create the MCP server
mcp = FastMCP.from_openapi(
    openapi_spec=openapi_spec,
    client=client,
    stateless_http=True, #!important for OpenAI Response API to accept the MCP streamable http transport mode
    name="MCP Server"
)
if __name__ == "__main__":
    print("Starting FastMCP server...")
    try:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=3333, path="/mcp")
    except Exception as e:
        print(f"FastMCP server crashed: {{e}}", exc_info=True)