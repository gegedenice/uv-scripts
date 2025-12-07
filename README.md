# uv-scripts

uv utilities : some python files remotly actionable with `uv run...`

## OpenAlex Embedding Atlas Dashboard

A Python script that harvests works from the OpenAlex API and visualizes them using the interactive and semantic dashboard provided by the embedding-atlas library.

See [README](https://github.com/gegedenice/uv-scripts/blob/main/Openalex-embedding-atlas-dashboard/README.md)

## RAG demo

Some Python utilities for building and querying RAG, see [README](https://github.com/gegedenice/uv-scripts/blob/main/RAG/README.md)

## Idref Web services

```
GH_RAW="https://raw.githubusercontent.com/gegedenice/uv-scripts/main/idref-webservice-basic.py"
```

```
uv run "{GH_RAW}" --web-service idref2id --id 240229061 --json-output
```

## llms-openai-inference.py

```
GH_RAW="https://raw.githubusercontent.com/gegedenice/uv-scripts/main/llms-openai-inference.py"
```

### List models (any provider) — raw JSON

```
uv run "{GH_RAW}" --provider openai --api-key "{OPENAI_API_KEY}" --list-models --json-output | jq .
```

### Openai minimal

```
export OPENAI_API_KEY=sk-...
uv run "{GH_RAW}" \
  --provider openai \
  --model gpt-4o-mini \
  -u "Say hello in one sentence."
```

### Groq minimal

```
export GROQ_API_KEY=grq-...
uv run "{GH_RAW}" \
  --provider groq \
  --model moonshotai/kimi-k2-instruct-0905 \
  -u "Give 3 bullet points about RAG pitfalls."
```

### Huggingface minimal

```
uv run "{GH_RAW}" \
  --provider huggingface \
  --hf-subpath novita/v3/openai \
  --model moonshotai/kimi-k2-instruct \
  --api-key "{hf_token}" \
  -u "{USER_PROMPT}" \
  -s "{SYSTEM_PROMPT}" \
  --temperature 0.0 \
  --max-tokens 16384
```

### OpenAI — system prompt + decoding options + token limit

```
uv run "{GH_RAW}" \
  --provider openai \
  --model gpt-4o-mini \
  -u "Summarize OAIS in 2 lines." \
  -s "Be concise and precise." \
  --temperature 0.0 \
  --max-tokens 64
```

### OpenAI — reasoning models (reasoning_effort)

```
uv run "{GH_RAW}" \
  --provider openai \
  --model o3-mini \
  -u "Explain the difference between SIP and AIP in OAIS." \
  --reasoning-effort medium
```

### OpenAI — extra knobs via --options-json

```
uv run "{GH_RAW}" \
  --provider openai \
  --model gpt-4o-mini \
  -u "One insightful line about archival appraisal." \
  --options-json '{"presence_penalty":0.2,"frequency_penalty":0.1}'
```

### Hugging Face Inference Router (OpenAI-compatible path)

```
export HF_API_KEY=hf_...
uv run "{GH_RAW}" \
  --provider hf \
  --hf-subpath openai/v1 \
  --model meta-llama/Meta-Llama-3-8B-Instruct \
  -u "What is an archival fonds?"
```

### Self-hosted / local OpenAI-compatible server (override base URL)

```
export LLM_API_KEY=not-used-or-your-key
uv run "{GH_RAW}" \
  --provider openai \
  --base-url http://localhost:8000/v1 \
  --model my-local-model \
  -u "Test a local server call."
```

### JSON output (easy to script)

```
uv run "{GH_RAW}" \
  --provider openai \
  --model gpt-4o-mini \
  -u "Give me a single JSON object with keys a,b." \
  --json-output | jq -r .text
```

### Read prompt from a file

```
uv run "{GH_RAW}" \
  --provider openai \
  --model gpt-4o-mini \
  -u "$(cat prompt.txt)"
```

## Script for generic MCP servers from OpenAPI specifications : mcp-server-from-openapi.py 

One file, one command : Minimal MCP server generated from an OpenAPI specification using FastMCP with multiple transport features (STDIO, HTTP and Streamable-HTTP).

The server automatically fetches the OpenAPI specification and creates MCP tools based on the available endpoints.

By default, this MCP server targets the OpenAlex REST API using this [provided OpenAPI specification](https://smartbiblia.fr/api/openalex-openapi-server/openapi.json), but it can dynamically adapt to any other API by changing the CLI parameters.

## How it works

1. Loads an OpenAPI spec from a online openapi.json file.
2. Creates an httpx.AsyncClient pinned to the API url (the one described by the openapi.json file).
3. Generates tools automatically with FastMCP.from_openapi(...).
4. Starts the MCP server in the transport you choose at runtime.

### Minimal launch commands

```
GH_RAW="https://raw.githubusercontent.com/gegedenice/uv-scripts/main/mcp-server-from-openapi.py"
API_BASE_URL="..." # Fill with your API base url
OPENAPI_SPEC_URL="..." # Fill with an OpenAPI json specification (url-based or local path)

# Default STDIO on OpenAlex API
uv run "{GH_RAW}"

# STDIO
uv run "{GH_RAW}" \
   --api-base-url "{API_BASE_URL}" --openapi-spec-url "{OPENAPI_SPEC_URL}" \
   --transport stdio

# Local HTTP
uv run "{GH_RAW}" --api-base-url "{API_BASE_URL}" --openapi-spec-url "{OPENAPI_SPEC_URL}" \
   --transport http \
   --port 3333 \
   --path /mcp

# Streamable HTTP
uv run "{GH_RAW}" --api-base-url "{API_BASE_URL}" --openapi-spec-url "{OPENAPI_SPEC_URL}" \
   --transport streamable-http \
   --port 3333 \
   --path /mcp \
   --stateless-http
```

### Environement variables

| Variable                                         | Purpose                              | Recommended                                                         |
| ------------------------------------------------ | ------------------------------------ | ------------------------------------------------------------------- |
| `FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER` | Enables FastMCP’s new OpenAPI parser | Set to `true` **before** using FastMCP (already done in the script) |


### CLI flags

| Flag                 | Values / Type                        |   Default                                                        | Notes                                                                           |
| -------------------- | ------------------------------------ | ---------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `--api-base-url`     | string                               | `https://api.openalex.org`                                       | Base URL for the target API                                                     |
| `--openapi-spec-url` | string                               | `https://smartbiblia.fr/api/openalex-openapi-server/openapi.json`| OpenAPI JSON URL or local file path                                             |
| `--transport`        | `stdio` | `http` | `streamable-http` | `stdio`                                                          | Use `stdio` for Cursor or Claude; `streamable-http` for OpenAI Responses MCP    |
| `--host`             | string                               | `0.0.0.0`                                                        | HTTP modes only                                                                 |
| `--port`             | int                                  | `3333`                                                           | HTTP modes only                                                                 |
| `--path`             | string                               | `/mcp`                                                           | HTTP modes only                                                                 |
| `--stateless-http`   | flag                                 | `false`                                                          | Required for HTTP transport modes                                               |

### Configuration examples

```
# STDIO MCP server on your API_BASE_URL and OPENAPI_SPEC_URL variables
{
  "mcpServers": {
    "openapi-mcp-server": {
        "command": "uv",
        "args": ["run", "https://raw.githubusercontent.com/gegedenice/uv-scripts/main/mcp-server-from-openapi.py", "--api-base-url", API_BASE_URL, "--openapi-spec-url", OPENAPI_SPEC_URL],
    }     	
  }
}
```

```
#streamable-http OpenAlex MCP server
{
  "mcpServers": {
    "openapi-mcp-server": {
        "command": "uv",
        "args": ["run", "https://raw.githubusercontent.com/gegedenice/uv-scripts/main/mcp-server-from-openapi.py", "--transport", "streamable-http", "--stateless-http"],
        "url": "http://localhost:3333/mcp"
    }     	
  }
}
```