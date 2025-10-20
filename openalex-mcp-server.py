#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "fastmcp",
#   "httpx[brotli]"  # optional but recommended; remove if you don't want brotli
# ]
# ///

import os
import argparse
import httpx
from fastmcp import FastMCP

# Must be set before importing/initializing FastMCP internals
os.environ["FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER"] = "true"

def build_client() -> httpx.AsyncClient:
    headers = {"Accept": "application/json"}
    return httpx.AsyncClient(
        base_url="https://api.openalex.org",
        timeout=None,
        headers=headers,
    )

def load_openapi_spec():
    headers = {"Accept": "application/json"}
    resp = httpx.get(
        "https://smartbiblia.fr/api/openalex-openapi-server/openapi.json",
        timeout=None,
        headers=headers,
    )
    resp.raise_for_status()
    return resp.json()

def main():
    parser = argparse.ArgumentParser(description="OpenAlex FastMCP server")
    parser.add_argument("--transport", choices=["stdio", "http", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=3333)
    parser.add_argument("--path", default="/mcp")
    parser.add_argument("--stateless-http", action="store_true", help="Enable stateless HTTP mode (needed for OpenAI Responses MCP HTTP)")
    args = parser.parse_args()

    client = build_client()
    openapi_spec = load_openapi_spec()

    mcp = FastMCP.from_openapi(
        openapi_spec=openapi_spec,
        client=client,
        name="OpenAlex MCP Server",
    )

    print(
        f"Starting FastMCP with transport={args.transport}"
        + (f" host={args.host} port={args.port} path={args.path}" if args.transport != "stdio" else "")
        + (f" stateless_http={args.stateless_http}" if args.transport != "stdio" else "")
    )

    if args.transport == "stdio":
        mcp.run()
    elif args.transport == "http":
        mcp.run(
            transport="http",
            host=args.host,
            port=args.port,
            path=args.path,
            stateless_http=args.stateless_http,
        )
    elif args.transport == "streamable-http":
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            path=args.path,
            stateless_http=args.stateless_http,
        )

if __name__ == "__main__":
    main()

        
#uv run openalex-mcp-server.py --transport streamable-http --host 0.0.0.0 --port 3333 --path /mcp
#uv run openalex-mcp-server.py --transport http --host 0.0.0.0 --port 9999 --path /mcp
#uv run openalex-mcp-server.py --transport stdio