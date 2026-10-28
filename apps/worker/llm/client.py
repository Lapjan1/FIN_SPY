"""
Model Client Interface - One place that knows Meta protocol per modular playbook Part 9.
Supports parallel tool calls Spark vs single Glimmer, reasoning separation, streaming.

Routing: local-first with privacy gate per docs/FLOWS.md Flowchart #2
"""
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict
import os
import json
import hashlib

@dataclass
class Capabilities:
    max_context: int
    supports_images: bool
    supports_parallel_tools: bool
    supports_structured_output: bool
    effort_levels: List[str]
    is_segmentation: bool = False

@dataclass
class ModelResult:
    content: str
    reasoning: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    usage: Dict[str, Any] = field(default_factory=dict)
    finish_reason: str = "stop"
    model_id: str = ""

# Models.yaml capabilities map (mirrored from config/models.yaml)
CAPABILITIES_MAP: Dict[str, Capabilities] = {
    "muse-spark-1.1": Capabilities(128000, True, True, True, ["low","medium","high"]),
    "muse-spark-1.3": Capabilities(1048576, True, True, True, ["low","medium","high","xhigh"]),
    "muse-wonder-1.0": Capabilities(1048576, True, True, True, ["low","medium","high","xhigh"]),
    "llama3.2:latest": Capabilities(131072, False, True, True, ["low","medium","high"]),
    "qwen2.5:7b": Capabilities(32768, False, True, False, ["low","medium","high"]),
    "sam-3.1": Capabilities(0, True, False, False, [], is_segmentation=True),
}

class PrivacyGateDenied(Exception): pass
class RateLimitError(Exception): pass
class ModelNotLoaded(Exception): pass

class MetaClient:
    """
    DB-first note: Model outputs validated before DB persist, never trusted raw.
    Prompts versioned in prompts/*.md with SHA256 header, never embedded in code.
    """
    def __init__(self, provider: str = "freellmapi", model_id: str = "muse-spark-1.1"):
        self.provider = provider
        self.model_id = model_id
        self.capabilities = CAPABILITIES_MAP.get(model_id, CAPABILITIES_MAP["muse-spark-1.1"])
        self.base_url = os.getenv("FREELLMAPI_BASE_URL", "http://127.0.0.1:3001/v1") if provider=="freellmapi" else os.getenv("OLLAMA_BASE_URL","http://127.0.0.1:11434/v1") if provider=="ollama" else os.getenv("META_BASE_URL","https://api.llama.com/compat/v1")
        # Keys only in env, never in code per AGENTS.md
        self.api_key_env_var = os.getenv("META_API_KEY") if provider=="meta_official" else os.getenv("FREELLMAPI_API_KEY") if provider=="freellmapi" else os.getenv("OLLAMA_API_KEY")

    def complete(self, messages: List[Dict], tools: Optional[List]=None, response_schema: Optional[Dict]=None, effort: str="medium", stream: bool=False, tenant_id: str = "default") -> ModelResult:
        """
        Complete with validation against Capabilities.effort_levels, front-loaded system prompt.
        Rules+goal at START per Meta prompting guide.
        Real implementation: OpenAI-compatible client via base_url + model_id + api_key per config/models.yaml
        For hackathon: freellmapi dev proxy muse-spark-1.1 at http://127.0.0.1:3001/v1 + meta_official muse-spark-1.3 at https://api.llama.com/compat/v1 with $123.88 credits
        """
        if effort not in self.capabilities.effort_levels and self.capabilities.effort_levels:
            effort = self.capabilities.effort_levels[0]

        # Try real API call if key available
        api_key = os.getenv("META_API_KEY") if self.provider=="meta_official" else os.getenv("FREELLMAPI_API_KEY") if self.provider=="freellmapi" else os.getenv("OLLAMA_API_KEY") or "ollama"
        if not api_key and self.provider != "ollama":
            # No key -> mock for tests/fakes
            return ModelResult(content="Mock completion - no API key, implement with openai SDK", model_id=self.model_id, usage={"prompt_tokens": 0, "completion_tokens": 0})

        try:
            from openai import OpenAI
            client = OpenAI(base_url=self.base_url, api_key=api_key)

            # Build params
            kwargs = {
                "model": self.model_id,
                "messages": messages,
                "temperature": 0.2,  # Low temp for extraction per prompts/extract_sa_bank_v1.md
                "max_tokens": 8192,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            if response_schema and self.capabilities.supports_structured_output:
                # Try structured output via response_format json_schema if provider supports
                try:
                    kwargs["response_format"] = {"type": "json_object"}
                except:
                    pass
            # Effort mapping: for Spark, use reasoning_effort header? For now pass via extra param if supported
            # Meta provider uses effort in extra_body? For scaffold, ignore

            from .ratelimit import get_limiter, with_retries, MAX_WAIT_S
            import time as _time
            wait = get_limiter().acquire(tenant_id)
            if wait > MAX_WAIT_S:
                return ModelResult(content='{"statement":{"currency":"ZAR","opening_balance":null,"closing_balance":null},"rows":[],"unaccounted_lines":[],"warnings":["rate limited, deterministic fallback"]}', model_id=self.model_id, usage={"prompt_tokens": 0, "completion_tokens": 0, "error": "rate_limited", "wait_s": round(wait, 1)})
            if wait > 0:
                _time.sleep(min(wait, MAX_WAIT_S))
            resp = with_retries(lambda: client.chat.completions.create(**kwargs))
            choice = resp.choices[0]
            content = choice.message.content or ""
            tool_calls = []
            if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    tool_calls.append({"name": tc.function.name, "arguments": tc.function.arguments, "id": tc.id})

            usage = {}
            if hasattr(resp, 'usage') and resp.usage:
                usage = {"prompt_tokens": resp.usage.prompt_tokens, "completion_tokens": resp.usage.completion_tokens, "total_tokens": resp.usage.total_tokens}

            return ModelResult(content=content, tool_calls=tool_calls, usage=usage, finish_reason=choice.finish_reason, model_id=self.model_id)

        except Exception as e:
            # Fallback to mock for tests/fakes if API fails, but log
            # For hackathon, log token usage for cost guard per config/models.yaml per_document_token_ceiling 15000
            print(f"MetaClient complete failed provider {self.provider} model {self.model_id} base {self.base_url}: {e} - returning mock for tests")
            # Return mock that will trigger validation failure and fallback to deterministic parser per docs/PLAN.md
            return ModelResult(content=f'{{"statement":{{"currency":"ZAR","opening_balance":null,"closing_balance":null}},"rows":[],"unaccounted_lines":[],"warnings":["LLM fallback mock due to API error: {e}"]}}', model_id=self.model_id, usage={"prompt_tokens": 0, "completion_tokens": 0, "error": str(e)})

def local_first_router(text_to_send: str, user_approved: bool = False, local_model_available: bool = True) -> str:
    """
    Flowchart #2: local-first with privacy gate, show exact text before hosted call.
    Returns decision: 'local'|'hosted'|'denied'|'cannot_answer'
    """
    if "bank" in text_to_send.lower() and not user_approved:
        # Sensitive financial data needs explicit approval before hosted
        return "denied_show_exact_text"
    if local_model_available:
        return "local"
    if os.getenv("META_API_KEY") and user_approved:
        return "hosted"
    return "cannot_answer"

def prompt_hash(prompt_path: str) -> str:
    """Hash prompt file for reproducibility per forensic evidence layer."""
    p = Path(prompt_path)
    if not p.exists():
        return "no_prompt_file"
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]

from pathlib import Path

# Model wiring (Day 9): ONE place mapping admin selection to (provider, model).
# Reads model_{purpose} -> model -> model_default (env first, settings table
# second via env_or_setting). Keys stay env-only; only non-secret selection
# lives in the settings table (admin UI saves `model` + `effort`).
MODEL_PROVIDERS: Dict[str, str] = {
    "muse-spark-1.1": "freellmapi",
    "auto": "freellmapi",
    "muse-spark-1.3": "meta_official",
    "muse-spark-1.3-contributor": "meta_official",
    "muse-wonder-1.0": "meta_official",
    "muse-image-1.0": "meta_official",
    "llama3.2:latest": "ollama",
    "qwen2.5:7b": "ollama",
}
DEFAULT_PROVIDER = "freellmapi"
DEFAULT_MODEL = "muse-spark-1.1"


def provider_for_model(model_id: str) -> str:
    """Derive provider from a model id; unknown ids stay on the dev proxy."""
    return MODEL_PROVIDERS.get((model_id or "").strip(), DEFAULT_PROVIDER)


def resolve_model(purpose: str = "extraction") -> tuple:
    """Return (provider, model_id) for a purpose.

    Contributor tier is NEVER resolved from settings/env - real documents
    must not train on contributor (AGENTS.md pitfall). Contributor runs are
    explicit-code-only (synthetic tests pass model_id directly)."""
    from apps.api.db import env_or_setting
    model = (env_or_setting(f"model_{purpose}", "")
             or env_or_setting("model", "")
             or env_or_setting("model_default", "")
             or DEFAULT_MODEL).strip()
    if "contributor" in model:
        model = DEFAULT_MODEL  # fail-closed to the safe dev default
    return provider_for_model(model), model


def get_client(purpose: str = "extraction") -> MetaClient:
    """MetaClient built from resolved admin selection for a purpose."""
    provider, model_id = resolve_model(purpose)
    return MetaClient(provider=provider, model_id=model_id)
