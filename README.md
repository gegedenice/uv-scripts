# uv-scripts

uv utilities : some python files remotly actionable with `uv run...`

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

## OpenALex MCP server

```
GH_RAW="https://raw.githubusercontent.com/gegedenice/uv-scripts/main/openalex-mcp-server.py"
```

### Start the OpenALex MCP Server

```bash
uv run "{GH_RAW}"
```

This script creates a FastMCP server that exposes the OpenALex API through the Model Context Protocol (MCP). The server:

- Connects to the OpenALex OpenAPI server at `https://smartbiblia.fr/api/openalex-openapi-server`
- Dynamically loads the OpenAPI specification
- Runs as a streamable HTTP server on `http://0.0.0.0:3333/mcp`
- Uses stateless HTTP mode for OpenAI Response API compatibility

### Server Details

- **Host**: 0.0.0.0 (all interfaces)
- **Port**: 3333
- **Path**: /mcp
- **Transport**: streamable-http
- **Base URL**: https://smartbiblia.fr/api/openalex-openapi-server

The server automatically fetches the latest OpenAPI specification from the remote server and creates MCP tools based on the available endpoints.

### Configuration example

```
{
  "mcpServers": {
    "openalex-mcp-server": {
        "command": "uv",
        "args": ["run", "https://raw.githubusercontent.com/gegedenice/uv-scripts/main/openalex-mcp-server.py"],
        "url": "http://localhost:3333/mcp"
    }     	
  }
}
```