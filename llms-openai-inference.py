#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests",
#   "openai>=1.40.0",
#   "pandas"
# ]
# ///

"""
Universal OpenAI-compatible LLM client with multiple providers (OpenAI, Groq, Runpod, HuggingFace).
Now supports optional `reasoning_effort` for reasoning-capable models.

Examples
--------
uv run llm_client.py --provider openai --model o3-mini \
  -u "Summarize OAIS in 2 lines" --reasoning-effort medium

# Or pass via options-json:
uv run llm_client.py --provider openai --model o3-mini \
  -u "Test" --options-json '{"reasoning_effort":"medium"}'
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

import requests
from openai import OpenAI


# =========================
# Provider loader classes
# =========================

class LLMLoader(ABC):
    """Abstract Base Class for loading LLM models."""
    @abstractmethod
    def get_base_url(self) -> str:
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        pass


class GroqLLMLoader(LLMLoader):
    def __init__(self):
        self.base_url = "https://api.groq.com/openai/v1"
    def get_base_url(self) -> str:
        return self.base_url
    def get_provider_name(self) -> str:
        return "Groq"


class OpenaiLLMLoader(LLMLoader):
    def __init__(self):
        self.base_url = "https://api.openai.com/v1"
    def get_base_url(self) -> str:
        return self.base_url
    def get_provider_name(self) -> str:
        return "OpenAI"


class RunpodLLMLoader(LLMLoader):
    def __init__(self, runpod_endpoint_id: str):
        self.base_url = f"https://api.runpod.ai/v2/{runpod_endpoint_id}/openai/v1"
    def get_base_url(self) -> str:
        return self.base_url
    def get_provider_name(self) -> str:
        return "Runpod"


class HuggingFaceLLMLoader(LLMLoader):
    def __init__(self, provider_subpath: str):
        self.base_url = f"https://router.huggingface.co/{provider_subpath}"
    def get_base_url(self) -> str:
        return self.base_url
    def get_provider_name(self) -> str:
        return "HuggingFace"


# =========================
# Base OpenAI client
# =========================

class BaseOpenAILLMClient:
    """Base class for OpenAI-compatible providers."""
    def __init__(self, api_key: str, model: str, llm_loader: LLMLoader, options: Optional[Dict[str, Any]] = None):
        self.base_url = llm_loader.get_base_url()
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        self.model = model
        self.llm_loader = llm_loader
        self.openai_client = self._create_openai_client()
        self._default_completion_options = {"temperature": 0.1}
        if options:
            self._default_completion_options.update(options)

    def _create_openai_client(self) -> OpenAI:
        return OpenAI(base_url=self.base_url, api_key=self.api_key)

    def list_models(self) -> Any:
        url = f"{self.base_url}/models"
        resp = requests.request("GET", url, headers=self.headers, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def create_chat_completion(
        self,
        user_prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        **options: Any,
    ) -> str:
        """
        Create a chat completion using the LLM client.

        Optional arguments supported include: temperature, top_p, max_tokens, stream,
        and reasoning_effort (for reasoning models): "low" | "medium" | "high".
        """
        merged_options = {**self._default_completion_options, **options}

        base_payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }

        # If provided, include reasoning_effort at the top level of the payload.
        # This is optional and may be ignored/rejected by providers that don't support it.
        if "reasoning_effort" in merged_options and merged_options["reasoning_effort"] is not None:
            base_payload["reasoning_effort"] = merged_options.pop("reasoning_effort")

        payload = {**base_payload, **merged_options}
        completion = self.openai_client.chat.completions.create(**payload)
        return completion.choices[0].message.content


# =========================
# CLI helpers
# =========================

def _infer_api_key(provider: str, cli_key: Optional[str]) -> Optional[str]:
    if cli_key:
        return cli_key
    provider = provider.lower()
    env_map = {
        "openai": "OPENAI_API_KEY",
        "groq": "GROQ_API_KEY",
        "runpod": "RUNPOD_API_KEY",
        "huggingface": None,
    }
    env_name = env_map.get(provider)
    candidates = []
    if env_name:
        candidates.append(env_name)
    if provider == "huggingface":
        candidates.extend(["HF_API_KEY", "HUGGINGFACE_API_KEY"])
    candidates.append("LLM_API_KEY")
    for name in candidates:
        val = os.getenv(name)
        if val:
            return val
    return None


def build_loader(provider: str, args: argparse.Namespace) -> LLMLoader:
    p = provider.lower()
    if p == "openai":
        return OpenaiLLMLoader()
    elif p == "groq":
        return GroqLLMLoader()
    elif p == "runpod":
        if not args.runpod_endpoint_id:
            raise ValueError("--runpod-endpoint-id is required when --provider runpod")
        return RunpodLLMLoader(args.runpod_endpoint_id)
    elif p in {"hf", "huggingface"}:
        sub = args.hf_subpath or "openai/v1"
        return HuggingFaceLLMLoader(sub)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Universal OpenAI-compatible LLM CLI (OpenAI, Groq, Runpod, HuggingFace)."
    )
    parser.add_argument("--provider", required=True, help="openai | groq | runpod | hf|huggingface")
    parser.add_argument("--model", required=False, help="Model name (required unless --list-models).")
    parser.add_argument("--api-key", help="API key (otherwise read from env).")
    parser.add_argument("--base-url", help="Override base URL (advanced).")

    # Provider-specific extras
    parser.add_argument("--runpod-endpoint-id", help="Runpod endpoint ID for openai-compatible route.")
    parser.add_argument("--hf-subpath", help="HuggingFace router subpath (default: openai/v1)")

    # Ops
    parser.add_argument("--list-models", action="store_true", help="List available models and exit.")
    parser.add_argument("--json-output", action="store_true", help="Print raw JSON.")
    parser.add_argument("--verbose", action="store_true", help="Verbose logs to stderr.")

    # Prompts
    parser.add_argument("-u", "--user-prompt", help="User prompt text.")
    parser.add_argument("-s", "--system-prompt", default="You are a helpful assistant.", help="System prompt text.")

    # Common completion options
    parser.add_argument("--temperature", type=float, help="Sampling temperature.")
    parser.add_argument("--top-p", type=float, help="Top-p sampling.")
    parser.add_argument("--max-tokens", type=int, help="Max tokens in response.")
    parser.add_argument("--stream", type=lambda v: str(v).lower() in {"1","true","yes"}, help="Enable streaming (bool).")

    # Reasoning effort (optional, only sent if provided)
    parser.add_argument("--reasoning-effort", choices=["low", "medium", "high"],
                        help="Request extra reasoning effort on reasoning-capable models.")

    # Pass arbitrary options via JSON
    parser.add_argument("--options-json", help='Arbitrary options as JSON, e.g. \'{"presence_penalty":0.1}\'')

    args = parser.parse_args(argv)
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    if args.verbose:
        print(f"[llm] provider={args.provider}", file=sys.stderr)

    api_key = _infer_api_key(args.provider, args.api_key)
    if not api_key:
        print("ERROR: No API key provided. Use --api-key or set an appropriate env var.", file=sys.stderr)
        return 2

    try:
        loader = build_loader(args.provider, args)
        if args.base_url:
            class _OverrideLoader(LLMLoader):
                def get_base_url(self) -> str:
                    return args.base_url
                def get_provider_name(self) -> str:
                    return f"{args.provider}(override)"
            loader = _OverrideLoader()

        # Merge options from CLI flags and JSON blob
        opt: Dict[str, Any] = {}
        if args.temperature is not None:
            opt["temperature"] = args.temperature
        if args.top_p is not None:
            opt["top_p"] = args.top_p
        if args.max_tokens is not None:
            opt["max_tokens"] = args.max_tokens
        if args.stream is not None:
            opt["stream"] = args.stream
        if args.reasoning_effort is not None:
            opt["reasoning_effort"] = args.reasoning_effort
        if args.options_json:
            try:
                extra = json.loads(args.options_json)
                if not isinstance(extra, dict):
                    raise ValueError("options-json must be a JSON object")
                opt.update(extra)
            except json.JSONDecodeError as e:
                print(f"ERROR: Invalid --options-json: {e}", file=sys.stderr)
                return 2

        model_name = args.model or ""
        client = BaseOpenAILLMClient(api_key=api_key, model=model_name, llm_loader=loader, options=opt)

        if args.list_models:
            data = client.list_models()
            if args.json_output:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                models = data.get("data") if isinstance(data, dict) else None
                if isinstance(models, list):
                    for m in models:
                        mid = m.get("id") if isinstance(m, dict) else str(m)
                        print(mid)
                else:
                    print(json.dumps(data, ensure_ascii=False, indent=2))
            return 0

        if not args.model:
            print("ERROR: --model is required unless --list-models is used.", file=sys.stderr)
            return 2
        if not args.user_prompt:
            print("ERROR: --user-prompt is required for chat completion.", file=sys.stderr)
            return 2

        text = client.create_chat_completion(
            user_prompt=args.user_prompt,
            system_prompt=args.system_prompt,
            **opt,
        )

        if args.json_output:
            print(json.dumps({"text": text}, ensure_ascii=False, indent=2))
        else:
            print(text)

        return 0

    except requests.HTTPError as e:
        print(f"HTTP ERROR: {e.response.status_code} {e.response.text}", file=sys.stderr)
        return 3
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))