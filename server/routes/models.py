from fastapi import APIRouter

from ..config import settings
from ..llm import list_chat_models

router = APIRouter()


@router.get("/models")
def get_models():
    return {"models": list_chat_models(), "default": settings.default_model}
