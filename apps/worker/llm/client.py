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
    usage: Dict[str, int] = field(default_factory=dict)
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

    def complete(self, messages: List[Dict], tools: Optional[List]=None, response_schema: Optional[Dict]=None, effort: str="medium", stream: bool=False) -> ModelResult:
        """
        Complete with validation against Capabilities.effort_levels, front-loaded system prompt.
        Rules+goal at START per Meta prompting guide.
        """
        if effort not in self.capabilities.effort_levels and self.capabilities.effort_levels:
            # fallback gracefully per playbook
            effort = self.capabilities.effort_levels[0]
        # TODO: implement OpenAI-compatible client call via base_url + model_id
        # For scaffold, return fake for tests/fakes
        return ModelResult(content="Mock completion - implement with openai SDK against base_url", model_id=self.model_id, usage={"prompt_tokens": 100, "completion_tokens": 50})

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
