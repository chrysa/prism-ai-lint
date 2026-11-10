"""Model per task (D-047): judgment subagents off Haiku, mechanical ones on it, no legacy model ids pinned."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from prism_ai_lint._markup import frontmatter_of
from prism_ai_lint._reference import CURRENT_MODELS, MODEL_SNAPSHOT, model_status


class SubagentModelChecker:
    """Judge the model each subagent and skill runs on against the kind of task it does.

    - A security or review subagent (`review`, `audit`, `secur`, `threat`, `pentest`, `vulnerab` in its name or
      description) must not run on Haiku, pinned or inherited from a Haiku session default:
      `SUBAGENT_MODEL_UNDERSIZED` (warn).
    - A subagent is "mechanical" (tests, lint, logs, formatting: a smaller model fits) only when no judgment word
      (review, audit, security, debug, architecture, design, quality, QA, decision...) appears.
    - A legacy model id pinned in an agent or skill frontmatter is reported as `MODEL_LEGACY` (info).
    """

    MECHANICAL = re.compile(r"\b(test|lint|log|triage|format)")
    JUDGMENT = re.compile(
        r"\b(review|audit|secur|threat|pentest|vulnerab|architect|design|debug|root.cause|qa\b|quality|legal|decid|decision)"
    )
    CRITICAL = re.compile(r"\b(review|audit|secur|threat|pentest|vulnerab)")

    @classmethod
    def is_mechanical(cls, name: str, description: str) -> bool:
        text = f"{name} {description}".lower()
        return bool(cls.MECHANICAL.search(text)) and not cls.JUDGMENT.search(text)

    @staticmethod
    def session_model(settings_files: list[Path]) -> str:
        """The default model of the first settings file that sets one (project before user), or ''."""
        for path in settings_files:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and isinstance(data.get("model"), str) and data["model"]:
                return str(data["model"])
        return ""

    def check_dir(self, claude_dir: Path, session_model: str, rep: Any) -> None:
        agents = claude_dir / "agents"
        for sub in sorted(agents.glob("*.md")) if agents.is_dir() else []:
            meta = frontmatter_of(sub)
            model = str(meta.get("model", "")).strip()
            self._legacy(sub, model, rep)
            text = f"{sub.stem} {meta.get('description', '')}".lower()
            if not self.CRITICAL.search(text):
                continue
            effective, how = (model, "pinned") if model and model != "inherit" else (session_model, "inherited")
            if "haiku" in effective.lower():
                rep.add(
                    "warn",
                    "SUBAGENT_MODEL_UNDERSIZED",
                    sub,
                    f"security or review subagent runs on {effective} ({how}): pin 'model: sonnet'",
                )
        skills = claude_dir / "skills"
        for skill in sorted(skills.glob("*/SKILL.md")) if skills.is_dir() else []:
            self._legacy(skill, str(frontmatter_of(skill).get("model", "")).strip(), rep)

    @staticmethod
    def _legacy(path: Path, model: str, rep: Any) -> None:
        if model and model_status(model) == "legacy":
            rep.add(
                "info",
                "MODEL_LEGACY",
                path,
                f"model {model!r} is a previous generation (docs snapshot {MODEL_SNAPSHOT}); "
                f"use an alias (haiku, sonnet, opus) or a current id: {', '.join(sorted(CURRENT_MODELS))}",
            )
