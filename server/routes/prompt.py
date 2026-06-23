from fastapi import APIRouter
from pydantic import BaseModel

from ..aiquery import default_prompt, preview_prompt
from ..config import settings
from ..llm import chat

router = APIRouter()


class GenerateIn(BaseModel):
    components: list[dict] = []
    model: str | None = None
    instruction: str = ""


class ImproveIn(BaseModel):
    prompt_text: str
    instruction: str
    components: list[dict] = []
    model: str | None = None


class PreviewIn(BaseModel):
    prompt_text: str
    components: list[dict] = []


_SYSTEM = (
    "You are an expert prompt engineer building a classification prompt for Databricks "
    "ai_query. The prompt is applied to each vehicle's technician service notes to classify "
    "upsell/replacement opportunity for the given component(s) as exactly Urgent, Upcoming, or "
    "Good, each with a short reasoning grounded in the notes. "
    "Be CONCISE: the prompt is re-sent for every row, so keep it tight — state the criteria and "
    "thresholds clearly, add at most one short example only if it materially improves accuracy, "
    "and avoid restating the same rule multiple ways. "
    "Do NOT include any output-format section, JSON spec, response template, or instructions "
    "about how to structure the answer — the response schema is enforced by the system "
    "separately, and any format instructions you add will conflict with it. Focus only on the "
    "classification criteria and reasoning guidance. "
    "Output ONLY the prompt text — no preamble, no markdown fences, no commentary."
)


def _clean(text: str) -> str:
    """Strip accidental markdown code fences the model sometimes wraps around the prompt."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def _components_block(components: list[dict]) -> str:
    lines = []
    for c in components:
        line = f"- {c.get('display_name', c.get('component_key'))} ({c.get('component_key')})"
        if c.get("description"):
            line += f": {c['description']}"
        if c.get("rubric"):
            line += f"\n    Rubric: {c['rubric']}"
        lines.append(line)
    return "\n".join(lines) or "(none selected)"


@router.post("/prompt/generate")
def generate(body: GenerateIn):
    model = body.model or settings.default_model
    if not body.components:
        return {"prompt_text": default_prompt(body.components)}
    user = (
        f"Components to assess:\n{_components_block(body.components)}\n\n"
        f"Guidance from the user (reflect this clearly in the prompt): "
        f"{body.instruction or '(none — use your best judgment)'}\n\n"
        "Write the ai_query classification prompt now."
    )
    try:
        text = _clean(chat([{"role": "system", "content": _SYSTEM},
                            {"role": "user", "content": user}], model=model, temperature=0.6))
    except Exception:
        text = default_prompt(body.components)
    return {"prompt_text": text}


@router.post("/prompt/improve")
def improve(body: ImproveIn):
    model = body.model or settings.default_model
    # Lead with the requested change and tell the model to apply it substantively, so feedback
    # is actually reflected rather than producing a token edit.
    user = (
        f"Revise the prompt below. The user's requested change is the priority — apply it "
        f"thoroughly and make it clearly visible in the result; rewrite as much as needed "
        f"(do NOT just make a minor edit), while keeping the core task intact (read the "
        f"technician notes and classify each component as Urgent / Upcoming / Good with a "
        f"short reasoning).\n\n"
        f"=== REQUESTED CHANGE ===\n{body.instruction}\n\n"
        f"=== CURRENT PROMPT ===\n{body.prompt_text}\n\n"
        f"=== COMPONENTS IN SCOPE ===\n{_components_block(body.components)}\n\n"
        "Return the full revised prompt only."
    )
    text = _clean(chat([{"role": "system", "content": _SYSTEM},
                        {"role": "user", "content": user}], model=model, temperature=0.6))
    return {"prompt_text": text}


@router.post("/prompt/preview")
def preview(body: PreviewIn):
    return {"composed": preview_prompt(body.prompt_text, body.components)}
