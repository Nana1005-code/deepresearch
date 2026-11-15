"""Live reference verification, separate from retrieval provenance and scoring."""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from html.parser import HTMLParser
from io import BytesIO
import ipaddress
import re
import socket
import threading
import time
import unicodedata
from urllib.parse import urljoin, urlsplit

import requests
from pypdf import PdfReader

MAX_BYTES = 24 * 1024 * 1024
_CACHE: OrderedDict[tuple[str, str], tuple[float, dict]] = OrderedDict()
_LOCK = threading.Lock()
_SLOTS = threading.BoundedSemaphore(4)


class Titles(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.titles = []
        self.tag = None
        self.parts = []
        self.h1_count = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and (attrs.get("property") or attrs.get("name") or "").lower() in {"og:title", "twitter:title", "citation_title", "dc.title"}:
            self.titles.append(attrs.get("content", ""))
        if tag == "title" or (tag == "h1" and self.h1_count < 2):
            if tag == "h1": self.h1_count += 1
            self.tag, self.parts = tag, []

    def handle_data(self, data):
        if self.tag: self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == self.tag:
            self.titles.append(" ".join(self.parts))
            self.tag, self.parts = None, []


def _key(text):
    # Expand only established model-family abbreviations, not semantic guesses.
    for short, full in ((r"(?<![a-z])MLLMs?(?![a-z])", "multimodal large language models"),
                        (r"(?<![a-z])LLMs?(?![a-z])", "large language models"),
                        (r"(?<![a-z])VLMs?(?![a-z])", "vision language models")):
        text = re.sub(short, full, text, flags=re.I)
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())


def title_matches(reported, actual):
    # Formatting and publisher suffixes are ignored, but no semantic/fuzzy match.
    expected = reported.strip()
    # A complete exact title may legitimately be short (e.g. BERT).
    if _key(expected) and _key(expected) == _key(actual):
        return True
    expected = re.sub(r"[（(]\d{4}[-/.]\d{1,2}[-/.]\d{1,2}[）)]$", "", expected).strip()
    # Reports append venue/model notes in full-width parentheses; these are
    # bibliographic annotations, not part of the article title.
    annotated = re.sub(r"（[^（）]+）$", "", expected).strip()
    if len(_key(annotated)) >= 16:
        expected = annotated
    bibliographic = bool(re.search(r"\[[JMCNDR]\]", expected, re.I))
    if bibliographic:
        expected = re.split(r"\[[JMCNDR]\]", expected, maxsplit=1, flags=re.I)[0]
        expected = re.split(r"[.．]\s+", expected)[-1]
    expected = re.split(r"\s+[|｜]\s*", expected, maxsplit=1)[0]
    actual = actual.strip()
    variants = [actual]
    for separator in (" | ", " - ", " – ", " — ", "_", " |", "｜"):
        if separator in actual:
            variants.append(actual.rsplit(separator, 1)[0])
    variants.extend(value.split(" - ", 1)[0] for value in list(variants) if " - " in value)
    if expected.startswith("《") and "》" in expected:
        expected = expected[1:expected.index("》")]
    # Conference pages prepend the event and presentation type to the title.
    prefix = r"^(?:NeurIPS|ICML|CVPR|ICLR)(?:\s+\d{4})?\s+(?:Poster|Oral|Paper)\s*:?\s*"
    expected = re.sub(prefix, "", expected, flags=re.I)
    variants = [re.sub(prefix, "", value, flags=re.I) for value in variants]
    target = _key(expected)
    # A full distinctive main title can omit the subtitle after a colon.
    if len(target) >= 24 and len(expected.split()) >= 3:
        if any(_key(value.split(":", 1)[0]) == target for value in variants if ":" in value):
            return True
    return len(target) >= 4 and any(_key(value) == target for value in variants)


def _public_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("不支持的链接")
    if parsed.port not in {None, 80, 443}:
        raise ValueError("不支持的链接端口")
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("该链接不是公开网页地址")


def _fetch_titles_once(url):
    deadline = time.monotonic() + 60
    current = url
    with requests.Session() as session:
        session.trust_env = False
        for _ in range(5):
            _public_url(current)
            if time.monotonic() > deadline: raise TimeoutError()
            with session.get(current, timeout=(10, 20), allow_redirects=False, stream=True,
                             headers={"User-Agent": "Mozilla/5.0 (compatible; ResearchReferenceVerifier/1.0)", "Accept": "text/html,application/pdf"}) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location")
                    if not location: raise ValueError("跳转地址缺失")
                    current = urljoin(current, location)
                    continue
                if response.status_code != 200:
                    raise ValueError(f"链接访问返回 HTTP {response.status_code}")
                data = bytearray()
                for chunk in response.iter_content(32768):
                    if time.monotonic() > deadline: raise TimeoutError()
                    data.extend(chunk)
                    if len(data) > MAX_BYTES: raise ValueError("文件过大，暂无法核验标题")
                content_type = response.headers.get("Content-Type", "").lower()
                if bytes(data[:5]) == b"%PDF-":
                    reader = PdfReader(BytesIO(data))
                    titles = [str((reader.metadata or {}).get("/Title") or "")]
                    first = reader.pages[0].extract_text() if reader.pages else ""
                    return current, titles, " ".join((first or "").splitlines()[:15])
                if "html" not in content_type and b"<html" not in bytes(data[:1000]).lower():
                    raise ValueError("未识别到网页或 PDF 标题")
                encoding = response.encoding
                if not encoding or encoding.lower() == "iso-8859-1":
                    match = re.search(br"charset=[\"']?([a-zA-Z0-9_-]+)", data[:10000], re.I)
                    encoding = match.group(1).decode("ascii") if match else "utf-8"
                parser = Titles()
                parser.feed(data.decode(encoding, errors="replace"))
                return current, [title.strip() for title in parser.titles if title.strip()], ""
    raise ValueError("链接跳转次数过多")


def fetch_titles(url):
    # A single transient timeout must not permanently fail a valid reference.
    for attempt in range(2):
        try:
            return _fetch_titles_once(url)
        except (requests.Timeout, requests.ConnectionError, TimeoutError):
            if attempt: raise


def eligible(row):
    # Only strengthen already matched references; do not equate provenance with
    # a live existence/title check. Check the REPORT URL, never a repair fallback.
    return bool(row.get("verified") and str(row.get("url") or "").startswith(("https://", "http://")))


def cached(row):
    key = (row.get("url", ""), row.get("title", ""))
    with _LOCK:
        item = _CACHE.get(key)
        if item and item[0] > time.monotonic():
            _CACHE.move_to_end(key)
            return dict(item[1])
        _CACHE.pop(key, None)
    return None


def verify(row, force=False):
    if not eligible(row):
        return {"status": "unconfirmed", "reason": "该条目尚未匹配到检索来源或不是网络文献"}
    hit = cached(row)
    if hit and not force: return hit
    result = {"status": "unconfirmed", "reason": "暂未完成链接与标题核验", "checked_at": datetime.now(timezone.utc).isoformat(), "url": row["url"]}
    try:
        with _SLOTS:
            final_url, titles, pdf_heading = fetch_titles(row["url"])
        result["resolved_url"] = final_url
        matched = next((title for title in titles if title_matches(row["title"], title)), None)
        # PDF line wrapping may split a title; only inspect the first-page heading.
        if not matched and pdf_heading:
            expected = re.sub(r"（[^（）]+）$", "", row["title"]).strip()
            expected = re.split(r"\[[JMCNDR]\]", expected, maxsplit=1, flags=re.I)[0]
            expected = re.split(r"[.．]\s+", expected)[-1]
            expected = re.split(r"\s+[|｜]\s*", expected, maxsplit=1)[0]
            if len(_key(expected)) >= 12 and _key(expected) in _key(pdf_heading[:600]):
                matched = expected
        if matched:
            result.update(status="real", reason="链接可访问，且页面标题与参考文献标题一致", page_title=matched)
        else:
            result.update(failure_kind="title_mismatch" if titles or pdf_heading else "missing_title", reason="页面标题与参考文献标题不一致" if titles or pdf_heading else "页面未提供可核对的标题", page_title=titles[0] if titles else "")
    except (requests.Timeout, TimeoutError):
        result["reason"] = "链接访问超时，请稍后重新核验"
    except ValueError as exc:
        result["reason"] = str(exc)
    except Exception:
        result["reason"] = "链接暂时无法访问或标题无法读取，请稍后重新核验"
    if result["status"] != "real":
        result.setdefault("failure_kind", "unreachable")
    with _LOCK:
        _CACHE[(row["url"], row["title"])] = (time.monotonic() + (3600 if result["status"] == "real" else 15), result)
        while len(_CACHE) > 512: _CACHE.popitem(last=False)
    return dict(result)


def attach_cached(result):
    for row in result["references"]:
        if eligible(row): row["authenticity"] = cached(row) or {"status": "pending", "reason": "等待核验链接与标题"}
    return result
