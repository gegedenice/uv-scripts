#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "fastmcp",
#   "httpx[brotli]"  # optional but recommended; remove if you don't want brotli
# ]
# ///

# Must be set before importing/initializing FastMCP internals
import os
os.environ["FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER"] = "true"

DEFAULT_API_BASE = "https://api.openalex.org"
DEFAULT_SPEC_URL = "https://smartbiblia.fr/api/openalex-openapi-server/openapi.json"

import argparse
from pathlib import Path
import httpx
from fastmcp import FastMCP


def build_client(api_base_url: str) -> httpx.AsyncClient:
    headers = {"Accept": "application/json"}
    return httpx.AsyncClient(
        base_url=api_base_url,
        timeout=None,
        headers=headers,
    )

def load_openapi_spec(spec_url: str):
    # if Local file path
    p = Path(spec_url)
    if p.exists() and p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    # Otherwise fetch via HTTP(S)
    headers = {"Accept": "application/json"}
    resp = httpx.get(
        spec_url,
        timeout=None,
        headers=headers,
    )
    resp.raise_for_status()
    return resp.json()

def main():
    parser = argparse.ArgumentParser(description="Generic OpenAPI → FastMCP server")
    # Transports / network
    parser.add_argument("--transport", choices=["stdio", "http", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=3333)
    parser.add_argument("--path", default="/mcp")
    parser.add_argument("--stateless-http", action="store_true", help="Enable stateless HTTP mode")
    # Generic args
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE, help="Base URL for the target API")
    parser.add_argument("--openapi-spec-url", default=DEFAULT_SPEC_URL, help="OpenAPI JSON URL or local file path")
    args = parser.parse_args()
    
    print(f"[FastMCP] api_base_url={args.api_base_url}")
    print(f"[FastMCP] openapi_spec_url={args.openapi_spec_url}")

    client = build_client(args.api_base_url)
    openapi_spec = load_openapi_spec(args.openapi_spec_url)

    mcp = FastMCP.from_openapi(
        openapi_spec=openapi_spec,
        client=client,
        name="Generic OpenAPI MCP Server",
    )

    if args.transport == "stdio":
        print("[FastMCP] Transport=STDIO")
        mcp.run()
    elif args.transport == "http":
        print(f"[FastMCP] Transport=HTTP host={args.host} port={args.port} path={args.path} stateless={args.stateless_http}")
        mcp.run(
            transport="http",
            host=args.host,
            port=args.port,
            path=args.path,
            stateless_http=args.stateless_http,
        )
    elif args.transport == "streamable-http":
        print(f"[FastMCP] Transport=STREAMABLE-HTTP host={args.host} port={args.port} path={args.path} stateless={args.stateless_http}")
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            path=args.path,
            stateless_http=args.stateless_http,
        )

if __name__ == "__main__":
    main()