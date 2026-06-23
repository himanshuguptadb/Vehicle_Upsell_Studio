"""Chat-completions client against Databricks serving endpoints (prompt-assist)."""
from __future__ import annotations

from functools import lru_cache

from openai import OpenAI

from .config import get_token, get_workspace_host, get_workspace_client


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    return OpenAI(api_key=get_token(), base_url=f"{get_workspace_host()}/serving-endpoints")


def chat(messages: list[dict], model: str, *, max_tokens: int = 4096,
         temperature: float = 0.3) -> str:
    resp = _client().chat.completions.create(
        model=model, messages=messages, max_tokens=max_tokens, temperature=temperature,
    )
    return resp.choices[0].message.content or ""


def list_chat_models() -> list[dict]:
    """Databricks Foundation Model chat endpoints usable by ai_query / chat.

    Filtered to chat-completions endpoints (task == llm/v1/chat) whose name starts with
    ``databricks-`` — i.e. the built-in Foundation Model APIs. This deliberately excludes
    embedding/agent endpoints and any custom/external serving endpoints, so demo users can
    only pick a supported foundation model.
    """
    w = get_workspace_client()
    out = []
    for e in w.serving_endpoints.list():
        task = getattr(e, "task", None) or ""
        name = e.name or ""
        if task == "llm/v1/chat" and name.lower().startswith("databricks-"):
            out.append({"name": name, "task": task})
    out.sort(key=lambda x: x["name"])
    return out
