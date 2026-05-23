from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from ingestforge.core.config import ExtractionConfig


@dataclass(frozen=True)
class HtmlExtraction:
    title: str
    clean_text: str
    snippets: list[str]
    diagnostics: dict[str, Any]


def _paragraph_snippets(text: str, *, min_chars: int = 40, limit: int = 20) -> list[str]:
    snippets: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        normalized = " ".join(raw.split())
        if len(normalized) < min_chars or normalized in seen:
            continue
        snippets.append(normalized)
        seen.add(normalized)
        if len(snippets) >= limit:
            break
    if not snippets and text.strip():
        compact = " ".join(text.split())
        if compact:
            snippets.append(compact[:1200])
    return snippets


def _trafilatura_extract(html: str, *, url: str | None, config: ExtractionConfig) -> str | None:
    """Call Trafilatura only when the optional dependency is installed.

    Kept as a small wrapper so tests can monkeypatch it without requiring the
    optional dependency. We intentionally do not set Trafilatura's
    ``target_language`` here: IngestForge supports BCP 47-style multi-language
    output config, while Trafilatura's extraction-time filter is narrower and
    can discard otherwise useful multilingual pages.
    """

    try:
        trafilatura = import_module("trafilatura")
    except ImportError:
        return None
    extracted = trafilatura.extract(
        html,
        url=url,
        output_format="txt",
        include_comments=config.include_comments,
        include_tables=config.include_tables,
        favor_precision=config.trafilatura_favor_precision,
        favor_recall=config.trafilatura_favor_recall,
    )
    if not isinstance(extracted, str):
        return None
    cleaned = extracted.strip()
    return cleaned or None


class HtmlExtractor:
    def __init__(self, config: ExtractionConfig | None = None) -> None:
        if config is None:
            from ingestforge.core.config import ExtractionConfig

            config = ExtractionConfig()
        self.config = config

    def extract(self, html: str, *, url: str | None = None) -> HtmlExtraction:
        if self.config.backend in {"auto", "trafilatura"}:
            extracted = _trafilatura_extract(html, url=url, config=self.config)
            if extracted:
                snippets = _paragraph_snippets(
                    extracted,
                    min_chars=self.config.min_extracted_chars,
                )
                title = self._title_from_html(html)
                return HtmlExtraction(
                    title=title,
                    clean_text=extracted,
                    snippets=snippets,
                    diagnostics={
                        "backend": "trafilatura",
                        "fallback_used": False,
                        "selected_node_count": len(snippets),
                        "clean_text_chars": len(extracted),
                    },
                )
            if self.config.backend == "trafilatura":
                return HtmlExtraction(
                    title=self._title_from_html(html),
                    clean_text="",
                    snippets=[],
                    diagnostics={
                        "backend": "trafilatura",
                        "fallback_used": False,
                        "error": "trafilatura_unavailable_or_empty",
                        "selected_node_count": 0,
                        "clean_text_chars": 0,
                    },
                )

        return self._extract_internal(html, fallback_used=self.config.backend == "auto")

    @staticmethod
    def _title_from_html(html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        return (soup.title.string.strip() if soup.title and soup.title.string else "").strip()

    def _extract_internal(self, html: str, *, fallback_used: bool) -> HtmlExtraction:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside"]):
            tag.decompose()
        title = (soup.title.string.strip() if soup.title and soup.title.string else "").strip()
        texts = []
        for node in soup.find_all(["p", "li", "h1", "h2", "h3", "td", "article", "main"]):
            t = " ".join(node.get_text(" ", strip=True).split())
            if len(t) >= self.config.min_extracted_chars and t not in texts:
                texts.append(t)
        clean = "\n\n".join(texts)
        return HtmlExtraction(
            title=title,
            clean_text=clean,
            snippets=texts[:20],
            diagnostics={
                "backend": "internal_bs4",
                "fallback_used": fallback_used,
                "selected_node_count": len(texts),
                "clean_text_chars": len(clean),
            },
        )
