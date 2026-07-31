"""Render shared markdown docs for user-facing explainer pages."""

from django.conf import settings

RANK_SCORING_DOC_PATH = settings.BASE_DIR / "docs" / "rank-scoring.md"
_PUBLIC_START_MARKER = "<!-- rank-scoring:public-start -->"
_PUBLIC_END_MARKER = "<!-- rank-scoring:public-end -->"


def rank_scoring_explainer_html() -> str:
    """HTML for the public-facing slice of docs/rank-scoring.md.

    Pulls the section between the public markers, so the About page and
    docs/rank-scoring.md stay in sync from a single source of truth. The
    excluded head (companion doc links, code file names) and tail (the
    internal code-reference table) are developer-only.
    """
    import markdown

    text = RANK_SCORING_DOC_PATH.read_text(encoding="utf-8")
    start = text.index(_PUBLIC_START_MARKER) + len(_PUBLIC_START_MARKER)
    end = text.index(_PUBLIC_END_MARKER)
    body = text[start:end].strip()
    return markdown.markdown(
        body,
        extensions=["extra", "nl2br", "sane_lists"],
        output_format="html5",
        tab_length=2,
    )
