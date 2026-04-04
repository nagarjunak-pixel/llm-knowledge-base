"""Thin wrapper around the Anthropic SDK with a deterministic offline fallback.

The fallback lets the application run (and tests pass) without an API key: it
produces rule-based summaries and echoes queries with basic citations. Real
deployments should set ANTHROPIC_API_KEY for high-quality output.
"""
from __future__ import annotations

import logging
import re
import textwrap
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    text: str
    model: str
    offline: bool = False


class LLMClient:
    def __init__(self, api_key: str | None, model: str, max_tokens: int = 4096):
        self.model = model
        self.max_tokens = max_tokens
        self._client = None
        if api_key:
            try:
                import anthropic  # type: ignore

                self._client = anthropic.Anthropic(api_key=api_key)
            except Exception as exc:  # pragma: no cover - network/sdk errors
                logger.warning("anthropic SDK unavailable, falling back: %s", exc)
                self._client = None

    @property
    def online(self) -> bool:
        return self._client is not None

    def complete(self, system: str, user: str) -> LLMResponse:
        if self._client is None:
            return LLMResponse(text=_offline_complete(system, user),
                               model="offline-stub", offline=True)
        try:
            msg = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            parts = []
            for block in msg.content:
                text = getattr(block, "text", None)
                if text:
                    parts.append(text)
            return LLMResponse(text="\n".join(parts).strip(), model=self.model)
        except Exception as exc:  # pragma: no cover - network errors
            logger.exception("LLM call failed, using offline fallback")
            return LLMResponse(
                text=_offline_complete(system, user) + f"\n\n> [!warning] LLM error: {exc}",
                model="offline-stub",
                offline=True,
            )


# ----- offline fallback -------------------------------------------------------

_SENT = re.compile(r"(?<=[.!?])\s+")


def _first_sentences(text: str, n: int = 3) -> str:
    stripped = re.sub(r"\s+", " ", text).strip()
    if not stripped:
        return ""
    parts = _SENT.split(stripped)
    return " ".join(parts[:n]).strip()


def _extract_keywords(text: str, n: int = 8) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text.lower())
    stop = {
        "this", "that", "with", "from", "have", "will", "been", "were",
        "they", "their", "there", "which", "about", "into", "than", "such",
        "also", "more", "some", "other", "these", "those", "your", "what",
        "when", "where", "while", "would", "could", "should", "because",
    }
    counts: dict[str, int] = {}
    for w in words:
        if w in stop:
            continue
        counts[w] = counts.get(w, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    return [w for w, _ in ranked[:n]]


def _offline_complete(system: str, user: str) -> str:
    """Rule-based imitation of the LLM for offline use and tests."""
    lower = system.lower() + "\n" + user.lower()
    if "summari" in lower or "summary" in lower:
        body = user.split("---CONTENT---", 1)[-1]
        summary = _first_sentences(body, 3) or "(empty source)"
        tags = _extract_keywords(body, 6)
        return textwrap.dedent(
            f"""
            ## Summary
            {summary}

            ## Key points
            - {', '.join(tags) if tags else '(no keywords extracted)'}

            ## Tags
            {', '.join(tags)}
            """
        ).strip()
    if "question" in lower or "answer" in lower or "query" in lower:
        question = user
        keywords = _extract_keywords(question, 5)
        return textwrap.dedent(
            f"""
            # Answer (offline mode)

            The application is running without an ANTHROPIC_API_KEY, so this is a
            rule-based answer. Set the key to enable full LLM answers.

            **Question:** {question.strip()[:500]}

            **Relevant keywords detected:** {', '.join(keywords) if keywords else '(none)'}

            See the search results in the UI for wiki pages matching these keywords.
            """
        ).strip()
    return "(offline stub)"
