"""
Meta depth (Day 8): Wonder/image generation + SAM segmentation clients.

Local-first, zero-surprise-credit: both refuse (ValueError -> 422) unless
their provider is explicitly configured. No caller invokes these
automatically; generation happens only on direct user request.
"""
import base64
import os
from typing import Any, Dict, List

import requests


def _image_client():
    """OpenAI-compatible client for the images endpoint. Local proxy first.
    Refuses unless explicitly configured (explicit base URL or proxy key)."""
    from openai import OpenAI
    if not image_configured():
        raise ValueError("Invalid parameters: image provider not configured"
                         " (IMAGE_BASE_URL/IMAGE_API_KEY missing)")
    base_url = os.getenv("IMAGE_BASE_URL") or "http://127.0.0.1:3001/v1"
    api_key = os.getenv("IMAGE_API_KEY", "") or os.getenv("FREELLMAPI_API_KEY", "")
    return OpenAI(base_url=base_url, api_key=api_key or "local")


def image_configured() -> bool:
    base_url = os.getenv("IMAGE_BASE_URL", "")
    if base_url:
        return True
    return bool(os.getenv("FREELLMAPI_API_KEY", ""))


def generate_image(prompt: str, size: str = "1024x1024",
                   model: str | None = None) -> Dict[str, Any]:
    """Text-to-image via an OpenAI-compatible /images/generations endpoint.

    Model id from config/models.yaml (wonder/image) unless overridden.
    Returns b64 payload + provider facts; raises on unconfigured provider.
    """
    if not (prompt or "").strip():
        raise ValueError("Invalid parameters: prompt must be non-empty")
    model = model or _wonder_model_id()
    client = _image_client()
    resp = client.images.generate(model=model, prompt=prompt.strip(), size=size)
    if not resp.data:
        raise RuntimeError("Image provider returned no data")
    item = resp.data[0]
    b64 = getattr(item, "b64_json", None)
    return {"b64_json": b64, "url": getattr(item, "url", None),
            "model_id": model, "mock": False}


def _wonder_model_id() -> str:
    try:
        import yaml
        from pathlib import Path
        cfg = yaml.safe_load(Path("config/models.yaml").read_text()) or {}
        ids = cfg.get("model_ids", {})
        return ids.get("wonder") or ids.get("image") or "muse-wonder-1.0"
    except Exception:
        return "muse-wonder-1.0"


def sam_configured() -> bool:
    return bool(os.getenv("SAM_ENDPOINT_URL", ""))


def segment_image(image_b64: str, points: List[List[int]] | None = None,
                  boxes: List[List[int]] | None = None) -> Dict[str, Any]:
    """Segment Anything via a self-hosted SAM HTTP service.

    Expected contract (documented, conventional): POST {image_b64, points?,
    boxes?} -> {masks: [{bbox, area, mask_rle}], model}. Default
    unconfigured -> 422 with setup hint. No hosted Meta SAM endpoint is
    assumed; bring your own service (see docs/SETTINGS.md).
    """
    url = os.getenv("SAM_ENDPOINT_URL", "")
    if not url:
        raise ValueError("Invalid parameters: SAM not configured"
                         " (SAM_ENDPOINT_URL missing - run a local SAM service)")
    try:
        raw = base64.b64decode(image_b64, validate=True)
    except Exception:
        raise ValueError("Invalid parameters: image_b64 is not valid base64")
    if not raw:
        raise ValueError("Invalid parameters: image_b64 is empty")
    payload: Dict[str, Any] = {"image_b64": image_b64}
    if points:
        payload["points"] = points
    if boxes:
        payload["boxes"] = boxes
    try:
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"SAM service failed: {e}") from e
    if not isinstance(data, dict) or "masks" not in data:
        raise RuntimeError("SAM service returned unexpected shape (need {masks})")
    return {"masks": data["masks"], "model": data.get("model", "sam"),
            "mock": False}
