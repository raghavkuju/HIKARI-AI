
import asyncio
import ipaddress
import logging
import re
import socket
import time
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS


# ============================================
# HIKARI AI - WEB SEARCH ENGINE v3.2.2
# ============================================

logger = logging.getLogger("hikari.search")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )
    )
    logger.addHandler(handler)

MAX_RESULTS = 6
MAX_PAGE_BYTES = 500_000
MAX_PAGE_CHARS = 6000

SEARCH_TIMEOUT = 12
CACHE_SECONDS = 300

# In-memory cache: resets on server restart.
SEARCH_CACHE = {}

GOV_TERMS = (
    "government",
    "minister",
    "chief minister",
    "prime minister",
    "president",
    "governor",
    "ministry",
    "department",
    "official",
    "sarkar",
    "mukhyamantri",
    "mantri",
    "who is the cm",
)


# ============================================
# URL AND DOMAIN HELPERS
# ============================================

def is_official_host(host):
    host = (host or "").lower().rstrip(".")

    return (
        host.endswith(".gov.in")
        or host.endswith(".nic.in")
    )


def is_government_query(query):
    query = str(query or "").lower()
    return any(word in query for word in GOV_TERMS)


def normalize_url(url):
    try:
        url = str(url or "").strip()
        parsed = urlsplit(url)

        if parsed.scheme not in ("http", "https"):
            return ""

        if not parsed.hostname:
            return ""

        if parsed.username or parsed.password:
            return ""

        return url

    except ValueError:
        return ""


def valid_public_host(host):
    """
    Preliminary DNS validation only.

    This does not eliminate DNS rebinding risks.
    """
    if not host or len(host) > 253:
        return False

    try:
        addresses = socket.getaddrinfo(
            host, 443, type=socket.SOCK_STREAM
        )

        if not addresses:
            return False

        for address in addresses:
            ip = ipaddress.ip_address(
                address[4][0]
            )

            if not ip.is_global:
                return False

        return True

    except (OSError, ValueError):
        return False


def official_page_allowed(url):
    try:
        parsed = urlsplit(url)

        if parsed.scheme != "https":
            return False

        if parsed.username or parsed.password:
            return False

        if parsed.port not in (None, 443):
            return False

        if not is_official_host(parsed.hostname):
            return False

        return valid_public_host(parsed.hostname)

    except ValueError:
        return False


# ============================================
# RESULT NORMALIZATION
# ============================================

def process_results(raw):
    results = []
    seen = set()

    for item in raw or []:
        if not isinstance(item, dict):
            continue

        url = normalize_url(
            item.get("href") or item.get("url")
        )

        if not url or url in seen:
            continue

        seen.add(url)

        parsed = urlsplit(url)

        results.append({
            "title": str(
                item.get("title") or ""
            )[:200],
            "url": url,
            "snippet": str(
                item.get("body")
                or item.get("snippet")
                or ""
            )[:1200],
            "official": is_official_host(
                parsed.hostname
            ),
            "content_type": "snippet",
            "page_text": "",
        })

    return results


# ============================================
# DDGS PROVIDER
# ============================================

def search_sync(
    query,
    max_results=MAX_RESULTS,
    backend="auto",
):
    with DDGS(timeout=SEARCH_TIMEOUT) as engine:
        raw = engine.text(
            query,
            max_results=max_results,
            backend=backend,
        )

    return process_results(raw)


# ============================================
# SEARCH CACHE
# ============================================

def get_cached(query):
    key = query.strip().lower()
    item = SEARCH_CACHE.get(key)

    if not item:
        return None

    timestamp, results = item

    if time.monotonic() - timestamp > CACHE_SECONDS:
        SEARCH_CACHE.pop(key, None)
        return None

    return [dict(result) for result in results]


def save_cache(query, results):
    if not results:
        return

    key = query.strip().lower()

    SEARCH_CACHE[key] = (
        time.monotonic(),
        [dict(result) for result in results],
    )

    # Bound cache size.
    if len(SEARCH_CACHE) > 100:
        oldest = next(iter(SEARCH_CACHE))
        SEARCH_CACHE.pop(oldest, None)


# ============================================
# RELIABLE SEARCH
# ============================================

async def search_web(
    query,
    max_results=MAX_RESULTS,
):
    query = str(query or "").strip()

    if not query:
        return []

    cached = get_cached(query)

    if cached is not None:
        logger.info("Cache hit: %s", query)
        return cached[:max_results]

    # Backends supported by DDGS may vary
    # between installed package versions.
    attempts = (
        ("auto", query),
        ("bing", query),
        ("google", query),
        ("auto", query),
    )

    for attempt_number, (backend, search_query) in enumerate(
        attempts, start=1
    ):
        try:
            logger.info(
                "Search attempt %s backend=%s query=%s",
                attempt_number,
                backend,
                search_query,
            )

            results = await asyncio.wait_for(
                asyncio.to_thread(
                    search_sync,
                    search_query,
                    max_results,
                    backend,
                ),
                timeout=SEARCH_TIMEOUT + 5,
            )

            if results:
                save_cache(query, results)

                logger.info(
                    "Search success: %s results",
                    len(results),
                )

                return results

            logger.warning(
                "Empty results: backend=%s",
                backend,
            )

        except Exception as exc:
            logger.warning(
                "Search error: backend=%s "
                "type=%s message=%s",
                backend,
                type(exc).__name__,
                str(exc),
            )

        if attempt_number < len(attempts):
            await asyncio.sleep(0.5)

    logger.error(
        "All search attempts failed: %s",
        query,
    )

    return []


# ============================================
# OFFICIAL PAGE FETCHER
# ============================================

async def fetch_official_page(url):
    allowed = await asyncio.to_thread(
        official_page_allowed,
        url,
    )

    if not allowed:
        logger.warning(
            "Official page blocked or DNS failed: %s",
            url,
        )
        return ""

    try:
        timeout = httpx.Timeout(
            10.0,
            connect=5.0,
        )

        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
            headers={
                "User-Agent": "HikariAI/3.2.2",
                "Accept": "text/html",
            },
        ) as client:

            async with client.stream(
                "GET", url
            ) as response:

                if response.status_code != 200:
                    logger.warning(
                        "HTTP %s: %s",
                        response.status_code,
                        url,
                    )
                    return ""

                content_type = response.headers.get(
                    "content-type", ""
                ).lower()

                if "text/html" not in content_type:
                    return ""

                data = bytearray()

                async for chunk in response.aiter_bytes():
                    data.extend(chunk)

                    if len(data) > MAX_PAGE_BYTES:
                        logger.warning(
                            "Page too large: %s",
                            url,
                        )
                        return ""

        soup = BeautifulSoup(
            bytes(data),
            "html.parser",
        )

        for tag in soup([
            "script", "style", "nav",
            "footer", "header", "noscript",
            "iframe", "form", "svg",
        ]):
            tag.decompose()

        main = (
            soup.find("main")
            or soup.find("article")
            or soup.body
            or soup
        )

        text = main.get_text(
            separator=" ",
            strip=True,
        )

        return re.sub(
            r"\s+",
            " ",
            text,
        )[:MAX_PAGE_CHARS]

    except Exception as exc:
        logger.warning(
            "Page fetch error: %s - %s",
            url,
            exc,
        )
        return ""


# ============================================
# RESEARCH PIPELINE
# ============================================

async def research_web(query):
    query = str(query or "").strip()

    if not query:
        return []

    government_question = is_government_query(query)

    if government_question:
        queries = [
            f"{query} site:gov.in",
            f"{query} site:nic.in",
            query,
        ]
    else:
        queries = [query]

    combined = []
    seen = set()

    for search_query in queries:
        batch = await search_web(
            search_query,
            MAX_RESULTS,
        )

        for item in batch:
            url = item["url"]

            if url in seen:
                continue

            seen.add(url)
            combined.append(item)

        if len(combined) >= MAX_RESULTS * 2:
            break

    if government_question:
        combined.sort(
            key=lambda item: not item["official"]
        )

    results = combined[:MAX_RESULTS]

    if not results:
        logger.error(
            "NO WEB EVIDENCE: %s",
            query,
        )
        return []

    official_items = [
        item
        for item in results
        if item["official"]
    ][:2]

    if official_items:
        page_texts = await asyncio.gather(
            *[
                fetch_official_page(item["url"])
                for item in official_items
            ],
            return_exceptions=True,
        )

        for item, text in zip(
            official_items,
            page_texts,
        ):
            if isinstance(text, str) and text:
                item["page_text"] = text
                item["content_type"] = "page"

    logger.info(
        "Research complete: %s sources",
        len(results),
    )

    return results


# ============================================
# FORMAT SOURCES FOR AI
# ============================================

def format_search_results(results):
    sections = []

    for index, item in enumerate(results, 1):
        evidence = (
            item.get("page_text")
            or item.get("snippet")
            or ""
        )

        sections.append(
            f"[{index}]\n"
            f"Title: {item.get('title', '')}\n"
            f"URL: {item.get('url', '')}\n"
            f"Official domain: "
            f"{item.get('official', False)}\n"
            f"Evidence type: "
            f"{item.get('content_type', 'snippet')}\n"
            f"Evidence: {evidence}"
        )

    return "\n\n".join(sections)
