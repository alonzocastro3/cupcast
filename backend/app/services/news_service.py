"""
News service: fetches, deduplicates, enriches, and caches World Cup articles.

Pipeline per request:
  1. Cache lookup (key = cupcast:news:{query_hash})
  2. On miss: fetch from provider → validate URLs → deduplicate → tag teams
  3. Cache the full list (10 min TTL)
  4. Filter by team_codes in Python (avoids per-combination cache keys)
  5. Paginate and return

Deduplication:
  - Pass 1: exact match on normalised URL (scheme lowercased, www. stripped,
    tracking params removed, fragment dropped)
  - Pass 2: Jaccard similarity ≥ 0.75 on 4+-character word tokens from title
    (catches "same story, different headline" syndicated duplicates)

URL validation:
  - Scheme must be http or https
  - netloc must be non-empty
  - Common tracking query parameters are stripped
  - Invalid URLs are silently dropped

Team detection:
  - Scans title + summary for known team name variants
  - Returns sorted list of ISO 3-letter country codes
"""
from __future__ import annotations

import hashlib
import logging
import re
from urllib.parse import parse_qs, urlencode, urlparse

from app.integrations.news.base import NewsProvider, NewsProviderError, RawArticle
from app.schemas.news import NewsArticle
from app.services.cache import CacheService, TTL_NEWS, key_news

logger = logging.getLogger(__name__)

# ── Tracking parameters stripped during URL normalisation ─────────────────────

_TRACKING_PARAMS = frozenset(
    {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "utm_id", "fbclid", "gclid", "msclkid", "ref", "source", "share",
        "via", "mc_cid", "mc_eid", "_ga",
    }
)

# ── Team name → country code aliases ─────────────────────────────────────────
# Keys are lowercase; values are ISO 3166-1 alpha-3 codes.
# Longer/more-specific names come first to reduce false positives.

_TEAM_ALIASES: list[tuple[str, str]] = [
    # Group A (seed data)
    ("brazil", "BRA"), ("seleção", "BRA"), ("canarinha", "BRA"),
    ("france", "FRA"), ("les bleus", "FRA"),
    ("spain", "ESP"), ("la roja", "ESP"),
    ("germany", "GER"), ("die mannschaft", "GER"),
    # Group B (seed data)
    ("argentina", "ARG"), ("albiceleste", "ARG"),
    ("england", "ENG"), ("three lions", "ENG"),
    ("portugal", "POR"), ("seleção das quinas", "POR"),
    ("netherlands", "NED"), ("holland", "NED"),
    # Other common WC nations
    ("united states", "USA"), ("usmnt", "USA"), ("team usa", "USA"),
    ("mexico", "MEX"), ("el tri", "MEX"),
    ("japan", "JPN"), ("samurai blue", "JPN"),
    ("morocco", "MAR"), ("atlas lions", "MAR"),
    ("senegal", "SEN"), ("lions of teranga", "SEN"),
    ("nigeria", "NGA"), ("super eagles", "NGA"),
    ("colombia", "COL"), ("los cafeteros", "COL"),
    ("uruguay", "URU"), ("la celeste", "URU"),
    ("croatia", "CRO"), ("vatreni", "CRO"),
    ("denmark", "DEN"), ("danish dynamite", "DEN"),
    ("switzerland", "SUI"), ("nati", "SUI"),
    ("australia", "AUS"), ("socceroos", "AUS"),
    ("south korea", "KOR"),
    ("iran", "IRN"), ("team melli", "IRN"),
    ("ecuador", "ECU"), ("la tri", "ECU"),
    ("saudi arabia", "KSA"),
    ("ghana", "GHA"), ("black stars", "GHA"),
    ("cameroon", "CMR"), ("indomitable lions", "CMR"),
    ("canada", "CAN"), ("canucks", "CAN"),
    ("belgium", "BEL"), ("red devils", "BEL"),
    ("poland", "POL"), ("biało-czerwoni", "POL"),
    ("turkey", "TUR"), ("crescent stars", "TUR"),
    ("ukraine", "UKR"),
    ("serbia", "SRB"),
    ("austria", "AUT"),
    ("hungary", "HUN"),
    ("czech republic", "CZE"), ("czechia", "CZE"),
    ("slovakia", "SVK"),
    ("wales", "WAL"), ("y dreigiau", "WAL"),
    ("scotland", "SCO"),
    ("ireland", "IRL"),
    ("norway", "NOR"),
    ("sweden", "SWE"),
    ("finland", "FIN"),
    ("greece", "GRE"),
    ("romania", "ROU"),
    ("chile", "CHI"),
    ("peru", "PER"),
    ("venezuela", "VEN"),
    ("bolivia", "BOL"),
    ("paraguay", "PAR"),
    ("costa rica", "CRC"),
    ("honduras", "HON"),
    ("panama", "PAN"),
    ("el salvador", "SLV"),
    ("jamaica", "JAM"),
    ("haiti", "HAI"),
    ("egypt", "EGY"), ("pharaohs", "EGY"),
    ("tunisia", "TUN"), ("eagles of carthage", "TUN"),
    ("algeria", "ALG"), ("desert foxes", "ALG"),
    ("mali", "MLI"),
    ("guinea", "GUI"),
    ("ivory coast", "CIV"), ("côte d'ivoire", "CIV"),
    ("cape verde", "CPV"),
    ("zambia", "ZMB"),
    ("china", "CHN"),
    ("indonesia", "IDN"),
    ("iraq", "IRQ"),
    ("new zealand", "NZL"), ("all whites", "NZL"),
]


# ── URL helpers ───────────────────────────────────────────────────────────────

def _validate_and_sanitize_url(url: str) -> str | None:
    """
    Return a sanitised URL or None if the URL is invalid.

    - Rejects non-http/https schemes (data:, javascript:, file:, etc.)
    - Strips common tracking query parameters
    - Drops URL fragments
    """
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return None
        if not parsed.netloc:
            return None
        params = parse_qs(parsed.query, keep_blank_values=False)
        clean = {k: v for k, v in params.items() if k.lower() not in _TRACKING_PARAMS}
        clean_query = urlencode(
            {k: v[0] for k, v in sorted(clean.items())}, safe=""
        )
        return parsed._replace(
            scheme=parsed.scheme.lower(),
            query=clean_query,
            fragment="",
        ).geturl()
    except Exception:
        return None


def _url_dedup_key(url: str) -> str:
    """Normalise URL for deduplication: lowercase, strip www., no trailing slash."""
    try:
        parsed = urlparse(url.lower())
        netloc = parsed.netloc.removeprefix("www.")
        path = parsed.path.rstrip("/") or "/"
        # Include sorted query to catch parameter-reordered duplicates
        params = parse_qs(parsed.query)
        clean_query = urlencode({k: v[0] for k, v in sorted(params.items())})
        return f"{netloc}{path}{'?' + clean_query if clean_query else ''}"
    except Exception:
        return url.lower()


def _article_id(normalized_url: str) -> str:
    return hashlib.sha256(normalized_url.encode()).hexdigest()[:16]


# ── Deduplication ─────────────────────────────────────────────────────────────

_TOKEN_RE = re.compile(r"\b\w{4,}\b")


def _title_tokens(title: str) -> frozenset[str]:
    return frozenset(_TOKEN_RE.findall(title.lower()))


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _deduplicate(raw_articles: list[RawArticle]) -> list[RawArticle]:
    """Remove exact-URL and near-duplicate-title articles."""
    seen_urls: set[str] = set()
    seen_tokens: list[frozenset[str]] = []
    result: list[RawArticle] = []

    for article in raw_articles:
        url_key = _url_dedup_key(article.url)
        if url_key in seen_urls:
            logger.debug("Dedup (url): %s", article.url[:80])
            continue

        tokens = _title_tokens(article.title)
        if any(_jaccard(tokens, existing) >= 0.75 for existing in seen_tokens):
            logger.debug("Dedup (title similarity): %s", article.title[:80])
            continue

        seen_urls.add(url_key)
        seen_tokens.append(tokens)
        result.append(article)

    return result


# ── Team detection ────────────────────────────────────────────────────────────

def _detect_team_codes(title: str, summary: str | None) -> list[str]:
    text = (title + " " + (summary or "")).lower()
    codes: set[str] = set()
    for alias, code in _TEAM_ALIASES:
        if alias in text:
            codes.add(code)
    return sorted(codes)


# ── Service ───────────────────────────────────────────────────────────────────

class NewsService:
    """
    Fetches World Cup news articles from a provider, applies deduplication and
    team tagging, caches the result, and returns paginated + filtered slices.
    """

    def __init__(
        self,
        provider: NewsProvider,
        cache: CacheService,
        query: str = "FIFA World Cup 2026",
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._query = query

    async def get_news(
        self,
        team_codes: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[NewsArticle], int]:
        """
        Return a paginated, optionally team-filtered list of news articles.

        The full article list is cached; team filtering and pagination are
        applied in Python after the cache lookup.  A provider failure returns
        an empty list — the endpoint never 500s due to a news API outage.
        """
        cache_key = key_news(self._query)

        cached = await self._cache.get(cache_key)
        if cached is not None:
            articles = [NewsArticle.model_validate(a) for a in cached]
        else:
            articles = await self._fetch_and_process()
            if articles:
                await self._cache.set(
                    cache_key,
                    [a.model_dump(mode="json") for a in articles],
                    TTL_NEWS,
                )

        if team_codes:
            upper = [c.upper() for c in team_codes]
            articles = [
                a for a in articles
                if any(code in a.related_team_codes for code in upper)
            ]

        total = len(articles)
        page = articles[offset : offset + limit]
        return page, total

    async def _fetch_and_process(self) -> list[NewsArticle]:
        try:
            raw = await self._provider.fetch_articles(self._query)
        except NewsProviderError as exc:
            logger.error("News provider failed: %s", exc)
            return []
        except Exception as exc:
            logger.error("Unexpected news provider error: %s", exc, exc_info=True)
            return []

        # Validate and sanitize URLs — drop articles with bad URLs
        valid: list[RawArticle] = []
        for article in raw:
            clean_url = _validate_and_sanitize_url(article.url)
            if clean_url is None:
                logger.debug("Dropping article with invalid URL: %r", article.url[:80])
                continue
            # Rebuild with sanitized URL
            valid.append(article.model_copy(update={"url": clean_url}))

        deduped = _deduplicate(valid)

        result: list[NewsArticle] = []
        for article in deduped:
            url_key = _url_dedup_key(article.url)
            result.append(
                NewsArticle(
                    id=_article_id(url_key),
                    title=article.title,
                    source=article.source_name,
                    url=article.url,
                    published_at=article.published_at,
                    image_url=_validate_and_sanitize_url(article.image_url)
                    if article.image_url
                    else None,
                    summary=article.summary,
                    related_team_codes=_detect_team_codes(
                        article.title, article.summary
                    ),
                )
            )

        logger.info(
            "Processed news: raw=%d valid=%d deduped=%d",
            len(raw),
            len(valid),
            len(result),
        )
        return result
