"""
Quality Score adapter.

Wraps scripts/quality engine for programmatic access via gateway.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure scripts path is available
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / "scripts" / ".env")


class QualityAdapter:
    """Adapter for content quality scoring."""

    async def score_content(
        self,
        content: str,
        rules: Optional[List[str]] = None,
        model: Optional[str] = None,
        use_llm: bool = True,
    ) -> Dict[str, Any]:
        """Score content and return report dict."""
        from scripts.quality.engine import QualityEngine

        engine = QualityEngine(
            rule_sets=rules,
            llm_model=model,
            use_llm=use_llm,
        )

        report = await engine.score_content(content, file_path="<api>")
        return report.to_dict()

    async def score_file(
        self,
        file_path: str,
        rules: Optional[List[str]] = None,
        model: Optional[str] = None,
        use_llm: bool = True,
    ) -> Dict[str, Any]:
        """Score a file and return report dict."""
        from scripts.quality.engine import QualityEngine

        engine = QualityEngine(
            rule_sets=rules,
            llm_model=model,
            use_llm=use_llm,
        )

        report = await engine.score(file_path)
        return report.to_dict()

    def list_rules(self) -> List[Dict[str, str]]:
        """List all available rules."""
        from scripts.quality.rules import get_all_rules

        # Trigger registration
        import scripts.quality.rules.algorithmic_authorship  # noqa
        import scripts.quality.rules.geo_signals  # noqa
        import scripts.quality.rules.content_structure  # noqa
        import scripts.quality.rules.four_us  # noqa

        return [
            {
                "rule_id": r.RULE_ID,
                "rule_name": r.RULE_NAME,
                "category": r.CATEGORY.value,
                "severity": r.SEVERITY.value,
                "description": r.DESCRIPTION,
                "requires_llm": hasattr(r, '_requires_llm') and r._requires_llm,
            }
            for r in get_all_rules()
        ]
