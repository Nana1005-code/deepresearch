"""Conservative recovery of source identity when a report truncates a URL.

This matches a retrieved source, not the validity of the shortened report URL.
Original URLs remain intact for navigation; callers expose a repair warning.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import unquote, urlsplit

from . import urls
from .parse import Citation, Source


def _title_key(title: str) -> str:
    # Strip publisher suffixes, then ignore typography/spacing only. No fuzzy
    # semantic matching: a similar title is not evidence of the same article.
    title = re.split(r"\s+\||_", title, maxsplit=1)[0]
    return "".join(c for c in unicodedata.normalize("NFKC", title).casefold() if c.isalnum())


def _truncated_url(short: str, full: str) -> bool:
    a, b = urlsplit(urls.normalize(short)), urlsplit(urls.normalize(full))
    if a.netloc != b.netloc or a.query != b.query:
        return False
    left, right = unquote(a.path).rstrip("/"), unquote(b.path).rstrip("/")
    # Segment boundary or numeric article ID followed by a human-readable slug.
    return bool(left and (right.startswith(left + "/") or
                         (re.search(r"/\d+$", left) and right.startswith(left + "-"))))


def match_retrieved_sources(citations: list[Citation], sources: list[Source]) -> None:
    web = [source for source in sources if source.kind == "web"]
    exact = {source.normalized for source in web}
    for citation in citations:
        if not urls.is_http(citation.url) or citation.normalized in exact:
            continue
        title = _title_key(citation.text)
        if len(title) < 16:
            continue
        # Ambiguous same-title records must remain unverified, even if one URL
        # happens to share a longer prefix with the report URL.
        candidates = {source.normalized: source for source in web
                      if urls.domain(source.url) == urls.domain(citation.url)
                      and _title_key(source.title) == title}
        if len(candidates) != 1:
            continue
        source = next(iter(candidates.values()))
        if _truncated_url(citation.url, source.url):
            citation.normalized = source.normalized
            citation.matched_url = source.url
