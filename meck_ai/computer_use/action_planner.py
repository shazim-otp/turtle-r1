import json
import os
import re
import time
from typing import List, Dict, Any, Optional

try:
    from ..ai_client import get_ai_client
except ImportError:
    from meck_ai.ai_client import get_ai_client


class ActionPlanner:
    """Decomposes high-level computer use instructions into sequential, verifiable milestone steps."""

    def __init__(self, client: Optional[Any] = None, model: Optional[str] = None):
        self.provider = "gemini"
        if client:
            self.client = client
            self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        else:
            try:
                c, m, _, prov = get_ai_client()
                self.client = c
                self.model = model or m
                self.provider = prov
            except Exception:
                self.client = None
                self.model = model or "gemini-3.5-flash"

    def create_plan(self, user_instruction: str, current_context: Optional[Dict[str, Any]] = None) -> List[str]:
        """Generate structured milestones for the autonomous computer use engine."""
        if not self.client:
            return [
                f"Initialize environment for: {user_instruction}",
                "Navigate to target application or site",
                "Perform required modifications",
                "Verify changes and conclude"
            ]

        prompt = f"""You are the Master Action Planner for an autonomous Windows 10 and browser agent.
Break down the following user instruction into 4 to 8 high-level, clear milestone steps.

User Instruction: "{user_instruction}"
Current Environment: {json.dumps(current_context or {})}

Guidelines:
- Each milestone must be actionable and verifiable.
- Include navigation, section editing, and explicit verification.
- Output ONLY a JSON array of strings, e.g.:
["Open Chrome and navigate to target", "Inspect current sections", "Perform requested edits", "Verify changes are saved"]

Return ONLY the JSON array.
"""
        models = [self.model]
        if self.provider == "gemini":
            for cand in ["gemini-3.5-flash", "gemini-flash-lite-latest", "gemini-3.1-flash-lite"]:
                if cand not in models:
                    models.append(cand)

        for m in models:
            try:
                resp = self.client.chat.completions.create(
                    model=m,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=200,
                )
                raw = (resp.choices[0].message.content or "").strip()
                cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
                steps = json.loads(cleaned)
                if isinstance(steps, list) and all(isinstance(s, str) for s in steps):
                    return steps
            except Exception:
                time.sleep(0.3)
                continue

        return [
            f"Launch required application or website",
            "Locate and inspect relevant content",
            "Execute requested updates or operations",
            "Verify results and complete task"
        ]
