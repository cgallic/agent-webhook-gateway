"""
Quality scoring webhook router.

Exposes scripts/quality engine via HTTP endpoints.
"""

from fastapi import APIRouter

from gateway.models import (
    WebhookResponse,
    QualityScoreRequest,
)
from gateway.adapters.quality_adapter import QualityAdapter

router = APIRouter()
adapter = QualityAdapter()


@router.post("/score", response_model=WebhookResponse)
async def quality_score(request: QualityScoreRequest):
    """
    Score content against quality rules.

    Equivalent to: python -m scripts.quality score --format json
    """
    try:
        rules = request.rules.split(",") if request.rules else None
        data = await adapter.score_content(
            content=request.content,
            rules=rules,
            model=request.model,
            use_llm=request.use_llm,
        )
        return WebhookResponse(success=True, data=data)
    except Exception as e:
        return WebhookResponse(success=False, error=str(e))


@router.get("/rules", response_model=WebhookResponse)
async def quality_rules():
    """
    List all available quality scoring rules.

    Equivalent to: python -m scripts.quality rules
    """
    try:
        rules = adapter.list_rules()
        return WebhookResponse(success=True, data={"rules": rules, "count": len(rules)})
    except Exception as e:
        return WebhookResponse(success=False, error=str(e))
