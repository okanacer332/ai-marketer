from __future__ import annotations

from collections import Counter, deque
from dataclasses import asdict, dataclass, field
import asyncio
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from scrapling import Selector
from scrapling.core.shell import Convertor

from .mongo_adaptive_storage import MongoAdaptiveStorageSystem

try:
    from scrapling.fetchers import FetcherSession, AsyncDynamicSession, AsyncStealthySession
    from scrapling.spiders import Spider as ScraplingSpider, Request as SpiderRequest

    SCRAPLING_FETCHERS_AVAILABLE = True
    SCRAPLING_FETCHERS_ERROR = ""
    SCRAPLING_SPIDERS_AVAILABLE = True
    SCRAPLING_SPIDERS_ERROR = ""
except Exception as exc:  # pragma: no cover
    FetcherSession = None  # type: ignore[assignment]
    AsyncDynamicSession = None  # type: ignore[assignment]
    AsyncStealthySession = None  # type: ignore[assignment]
    ScraplingSpider = None  # type: ignore[assignment]
    SpiderRequest = None  # type: ignore[assignment]
    SCRAPLING_FETCHERS_AVAILABLE = False
    SCRAPLING_FETCHERS_ERROR = str(exc)
    SCRAPLING_SPIDERS_AVAILABLE = False
    SCRAPLING_SPIDERS_ERROR = str(exc)


EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(
    r"(?:\+\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{2,4}[\s-]?\d{2,4}"
)
PRICE_PATTERN = re.compile(
    r"(?:[$€£₺]\s?\d[\d\s.,]*|\d[\d\s.,]*\s?(?:TL|USD|EUR|GBP|₺|€|\$))",
    re.IGNORECASE,
)
ADDRESS_HINT_PATTERN = re.compile(
    r"\b(?:mah\.|mahalle|sokak|sk\.|cadde|cd\.|bulvar|no:|kat:|daire|istanbul|ankara|izmir)\b",
    re.IGNORECASE,
)
SOCIAL_HOSTS = (
    "instagram.com",
    "facebook.com",
    "linkedin.com",
    "x.com",
    "twitter.com",
    "youtube.com",
    "tiktok.com",
    "pinterest.com",
    "threads.net",
)
PRIORITY_SEGMENTS = (
    "",
    "about",
    "hakkimizda",
    "products",
    "product",
    "shop",
    "collections",
    "collection",
    "services",
    "service",
    "pricing",
    "fiyat",
    "features",
    "solutions",
    "blog",
    "faq",
    "sss",
    "case",
    "testimonial",
    "referans",
    "portfolio",
    "work",
    "contact",
    "iletisim",
)
SKIP_PATH_KEYWORDS = (
    "/wp-json",
    "/cdn-cgi/",
    "/cart",
    "/checkout",
    "/account",
    "/login",
    "/signin",
    "/register",
    "/privacy",
    "/terms",
    "/cookie",
    "/policy",
    "/feed",
    "/rss",
    "/tag/",
    "/author/",
)
CTA_KEYWORDS = (
    "başla",
    "teklif",
    "hemen",
    "demo",
    "iletişim",
    "fiyat",
    "satın al",
    "incele",
    "keşfet",
    "get",
    "start",
    "book",
    "contact",
    "trial",
    "free",
    "download",
    "quote",
    "shop",
)
TRUST_KEYWORDS = (
    "müşteri",
    "client",
    "clients",
    "partner",
    "partners",
    "referans",
    "reference",
    "testimonial",
    "review",
    "başarı",
    "case study",
    "vaka",
    "award",
    "ödül",
    "certified",
    "sertifika",
    "trusted",
    "güven",
    "uzman",
    "expert",
    "since",
    "years",
    "teknopark",
    "enterprise",
)
AUDIENCE_KEYWORDS = (
    "kobi",
    "kobİ",
    "smb",
    "small business",
    "startup",
    "agency",
    "ajans",
    "brand",
    "marka",
    "publisher",
    "yayıncı",
    "influencer",
    "creator",
    "team",
    "ekip",
    "enterprise",
    "kurum",
    "business",
    "businesses",
    "developer",
    "developers",
    "ecommerce",
    "e-commerce",
)
PROOF_POINT_PATTERN = re.compile(
    r"(?:\b\d{1,3}(?:[.,]\d{3})*(?:\+|x)\b|\b\d{1,3}%\b|\b20\d{2}\b)"
)
GENERIC_TOPIC_TERMS = {
    "home",
    "homepage",
    "about",
    "about us",
    "contact",
    "pricing",
    "blog",
    "services",
    "service",
    "products",
    "product",
    "solutions",
    "solution",
    "faq",
    "sss",
    "menu",
    "ürünlerimizi",
    "yazılım",
    "selected",
    "featured",
    "overview",
    "project",
    "projects",
    "insights",
    "insight",
    "read more",
    "devamını oku",
    "copyright",
    "all rights reserved",
}
LOW_SIGNAL_PHRASES = (
    "services projects blog contact",
    "made with by",
    "all rights reserved",
    "copyright",
    "devamını oku",
    "read more",
    "selected",
    "built with the industry's most",
)
NAVIGATION_NOISE_TOKENS = {
    "home",
    "about",
    "services",
    "service",
    "projects",
    "project",
    "blog",
    "contact",
    "menu",
    "pricing",
    "faq",
    "login",
    "signin",
    "register",
    "search",
    "quote",
    "en",
    "tr",
}
TOPIC_HINT_TOKENS = (
    "ai",
    "seo",
    "geo",
    "aeo",
    "automation",
    "otomasyon",
    "web",
    "mobil",
    "mobile",
    "desktop",
    "yazılım",
    "uygulama",
    "application",
    "platform",
    "erp",
    "outsourcing",
    "danışmanlık",
    "learning",
    "eğitim",
    "muhasebe",
    "designops",
    "legacy",
    "modernizasyon",
)
SERVICE_OFFER_HINTS = (
    "consulting",
    "danışmanlık",
    "development",
    "geliştirme",
    "outsourcing",
    "dedicated team",
    "ekip",
    "service",
    "services",
    "solution",
    "solutions",
    "çözüm",
    "çözümleri",
    "automation",
    "otomasyon",
    "design",
    "tasarım",
    "web",
    "mobil",
    "mobile",
    "desktop",
)
PRODUCT_OFFER_HINTS = (
    "platform",
    "app",
    "application",
    "tool",
    "software",
    "analytics",
    "dashboard",
    "erp",
    "saas",
    "ürün",
    "uygulama",
    "yazılımı",
    "yazılım",
    "learning",
    "visibility",
    "geo",
    "ai report",
)
TECH_SIGNATURES = {
    "Shopify": ("cdn.shopify.com", "shopify.theme", "shopify-payment-button"),
    "WooCommerce": ("woocommerce", "wc-", "wp-content/plugins/woocommerce"),
    "WordPress": ("wp-content", "wp-includes"),
    "Ticimax": ("ticimax", "ticimaxcdn", "ticimax.com"),
    "Next.js": ("__next", "_next/static"),
    "Nuxt": ("__nuxt", "_nuxt/"),
    "React": ("reactroot", "data-reactroot"),
    "Google Tag Manager": ("googletagmanager.com", "gtm.js"),
    "Google Analytics": ("google-analytics.com", "gtag("),
    "Meta Pixel": ("connect.facebook.net", "fbq("),
    "Klaviyo": ("klaviyo", "_learnq"),
    "HubSpot": ("hs-scripts.com", "hubspot"),
    "Stripe": ("js.stripe.com", "stripe"),
}
TRACKER_BLOCKLIST = {
    "google-analytics.com",
    "googletagmanager.com",
    "connect.facebook.net",
    "static.hotjar.com",
    "clarity.ms",
}
BLOCKED_STATUS_CODES = {401, 403, 407, 429, 444, 500, 502, 503, 504}
BLOCKED_BODY_MARKERS = (
    "access denied",
    "attention required",
    "captcha",
    "cloudflare",
    "just a moment",
    "verify you are human",
    "rate limit",
)
DEFAULT_ACCEPT_LANGUAGE = "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
SCRAPE_SELECTOR_CONFIG = {
    "keep_comments": False,
    "keep_cdata": False,
    "huge_tree": True,
}


@dataclass
class FaqItem:
    question: str
    answer: str


@dataclass
class FormSnapshot:
    action: str
    method: str
    fields: list[str]


@dataclass
class PageSnapshot:
    url: str
    title: str
    description: str
    headings: list[str]
    excerpt: str
    raw_text: str
    links: list[str]
    structured_data: list[str] = field(default_factory=list)
    page_type: str = "general"
    fetch_mode: str = "static"
    status_code: int = 200
    main_content: str = ""
    cta_texts: list[str] = field(default_factory=list)
    value_props: list[str] = field(default_factory=list)
    nav_labels: list[str] = field(default_factory=list)
    pricing_signals: list[str] = field(default_factory=list)
    faq_items: list[FaqItem] = field(default_factory=list)
    forms: list[FormSnapshot] = field(default_factory=list)
    entity_labels: list[str] = field(default_factory=list)
    image_alts: list[str] = field(default_factory=list)
    logo_candidates: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    currencies: list[str] = field(default_factory=list)
    hero_messages: list[str] = field(default_factory=list)
    trust_signals: list[str] = field(default_factory=list)
    audience_signals: list[str] = field(default_factory=list)
    proof_points: list[str] = field(default_factory=list)
    zones: dict[str, list[str]] = field(default_factory=dict)
    meta: dict[str, str] = field(default_factory=dict)


@dataclass
class ContactSignals:
    emails: list[str]
    phones: list[str]
    socials: list[str]
    addresses: list[str] = field(default_factory=list)


@dataclass
class BrandAssets:
    brand_logo: str = ""
    favicon: str = ""
    touch_icon: str = ""
    social_image: str = ""
    manifest_url: str = ""
    mask_icon: str = ""
    tile_image: str = ""
    candidates: list[str] = field(default_factory=list)


@dataclass
class AssetCandidate:
    url: str
    asset_type: str
    source: str
    page_type: str = "general"
    page_url: str = ""


@dataclass
class SiteSignals:
    technologies: list[str]
    currencies: list[str]
    cta_texts: list[str]
    faq_highlights: list[str]
    entity_labels: list[str]
    page_mix: list[str]
    pricing_signals: list[str]
    brand_assets: BrandAssets = field(default_factory=BrandAssets)
    logo_url: str = ""


@dataclass
class CrawlMeta:
    status: str
    fetch_strategy: str
    page_limit: int
    depth_limit: int
    pages_visited: int
    pages_succeeded: int
    pages_failed: int
    sitemap_urls: list[str] = field(default_factory=list)
    render_modes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class ResearchPackage:
    company_name_candidates: list[str]
    hero_messages: list[str]
    semantic_zones: dict[str, list[str]]
    positioning_signals: list[str]
    offer_signals: list[str]
    service_offers: list[str]
    product_offers: list[str]
    audience_signals: list[str]
    trust_signals: list[str]
    proof_points: list[str]
    conversion_actions: list[str]
    content_topics: list[str]
    seo_signals: list[str]
    geography_signals: list[str]
    language_signals: list[str]
    market_signals: list[str]
    visual_signals: list[str]
    core_value_props: list[str]
    supporting_benefits: list[str]
    proof_claims: list[str]
    audience_claims: list[str]
    cta_claims: list[str]
    evidence_blocks: list[dict[str, Any]]


@dataclass
class CrawlBundle:
    website: str
    domain: str
    pages: list[PageSnapshot]
    notes: list[str]
    contact_signals: ContactSignals
    site_signals: SiteSignals
    crawl_meta: CrawlMeta
    research_package: ResearchPackage

    @property
    def primary_page(self) -> PageSnapshot:
        return self.pages[0]


def normalize_url(url: str) -> str:
    value = url.strip()

    if not value:
        raise ValueError("Website adresi gerekli.")

    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"

    parsed = urlparse(value)
    if not parsed.netloc:
        raise ValueError("Website adresi geçersiz.")

    path = parsed.path or "/"
    cleaned = parsed._replace(fragment="", query="", path=path)
    return urlunparse(cleaned)


def build_selector_config_for_domain(domain: str) -> dict[str, Any]:
    return {
        **SCRAPE_SELECTOR_CONFIG,
        "adaptive": True,
        "adaptive_domain": domain,
        "storage": MongoAdaptiveStorageSystem,
        "storage_args": {
            "url": domain,
        },
    }


class WebsiteAnalysisSpider(ScraplingSpider if ScraplingSpider is not None else object):  # type: ignore[misc]
    name = "website-analysis"
    concurrent_requests = 6
    concurrent_requests_per_domain = 4
    download_delay = 0.15
    max_blocked_retries = 2

    def __init__(
        self,
        *,
        website: str,
        domain: str,
        start_urls: list[str],
        max_pages: int,
        max_depth: int,
        selector_config: dict[str, Any],
        crawldir: Path,
    ):
        self.name = f"website-analysis-{domain.replace('.', '-')}"
        self.start_urls = start_urls
        self.allowed_domains = {domain, f"www.{domain}"}
        self.website = website
        self.domain = domain
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.selector_config = selector_config
        self._emitted_pages: set[str] = set()
        super().__init__(crawldir=crawldir, interval=60.0)

    def configure_sessions(self, manager) -> None:  # type: ignore[override]
        manager.add(
            "fast",
            FetcherSession(
                impersonate=["chrome", "firefox", "safari"],
                stealthy_headers=True,
                timeout=20,
                retries=2,
                retry_delay=1,
                follow_redirects=True,
                verify=should_verify_ssl(),
                headers={"Accept-Language": DEFAULT_ACCEPT_LANGUAGE},
                selector_config=self.selector_config,
            ),
            default=True,
        )
        manager.add(
            "dynamic",
            AsyncDynamicSession(
                headless=True,
                timeout=30000,
                wait_selector="body",
                network_idle=True,
                google_search=True,
                extra_headers={"Accept-Language": DEFAULT_ACCEPT_LANGUAGE},
                blocked_domains=TRACKER_BLOCKLIST,
                selector_config=self.selector_config,
            ),
            lazy=True,
        )
        manager.add(
            "stealth",
            AsyncStealthySession(
                headless=True,
                timeout=45000,
                wait_selector="body",
                network_idle=True,
                google_search=True,
                block_webrtc=True,
                hide_canvas=True,
                solve_cloudflare=True,
                extra_headers={"Accept-Language": DEFAULT_ACCEPT_LANGUAGE},
                blocked_domains=TRACKER_BLOCKLIST,
                selector_config=self.selector_config,
            ),
            lazy=True,
        )

    async def start_requests(self):
        for index, url in enumerate(self.start_urls):
            yield SpiderRequest(
                url,
                sid="fast",
                callback=self.parse,
                priority=max(0, len(self.start_urls) - index),
                meta={"depth": 0},
            )

    async def is_blocked(self, response):  # type: ignore[override]
        return is_blocked_response(response)

    async def retry_blocked_request(self, request, response):  # type: ignore[override]
        retry_request = request.copy()
        if request.sid == "fast":
            retry_request.sid = "dynamic"
        else:
            retry_request.sid = "stealth"
        return retry_request

    async def parse(self, response):
        if len(self._emitted_pages) >= self.max_pages:
            self.pause()
            return

        fetch_mode = map_spider_session_to_fetch_mode(getattr(getattr(response, "request", None), "sid", "fast"))
        page = parse_page(response, fetch_mode=fetch_mode, status_code=getattr(response, "status", 200))
        normalized_url = canonicalize_url(page.url)

        if normalized_url in self._emitted_pages:
            return

        self._emitted_pages.add(normalized_url)
        yield {"kind": "page", "page": serialize_page_snapshot(page)}

        if len(self._emitted_pages) >= self.max_pages:
            self.pause()
            return

        depth = int((getattr(response, "meta", {}) or {}).get("depth", 0))
        if depth >= self.max_depth:
            return

        for index, candidate in enumerate(prioritize_links(page.links, self.domain, page.page_type)):
            yield response.follow(
                candidate,
                sid=choose_spider_session_id(candidate, page),
                callback=self.parse,
                priority=max(1, 12 - index),
                meta={"depth": depth + 1},
            )


async def crawl_website(url: str, max_pages: int = 12, max_depth: int = 2) -> CrawlBundle:
    website = normalize_url(url)
    domain = urlparse(website).netloc.replace("www.", "")

    if SCRAPLING_FETCHERS_AVAILABLE and FetcherSession is not None:
        if (
            os.getenv("SCRAPLING_ENABLE_SPIDER", "false").lower() in {"1", "true", "yes"}
            and SCRAPLING_SPIDERS_AVAILABLE
            and ScraplingSpider is not None
            and SpiderRequest is not None
        ):
            try:
                return await crawl_with_scrapling_spider(
                    website,
                    domain,
                    max_pages=max_pages,
                    max_depth=max_depth,
                )
            except Exception as exc:
                fallback_bundle = await crawl_with_scrapling(
                    website,
                    domain,
                    max_pages=max_pages,
                    max_depth=max_depth,
                )
                fallback_bundle.notes.insert(
                    0,
                    f"WARN: Scrapling Spider akışı başarısız oldu, fetcher kuyruğu ile devam edildi. Neden: {exc}",
                )
                fallback_bundle.notes = standardize_crawl_notes(fallback_bundle.notes)
                fallback_bundle.crawl_meta.notes = fallback_bundle.notes
                return fallback_bundle
        return await crawl_with_scrapling(website, domain, max_pages=max_pages, max_depth=max_depth)

    fallback_note = "INFO: Scrapling fetcher katmanı kullanılamadı, selector tabanlı yedek akış kullanıldı."
    if SCRAPLING_FETCHERS_ERROR:
        fallback_note = f"{fallback_note} Neden: {SCRAPLING_FETCHERS_ERROR}"

    bundle = await crawl_with_httpx_fallback(website, domain, max_pages=max_pages, max_depth=max_depth)
    bundle.notes.insert(0, fallback_note)
    bundle.notes = standardize_crawl_notes(bundle.notes)
    bundle.crawl_meta.notes = bundle.notes
    return bundle


async def crawl_with_scrapling_spider(website: str, domain: str, max_pages: int, max_depth: int) -> CrawlBundle:
    selector_config = build_selector_config_for_domain(domain)

    seed_session = FetcherSession(  # type: ignore[operator]
        impersonate=["chrome", "firefox", "safari"],
        stealthy_headers=True,
        timeout=20,
        retries=2,
        retry_delay=1,
        follow_redirects=True,
        verify=should_verify_ssl(),
        headers={"Accept-Language": DEFAULT_ACCEPT_LANGUAGE},
        selector_config=selector_config,
    )

    async with seed_session as static_session:
        sitemap_urls = await discover_sitemap_urls_scrapling(static_session, website, domain)

    start_urls = unique_ordered([website, *sitemap_urls[: max_pages * 4]])[: max_pages * 5]
    crawldir = Path(__file__).resolve().parents[2] / "data" / "spider_checkpoints" / domain.replace(".", "_")
    crawldir.mkdir(parents=True, exist_ok=True)

    spider = WebsiteAnalysisSpider(
        website=website,
        domain=domain,
        start_urls=start_urls,
        max_pages=max_pages,
        max_depth=max_depth,
        selector_config=selector_config,
        crawldir=crawldir,
    )

    notes: list[str] = ["INFO: Scrapling Spider akışı etkin."]
    result = await asyncio.to_thread(spider.start)
    pages = [
        deserialize_page_snapshot(item.get("page", {}))
        for item in result.items
        if isinstance(item, dict) and item.get("kind") == "page" and isinstance(item.get("page"), dict)
    ][:max_pages]
    spider_stats = result.stats.to_dict()

    if not pages:
        raise ValueError("Scrapling Spider okunabilir HTML sayfası üretemedi.")

    notes.append(
        "INFO: Spider istatistikleri -> istek: {requests}, bloklu: {blocked}, başarısız: {failed}.".format(
            requests=int(spider_stats.get("requests_count", len(pages))),
            blocked=int(spider_stats.get("blocked_requests_count", 0)),
            failed=int(spider_stats.get("failed_requests_count", 0)),
        )
    )

    brand_assets, asset_notes = await discover_brand_assets(website, pages)
    notes.extend(asset_notes)

    return build_bundle(
        website,
        domain,
        pages,
        notes,
        fetch_strategy="scrapling-spider",
        page_limit=max_pages,
        depth_limit=max_depth,
        pages_visited=max(int(spider_stats.get("requests_count", len(pages))), len(pages)),
        pages_failed=int(spider_stats.get("failed_requests_count", 0)),
        sitemap_urls=sitemap_urls,
        brand_assets=brand_assets,
    )


async def crawl_with_scrapling(website: str, domain: str, max_pages: int, max_depth: int) -> CrawlBundle:
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(website, 0)])
    pages: list[PageSnapshot] = []
    notes: list[str] = []
    failures = 0

    selector_config = build_selector_config_for_domain(domain)

    static_session_manager = FetcherSession(  # type: ignore[operator]
        impersonate=["chrome", "firefox", "safari"],
        stealthy_headers=True,
        timeout=20,
        retries=2,
        retry_delay=1,
        follow_redirects=True,
        verify=should_verify_ssl(),
        headers={"Accept-Language": DEFAULT_ACCEPT_LANGUAGE},
        selector_config=selector_config,
    )

    async with static_session_manager as static_session:
        sitemap_urls = await discover_sitemap_urls_scrapling(static_session, website, domain)
        for sitemap_url in sitemap_urls[: max_pages * 4]:
            queue.append((sitemap_url, 1))

        while queue and len(pages) < max_pages:
            current_url, depth = queue.popleft()
            normalized = canonicalize_url(current_url)

            if normalized in visited:
                continue

            visited.add(normalized)

            try:
                response, fetch_mode, fetch_notes = await fetch_with_best_effort(
                    static_session,
                    current_url,
                    selector_config=selector_config,
                )
            except Exception as exc:
                failures += 1
                notes.append(f"ERROR: {current_url} taranamadı: {exc}")
                continue

            notes.extend(fetch_notes)

            if not looks_like_html_response(response):
                continue

            page = parse_page(response, fetch_mode=fetch_mode)
            pages.append(page)

            if depth >= max_depth:
                continue

            for candidate in prioritize_links(page.links, domain, page.page_type):
                candidate_normalized = canonicalize_url(candidate)
                if candidate_normalized not in visited:
                    queue.append((candidate, depth + 1))

    if not pages:
        raise ValueError("Verilen adresten okunabilir HTML sayfası çekilemedi.")

    brand_assets, asset_notes = await discover_brand_assets(website, pages)
    notes.extend(asset_notes)

    return build_bundle(
        website,
        domain,
        pages,
        notes,
        fetch_strategy="scrapling-escalation",
        page_limit=max_pages,
        depth_limit=max_depth,
        pages_visited=len(visited),
        pages_failed=failures,
        sitemap_urls=sitemap_urls,
        brand_assets=brand_assets,
    )


async def crawl_with_httpx_fallback(website: str, domain: str, max_pages: int, max_depth: int) -> CrawlBundle:
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(website, 0)])
    pages: list[PageSnapshot] = []
    notes: list[str] = []
    failures = 0

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=20.0,
        verify=should_verify_ssl(),
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept-Language": DEFAULT_ACCEPT_LANGUAGE,
        },
    ) as client:
        sitemap_urls = await discover_sitemap_urls_httpx(client, website, domain)
        for sitemap_url in sitemap_urls[: max_pages * 3]:
            queue.append((sitemap_url, 1))

        while queue and len(pages) < max_pages:
            current_url, depth = queue.popleft()
            normalized = canonicalize_url(current_url)

            if normalized in visited:
                continue

            visited.add(normalized)

            try:
                response = await client.get(current_url)
                response.raise_for_status()
            except Exception as exc:
                failures += 1
                notes.append(f"ERROR: {current_url} çekilemedi: {exc}")
                continue

            if not looks_like_html_httpx(response):
                continue

            selector = Selector(
                response.text,
                url=str(response.url),
                adaptive=True,
                storage=MongoAdaptiveStorageSystem,
                storage_args={
                    "url": domain,
                },
            )
            page = parse_page(selector, fetch_mode="httpx-selector", status_code=response.status_code)
            pages.append(page)

            if depth >= max_depth:
                continue

            for candidate in prioritize_links(page.links, domain, page.page_type):
                candidate_normalized = canonicalize_url(candidate)
                if candidate_normalized not in visited:
                    queue.append((candidate, depth + 1))

    if not pages:
        raise ValueError("Verilen adresten okunabilir HTML sayfası çekilemedi.")

    brand_assets, asset_notes = await discover_brand_assets(website, pages)
    notes.extend(asset_notes)

    return build_bundle(
        website,
        domain,
        pages,
        notes,
        fetch_strategy="httpx-selector-fallback",
        page_limit=max_pages,
        depth_limit=max_depth,
        pages_visited=len(visited),
        pages_failed=failures,
        sitemap_urls=sitemap_urls,
        brand_assets=brand_assets,
    )


async def fetch_with_best_effort(
    static_session: Any,
    url: str,
    *,
    selector_config: dict[str, Any],
) -> tuple[Any, str, list[str]]:
    notes: list[str] = []
    static_response = await static_session.get(url)
    best_response = static_response
    best_mode = "static"

    if is_blocked_response(static_response):
        notes.append(f"{url} için korumalı yanıt algılandı, tarayıcı katmanına yükseltildi.")
        dynamic_response = await try_dynamic_fetch(url, selector_config=selector_config)
        if dynamic_response is not None:
            return dynamic_response, "dynamic", notes

        stealth_response = await try_stealth_fetch(url, selector_config=selector_config)
        if stealth_response is not None:
            return stealth_response, "stealth", notes

        return best_response, best_mode, notes

    if needs_browser_render(static_response):
        dynamic_response = await try_dynamic_fetch(url, selector_config=selector_config)
        if dynamic_response is not None and response_quality_score(dynamic_response) > response_quality_score(static_response):
            notes.append(f"{url} için dinamik render daha zengin içerik döndürdü.")
            best_response = dynamic_response
            best_mode = "dynamic"
        else:
            stealth_response = await try_stealth_fetch(url, selector_config=selector_config)
            if stealth_response is not None and response_quality_score(stealth_response) > response_quality_score(best_response):
                notes.append(f"{url} için stealth render daha zengin içerik döndürdü.")
                best_response = stealth_response
                best_mode = "stealth"

    return best_response, best_mode, notes


async def try_dynamic_fetch(url: str, *, selector_config: dict[str, Any]) -> Any | None:
    if AsyncDynamicSession is None:
        return None

    try:
        async with AsyncDynamicSession(
            headless=True,
            timeout=30000,
            wait_selector="body",
            network_idle=True,
            google_search=True,
            extra_headers={"Accept-Language": DEFAULT_ACCEPT_LANGUAGE},
            blocked_domains=TRACKER_BLOCKLIST,
            selector_config=selector_config,
        ) as session:
            return await session.fetch(url)
    except Exception:
        return None


async def try_stealth_fetch(url: str, *, selector_config: dict[str, Any]) -> Any | None:
    if AsyncStealthySession is None:
        return None

    try:
        async with AsyncStealthySession(
            headless=True,
            timeout=45000,
            wait_selector="body",
            network_idle=True,
            google_search=True,
            block_webrtc=True,
            hide_canvas=True,
            solve_cloudflare=True,
            extra_headers={"Accept-Language": DEFAULT_ACCEPT_LANGUAGE},
            blocked_domains=TRACKER_BLOCKLIST,
            selector_config=selector_config,
        ) as session:
            return await session.fetch(url)
    except Exception:
        return None


async def discover_sitemap_urls_scrapling(static_session: Any, website: str, domain: str) -> list[str]:
    sitemap_candidates = [urljoin(website, "/sitemap.xml")]
    discovered: list[str] = []

    try:
        robots = await static_session.get(urljoin(website, "/robots.txt"))
        if getattr(robots, "status", 0) == 200:
            body_text = safe_decode(getattr(robots, "body", b""))
            for line in body_text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_candidates.append(line.split(":", 1)[1].strip())
    except Exception:
        pass

    for sitemap_url in unique_ordered(sitemap_candidates)[:4]:
        try:
            response = await static_session.get(sitemap_url)
        except Exception:
            continue

        xml_text = safe_decode(getattr(response, "body", b""))
        discovered.extend(prioritize_links(re.findall(r"<loc>(.*?)</loc>", xml_text), domain))

    return unique_ordered(discovered)


async def discover_sitemap_urls_httpx(client: httpx.AsyncClient, website: str, domain: str) -> list[str]:
    sitemap_candidates = [urljoin(website, "/sitemap.xml")]
    discovered: list[str] = []

    try:
        robots = await client.get(urljoin(website, "/robots.txt"))
        if robots.is_success:
            for line in robots.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_candidates.append(line.split(":", 1)[1].strip())
    except Exception:
        pass

    for sitemap_url in unique_ordered(sitemap_candidates)[:4]:
        try:
            response = await client.get(sitemap_url)
            response.raise_for_status()
        except Exception:
            continue

        discovered.extend(prioritize_links(re.findall(r"<loc>(.*?)</loc>", response.text), domain))

    return unique_ordered(discovered)


def choose_spider_session_id(url: str, page: PageSnapshot) -> str:
    path = urlparse(url).path.lower()
    if any(token in path for token in ("login", "signin", "register", "account", "checkout")):
        return "stealth"
    if page.fetch_mode in {"dynamic", "stealth"}:
        return page.fetch_mode
    if any(token in path for token in ("analysis", "tool", "contact", "faq", "pricing", "demo", "app")):
        return "dynamic"
    return "fast"


def map_spider_session_to_fetch_mode(session_id: str) -> str:
    if session_id == "dynamic":
        return "dynamic"
    if session_id == "stealth":
        return "stealth"
    return "static"


def serialize_page_snapshot(page: PageSnapshot) -> dict[str, Any]:
    return asdict(page)


def deserialize_page_snapshot(payload: dict[str, Any]) -> PageSnapshot:
    faq_items = [
        FaqItem(
            question=clean_text(str(item.get("question", ""))),
            answer=clean_text(str(item.get("answer", ""))),
        )
        for item in payload.get("faq_items", [])
        if isinstance(item, dict)
    ]
    forms = [
        FormSnapshot(
            action=clean_text(str(item.get("action", ""))),
            method=clean_text(str(item.get("method", ""))) or "GET",
            fields=[clean_text(str(field)) for field in item.get("fields", []) if clean_text(str(field))],
        )
        for item in payload.get("forms", [])
        if isinstance(item, dict)
    ]
    return PageSnapshot(
        url=clean_text(str(payload.get("url", ""))),
        title=clean_text(str(payload.get("title", ""))),
        description=clean_text(str(payload.get("description", ""))),
        headings=[clean_text(str(value)) for value in payload.get("headings", []) if clean_text(str(value))],
        excerpt=clean_text(str(payload.get("excerpt", ""))),
        raw_text=clean_text(str(payload.get("raw_text", ""))),
        links=[clean_text(str(value)) for value in payload.get("links", []) if clean_text(str(value))],
        structured_data=[clean_text(str(value)) for value in payload.get("structured_data", []) if clean_text(str(value))],
        page_type=clean_text(str(payload.get("page_type", ""))) or "general",
        fetch_mode=clean_text(str(payload.get("fetch_mode", ""))) or "static",
        status_code=int(payload.get("status_code", 200) or 200),
        main_content=clean_text(str(payload.get("main_content", ""))),
        cta_texts=[clean_text(str(value)) for value in payload.get("cta_texts", []) if clean_text(str(value))],
        value_props=[clean_text(str(value)) for value in payload.get("value_props", []) if clean_text(str(value))],
        nav_labels=[clean_text(str(value)) for value in payload.get("nav_labels", []) if clean_text(str(value))],
        pricing_signals=[clean_text(str(value)) for value in payload.get("pricing_signals", []) if clean_text(str(value))],
        faq_items=faq_items,
        forms=forms,
        entity_labels=[clean_text(str(value)) for value in payload.get("entity_labels", []) if clean_text(str(value))],
        image_alts=[clean_text(str(value)) for value in payload.get("image_alts", []) if clean_text(str(value))],
        logo_candidates=[clean_text(str(value)) for value in payload.get("logo_candidates", []) if clean_text(str(value))],
        technologies=[clean_text(str(value)) for value in payload.get("technologies", []) if clean_text(str(value))],
        currencies=[clean_text(str(value)) for value in payload.get("currencies", []) if clean_text(str(value))],
        hero_messages=[clean_text(str(value)) for value in payload.get("hero_messages", []) if clean_text(str(value))],
        trust_signals=[clean_text(str(value)) for value in payload.get("trust_signals", []) if clean_text(str(value))],
        audience_signals=[clean_text(str(value)) for value in payload.get("audience_signals", []) if clean_text(str(value))],
        proof_points=[clean_text(str(value)) for value in payload.get("proof_points", []) if clean_text(str(value))],
        zones={
            key: [clean_text(str(value)) for value in values if clean_text(str(value))]
            for key, values in payload.get("zones", {}).items()
            if isinstance(values, list)
        }
        if isinstance(payload.get("zones"), dict)
        else {},
        meta={
            str(key): clean_text(str(value))
            for key, value in payload.get("meta", {}).items()
            if clean_text(str(value))
        }
        if isinstance(payload.get("meta"), dict)
        else {},
    )


async def discover_brand_assets(website: str, pages: list[PageSnapshot]) -> tuple[BrandAssets, list[str]]:
    notes: list[str] = []
    asset_candidates = collect_asset_candidates(website, pages)
    manifest_url = choose_manifest_url(pages)

    if manifest_url:
        manifest_candidates, manifest_notes = await fetch_manifest_asset_candidates(manifest_url)
        asset_candidates.extend(manifest_candidates)
        notes.extend(manifest_notes)

    brand_assets = build_brand_assets(website, asset_candidates, manifest_url)

    if brand_assets.brand_logo:
        notes.append(f"INFO: Marka logosu tespit edildi: {brand_assets.brand_logo}")
    elif brand_assets.favicon:
        notes.append(f"INFO: Doğrudan logo bulunamadı, favicon kullanıma hazır: {brand_assets.favicon}")
    else:
        notes.append("WARN: Marka logosu veya favicon güvenilir şekilde ayrıştırılamadı.")

    return brand_assets, unique_ordered(notes)


def collect_asset_candidates(website: str, pages: list[PageSnapshot]) -> list[AssetCandidate]:
    candidates: list[AssetCandidate] = []

    def add_candidate(
        page: PageSnapshot,
        raw_value: str,
        asset_type: str,
        source: str,
    ) -> None:
        resolved = resolve_asset_url(page.url, raw_value)
        if not resolved:
            return
        candidates.append(
            AssetCandidate(
                url=resolved,
                asset_type=asset_type,
                source=source,
                page_type=page.page_type,
                page_url=page.url,
            )
        )

    for page in pages:
        add_candidate(page, page.meta.get("icon", ""), "favicon", "meta_icon")
        add_candidate(page, page.meta.get("shortcutIcon", ""), "favicon", "meta_shortcut_icon")
        add_candidate(page, page.meta.get("appleTouchIcon", ""), "touch_icon", "meta_apple_touch_icon")
        add_candidate(
            page,
            page.meta.get("appleTouchIconPrecomposed", ""),
            "touch_icon",
            "meta_apple_touch_precomposed",
        )
        add_candidate(page, page.meta.get("maskIcon", ""), "mask_icon", "meta_mask_icon")
        add_candidate(page, page.meta.get("msTileImage", ""), "tile_image", "meta_ms_tile_image")
        add_candidate(page, page.meta.get("ogImage", ""), "social_image", "meta_og_image")
        add_candidate(page, page.meta.get("twitterImage", ""), "social_image", "meta_twitter_image")

        for candidate in page.logo_candidates:
            add_candidate(page, candidate, "brand_logo", "dom_logo")

    favicon_fallback = resolve_asset_url(website, "/favicon.ico")
    if favicon_fallback:
        candidates.append(
            AssetCandidate(
                url=favicon_fallback,
                asset_type="favicon",
                source="root_favicon",
                page_type="home",
                page_url=website,
            )
        )

    return dedupe_asset_candidates(candidates)


def dedupe_asset_candidates(candidates: list[AssetCandidate]) -> list[AssetCandidate]:
    deduped: dict[tuple[str, str, str], AssetCandidate] = {}
    for candidate in candidates:
        key = (
            canonicalize_url(candidate.url),
            candidate.asset_type,
            candidate.source,
        )
        deduped[key] = candidate
    return list(deduped.values())


def choose_manifest_url(pages: list[PageSnapshot]) -> str:
    manifest_candidates: list[str] = []
    for page in pages:
        manifest_value = page.meta.get("manifest", "")
        resolved = resolve_asset_url(page.url, manifest_value)
        if resolved:
            manifest_candidates.append(resolved)
    unique_candidates = unique_ordered(manifest_candidates)
    return unique_candidates[0] if unique_candidates else ""


async def fetch_manifest_asset_candidates(manifest_url: str) -> tuple[list[AssetCandidate], list[str]]:
    notes: list[str] = []
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=8.0,
            verify=should_verify_ssl(),
            headers={"Accept-Language": DEFAULT_ACCEPT_LANGUAGE},
        ) as client:
            response = await client.get(manifest_url)
            response.raise_for_status()
    except Exception as exc:
        return [], [f"INFO: Web manifest okunamadı: {exc}"]

    try:
        manifest_data = response.json()
    except Exception as exc:
        return [], [f"INFO: Web manifest çözümlenemedi: {exc}"]

    if not isinstance(manifest_data, dict):
        return [], []

    candidates: list[AssetCandidate] = []
    for item in manifest_data.get("icons", []):
        if not isinstance(item, dict):
            continue

        src = clean_text(str(item.get("src", "")))
        resolved = resolve_asset_url(manifest_url, src)
        if not resolved:
            continue

        purpose = clean_text(str(item.get("purpose", ""))).lower()
        sizes = clean_text(str(item.get("sizes", ""))).lower()
        asset_type = "favicon"
        if "maskable" in purpose or "monochrome" in purpose:
            asset_type = "touch_icon"
        elif any(size in sizes for size in ("512x512", "256x256", "192x192", "180x180")):
            asset_type = "touch_icon"

        candidates.append(
            AssetCandidate(
                url=resolved,
                asset_type=asset_type,
                source="manifest_icon",
                page_type="home",
                page_url=manifest_url,
            )
        )

    if candidates:
        notes.append("INFO: Web manifest içindeki ikon seti işlendi.")

    return dedupe_asset_candidates(candidates), notes


def build_brand_assets(
    website: str,
    candidates: list[AssetCandidate],
    manifest_url: str = "",
) -> BrandAssets:
    brand_logo = choose_best_asset_url(candidates, "brand_logo")
    favicon = choose_best_asset_url(candidates, "favicon")
    touch_icon = choose_best_asset_url(candidates, "touch_icon")
    social_image = choose_best_asset_url(candidates, "social_image")
    mask_icon = choose_best_asset_url(candidates, "mask_icon")
    tile_image = choose_best_asset_url(candidates, "tile_image")

    if not brand_logo:
        brand_logo = favicon or touch_icon or social_image

    ordered_candidates = sorted(
        candidates,
        key=lambda item: score_asset_candidate(item, item.asset_type),
        reverse=True,
    )

    return BrandAssets(
        brand_logo=brand_logo,
        favicon=favicon,
        touch_icon=touch_icon,
        social_image=social_image,
        manifest_url=manifest_url,
        mask_icon=mask_icon,
        tile_image=tile_image,
        candidates=unique_ordered([item.url for item in ordered_candidates])[:16],
    )


def choose_brand_assets(pages: list[PageSnapshot]) -> BrandAssets:
    return build_brand_assets(pages[0].url if pages else "", collect_asset_candidates(pages[0].url if pages else "", pages))


def choose_best_asset_url(candidates: list[AssetCandidate], target_type: str) -> str:
    if not candidates:
        return ""

    scored: dict[str, tuple[int, AssetCandidate]] = {}
    for candidate in candidates:
        score = score_asset_candidate(candidate, target_type)
        existing = scored.get(candidate.url)
        if existing is None or score > existing[0]:
            scored[candidate.url] = (score, candidate)

    if not scored:
        return ""

    best_score, best_candidate = max(scored.values(), key=lambda item: item[0])
    if best_score <= 0:
        return ""
    return best_candidate.url


def score_asset_candidate(candidate: AssetCandidate, target_type: str) -> int:
    lower_url = candidate.url.lower()
    lower_source = candidate.source.lower()
    score = 0

    if candidate.asset_type == target_type:
        score += 40
    elif target_type == "brand_logo" and candidate.asset_type in {"favicon", "touch_icon"}:
        score += 12
    elif target_type == "favicon" and candidate.asset_type == "touch_icon":
        score += 10

    if candidate.page_type in {"home", "about", "general"}:
        score += 10

    if lower_source == "dom_logo":
        score += 28
    elif lower_source.startswith("meta_"):
        score += 18
    elif lower_source == "manifest_icon":
        score += 15
    elif lower_source == "root_favicon":
        score += 6

    if "logo" in lower_url:
        score += 22
    if "brand" in lower_url:
        score += 14
    if "navbar" in lower_url or "header" in lower_url or "nav" in lower_url:
        score += 10
    if "favicon" in lower_url:
        score += 18 if target_type == "favicon" else -8
    if "apple-touch" in lower_url or "touch-icon" in lower_url:
        score += 18 if target_type == "touch_icon" else -6
    if "mask" in lower_url:
        score += 14 if target_type == "mask_icon" else -4
    if "tile" in lower_url:
        score += 14 if target_type == "tile_image" else -4
    if any(token in lower_url for token in ("og-image", "social", "share", "banner", "hero", "cover")):
        score += 20 if target_type == "social_image" else -24

    if lower_url.endswith(".svg"):
        score += 12 if target_type == "brand_logo" else 4
    elif lower_url.endswith(".ico"):
        score += 14 if target_type == "favicon" else 3
    elif lower_url.endswith(".png"):
        score += 7
    elif lower_url.endswith(".webp"):
        score += 6

    return score


def parse_page(page: Selector, fetch_mode: str, status_code: int | None = None) -> PageSnapshot:
    title = clean_text(page.css("title::text").get(default=""))
    description = clean_text(
        page.css("meta[name='description']::attr(content)").get(default="")
        or page.css("meta[property='og:description']::attr(content)").get(default="")
        or page.css("meta[name='twitter:description']::attr(content)").get(default="")
    )
    headings = unique_ordered(
        [
            clean_text(value)
            for value in page.css("h1::text, h2::text, h3::text").getall()
            if clean_text(value)
        ]
    )[:14]
    main_content = extract_main_content(page)
    raw_text = clean_text(
        main_content
        or " ".join(page.xpath("//body//text()[normalize-space()]").getall())
    )[:20000]
    excerpt = raw_text[:2200]
    links = unique_ordered(
        [
            urljoin(page.url, href)
            for href in page.css("a::attr(href)").getall()
            if href and not href.startswith(("mailto:", "tel:", "javascript:", "#"))
        ]
    )

    structured_data, faq_items, structured_entities = extract_structured_data(page)
    cta_texts = extract_cta_texts(page)
    nav_labels = extract_nav_labels(page)
    pricing_signals = extract_pricing_signals(page, raw_text)
    forms = extract_forms(page)
    hero_messages = extract_hero_messages(page)
    trust_signals = extract_trust_signals(raw_text)
    audience_signals = extract_audience_signals(raw_text, headings, nav_labels)
    proof_points = extract_proof_points(raw_text, trust_signals)
    zones = extract_semantic_zones(
        page,
        raw_text=raw_text,
        page_type=classify_page(page.url, title),
        hero_messages=hero_messages,
        trust_signals=trust_signals,
        audience_signals=audience_signals,
        proof_points=proof_points,
        pricing_signals=pricing_signals,
        faq_items=faq_items,
    )
    value_props = extract_value_props(page, zones)
    entity_labels = unique_ordered(structured_entities + extract_repeated_entities(page))[:12]
    image_alts = unique_ordered(
        [clean_text(alt) for alt in page.css("img::attr(alt)").getall() if clean_text(alt)]
    )[:12]
    logo_candidates = extract_logo_candidates(page)
    meta = extract_meta_tags(page)
    technologies = detect_technologies(page)
    currencies = detect_currencies(pricing_signals, raw_text)
    page_type = classify_page(page.url, title)

    return PageSnapshot(
        url=page.url,
        title=title,
        description=description,
        headings=headings,
        excerpt=excerpt,
        raw_text=raw_text,
        links=links,
        structured_data=structured_data[:8],
        page_type=page_type,
        fetch_mode=fetch_mode,
        status_code=status_code or getattr(page, "status", 200),
        main_content=main_content[:6000],
        cta_texts=cta_texts[:10],
        value_props=value_props[:10],
        nav_labels=nav_labels[:16],
        pricing_signals=pricing_signals[:10],
        faq_items=faq_items[:8],
        forms=forms[:6],
        entity_labels=entity_labels[:12],
        image_alts=image_alts,
        logo_candidates=logo_candidates[:12],
        technologies=technologies[:8],
        currencies=currencies[:5],
        hero_messages=hero_messages[:8],
        trust_signals=trust_signals[:8],
        audience_signals=audience_signals[:8],
        proof_points=proof_points[:8],
        zones={key: values[:8] for key, values in zones.items()},
        meta=meta,
    )


def build_bundle(
    website: str,
    domain: str,
    pages: list[PageSnapshot],
    notes: list[str],
    fetch_strategy: str,
    page_limit: int,
    depth_limit: int,
    pages_visited: int,
    pages_failed: int,
    sitemap_urls: list[str],
    brand_assets: BrandAssets | None = None,
) -> CrawlBundle:
    full_text = "\n".join(page.raw_text for page in pages)
    contact_signals = ContactSignals(
        emails=sorted(set(EMAIL_PATTERN.findall(full_text)))[:10],
        phones=sorted(normalize_phones(PHONE_PATTERN.findall(full_text)))[:10],
        socials=sorted(
            {
                link
                for page in pages
                for link in page.links
                if any(host in link for host in SOCIAL_HOSTS)
            }
        )[:10],
        addresses=extract_address_candidates(pages),
    )

    site_signals = build_site_signals(pages, brand_assets=brand_assets)
    research_package = build_research_package(website, domain, pages, contact_signals, site_signals)
    clean_notes = standardize_crawl_notes(notes)
    pages_succeeded = len(pages)
    render_modes = unique_ordered([page.fetch_mode for page in pages if page.fetch_mode])[:6]
    crawl_status = "partial" if pages_failed or pages_visited > pages_succeeded else "completed"
    crawl_meta = CrawlMeta(
        status=crawl_status,
        fetch_strategy=fetch_strategy,
        page_limit=page_limit,
        depth_limit=depth_limit,
        pages_visited=pages_visited,
        pages_succeeded=pages_succeeded,
        pages_failed=pages_failed,
        sitemap_urls=unique_ordered([canonicalize_url(url) for url in sitemap_urls if url])[:20],
        render_modes=render_modes,
        notes=clean_notes,
    )

    return CrawlBundle(
        website=website,
        domain=domain,
        pages=pages,
        notes=clean_notes,
        contact_signals=contact_signals,
        site_signals=site_signals,
        crawl_meta=crawl_meta,
        research_package=research_package,
    )


def build_site_signals(pages: list[PageSnapshot], brand_assets: BrandAssets | None = None) -> SiteSignals:
    technologies = unique_ordered([tech for page in pages for tech in page.technologies])[:12]
    currencies = unique_ordered([currency for page in pages for currency in page.currencies])[:8]
    cta_texts = unique_ordered([cta for page in pages for cta in page.cta_texts])[:16]
    faq_highlights = unique_ordered(
        [f"{faq.question} -> {faq.answer[:140]}" for page in pages for faq in page.faq_items if faq.question and faq.answer]
    )[:10]
    entity_labels = unique_ordered([label for page in pages for label in page.entity_labels])[:18]
    pricing_signals = unique_ordered([price for page in pages for price in page.pricing_signals])[:12]
    page_counter = Counter(page.page_type for page in pages)
    page_mix = [f"{page_type}: {count}" for page_type, count in page_counter.most_common()]
    resolved_brand_assets = brand_assets or choose_brand_assets(pages)
    logo_url = resolved_brand_assets.brand_logo or resolved_brand_assets.favicon or choose_logo_url(pages)

    return SiteSignals(
        technologies=technologies,
        currencies=currencies,
        cta_texts=cta_texts,
        faq_highlights=faq_highlights,
        entity_labels=entity_labels,
        page_mix=page_mix,
        pricing_signals=pricing_signals,
        brand_assets=resolved_brand_assets,
        logo_url=logo_url,
    )


def build_research_package(
    website: str,
    domain: str,
    pages: list[PageSnapshot],
    contact_signals: ContactSignals,
    site_signals: SiteSignals,
) -> ResearchPackage:
    company_name_candidates = infer_company_name_candidates(pages, domain)
    hero_messages = unique_ordered([message for page in pages for message in page.hero_messages])[:12]
    semantic_zones = build_semantic_zone_summary(pages)
    inferred_service_offers, inferred_product_offers = infer_offer_buckets(pages)
    service_offers = clean_signal_list(
        collect_offer_labels(pages, {"service"}) + inferred_service_offers,
        min_len=4,
        max_len=120,
    )[:14]
    product_offers = clean_signal_list(
        collect_offer_labels(pages, {"product"}) + inferred_product_offers,
        min_len=4,
        max_len=120,
    )[:14]
    core_value_props = build_core_value_props(pages, semantic_zones)
    supporting_benefits = build_supporting_benefits(pages, semantic_zones)
    proof_claims = build_proof_claims(pages, semantic_zones)
    audience_claims = build_audience_claims(pages, semantic_zones)
    cta_claims = build_cta_claims(pages, site_signals)
    evidence_blocks = build_evidence_blocks(
        pages,
        core_value_props=core_value_props,
        supporting_benefits=supporting_benefits,
        proof_claims=proof_claims,
        audience_claims=audience_claims,
    )
    offer_signals = clean_signal_list(
        [
            *hero_messages,
            *core_value_props,
            *supporting_benefits,
            *[label for page in pages for label in page.entity_labels],
            *[heading for page in pages for heading in page.headings],
        ],
        min_len=12,
        max_len=220,
    )[:18]
    audience_signals = clean_signal_list(
        [value for page in pages for value in page.audience_signals],
        min_len=12,
        max_len=180,
    )[:14]
    trust_signals = clean_signal_list(
        [value for page in pages for value in page.trust_signals],
        min_len=12,
        max_len=180,
    )[:14]
    proof_points = clean_signal_list(
        [value for page in pages for value in page.proof_points],
        min_len=12,
        max_len=180,
    )[:12]
    conversion_actions = build_conversion_actions(pages, site_signals, contact_signals)
    content_topics = build_content_topics(pages)
    seo_signals = build_seo_signals(pages)
    geography_signals = build_geography_signals(website, domain, contact_signals)
    language_signals = build_language_signals(website, pages)
    market_signals = build_market_signals(site_signals, pages)
    visual_signals = build_visual_signals(pages, site_signals)
    positioning_signals = build_positioning_signals(
        hero_messages=hero_messages,
        core_value_props=core_value_props,
        service_offers=service_offers,
        product_offers=product_offers,
        pages=pages,
        contact_signals=contact_signals,
        site_signals=site_signals,
    )

    return ResearchPackage(
        company_name_candidates=company_name_candidates,
        hero_messages=hero_messages,
        semantic_zones=semantic_zones,
        positioning_signals=positioning_signals,
        offer_signals=offer_signals,
        service_offers=service_offers,
        product_offers=product_offers,
        audience_signals=audience_signals,
        trust_signals=trust_signals,
        proof_points=proof_points,
        conversion_actions=conversion_actions,
        content_topics=content_topics,
        seo_signals=seo_signals,
        geography_signals=geography_signals,
        language_signals=language_signals,
        market_signals=market_signals,
        visual_signals=visual_signals,
        core_value_props=core_value_props,
        supporting_benefits=supporting_benefits,
        proof_claims=proof_claims,
        audience_claims=audience_claims,
        cta_claims=cta_claims,
        evidence_blocks=evidence_blocks,
    )


def build_semantic_zone_summary(pages: list[PageSnapshot]) -> dict[str, list[str]]:
    summary: dict[str, list[str]] = {
        "hero": [],
        "offers": [],
        "proof": [],
        "pricing": [],
        "faq": [],
        "contact": [],
    }

    for page in pages:
        for zone_name, values in page.zones.items():
            if zone_name not in summary:
                summary[zone_name] = []
            summary[zone_name].extend(values)

    return {
        zone_name: unique_ordered([clean_text(value) for value in values if clean_text(value)])[:12]
        for zone_name, values in summary.items()
    }


def build_core_value_props(pages: list[PageSnapshot], semantic_zones: dict[str, list[str]]) -> list[str]:
    primary = pages[0]
    candidates = unique_ordered(
        [
            *semantic_zones.get("hero", []),
            *semantic_zones.get("offers", []),
            primary.description,
            *primary.headings[:6],
        ]
    )
    return rank_filtered_claim_candidates(candidates, claim_type="value_prop")[:8]


def build_supporting_benefits(pages: list[PageSnapshot], semantic_zones: dict[str, list[str]]) -> list[str]:
    candidates = unique_ordered(
        [
            *semantic_zones.get("offers", []),
            *[value for page in pages for value in page.value_props],
            *[value for page in pages for value in page.headings[1:5]],
        ]
    )
    return rank_filtered_claim_candidates(candidates, claim_type="benefit")[:10]


def build_proof_claims(pages: list[PageSnapshot], semantic_zones: dict[str, list[str]]) -> list[str]:
    candidates = unique_ordered(
        [
            *semantic_zones.get("proof", []),
            *[value for page in pages for value in page.proof_points],
            *[value for page in pages for value in page.trust_signals],
        ]
    )
    return rank_filtered_claim_candidates(candidates, claim_type="proof")[:10]


def build_audience_claims(pages: list[PageSnapshot], semantic_zones: dict[str, list[str]]) -> list[str]:
    candidates = unique_ordered(
        [
            *semantic_zones.get("contact", []),
            *[value for page in pages for value in page.audience_signals],
        ]
    )
    return rank_filtered_claim_candidates(candidates, claim_type="audience")[:10]


def build_cta_claims(pages: list[PageSnapshot], site_signals: SiteSignals) -> list[str]:
    candidates = unique_ordered(
        [
            *[f"CTA: {value}" for value in site_signals.cta_texts],
            *[
                f"{page.page_type} formu: {', '.join(form.fields[:4]) or 'alan bilgisi sınırlı'}"
                for page in pages
                for form in page.forms[:2]
            ],
        ]
    )
    return rank_filtered_claim_candidates(candidates, claim_type="cta")[:10]


def build_evidence_blocks(
    pages: list[PageSnapshot],
    *,
    core_value_props: list[str],
    supporting_benefits: list[str],
    proof_claims: list[str],
    audience_claims: list[str],
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    blocks.extend(
        create_evidence_block("value_prop", claim, pages, why="Hero ve teklif bölgelerinde tekrar eden ana vaat.")
        for claim in core_value_props[:3]
    )
    blocks.extend(
        create_evidence_block("benefit", claim, pages, why="Teklif bölgeleri ve detay sayfalarında desteklenen fayda.")
        for claim in supporting_benefits[:3]
    )
    blocks.extend(
        create_evidence_block("proof", claim, pages, why="Güven ve kanıt katmanlarında görülen destekleyici sinyal.")
        for claim in proof_claims[:3]
    )
    blocks.extend(
        create_evidence_block("audience", claim, pages, why="Hedef kitle veya kullanım senaryosu sinyali.")
        for claim in audience_claims[:3]
    )
    return [block for block in blocks if block.get("claim")]


def create_evidence_block(
    evidence_type: str,
    claim: str,
    pages: list[PageSnapshot],
    *,
    why: str,
) -> dict[str, Any]:
    evidence_urls = find_claim_evidence_urls(claim, pages)
    confidence = min(0.95, 0.48 + (0.12 * len(evidence_urls)))
    return {
        "type": evidence_type,
        "claim": claim,
        "why": why,
        "confidence": round(confidence, 2),
        "evidenceUrls": evidence_urls[:4],
    }


def find_claim_evidence_urls(claim: str, pages: list[PageSnapshot]) -> list[str]:
    claim_tokens = {
        token
        for token in re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9]{4,}", claim.lower())
        if token not in {"with", "from", "your", "that", "this", "have", "more", "site", "page"}
    }
    matched_urls: list[str] = []

    for page in pages:
        haystack = " ".join(
            [
                page.title,
                page.description,
                page.main_content[:2400],
                " ".join(page.headings[:8]),
                " ".join(page.hero_messages[:6]),
                " ".join(page.value_props[:6]),
            ]
        ).lower()
        if not claim_tokens:
            continue
        overlap = sum(1 for token in claim_tokens if token in haystack)
        if overlap >= max(1, min(2, len(claim_tokens))):
            matched_urls.append(page.url)

    return unique_ordered(matched_urls)


def rank_claim_candidates(candidates: list[str], *, claim_type: str) -> list[str]:
    scored: list[tuple[int, str]] = []
    for candidate in candidates:
        text = clean_text(candidate)
        if not text:
            continue
        score = score_claim_candidate(text, claim_type=claim_type)
        if score <= 0:
            continue
        scored.append((score, text))

    scored.sort(key=lambda item: item[0], reverse=True)
    return unique_ordered([text for _, text in scored])


def rank_filtered_claim_candidates(candidates: list[str], *, claim_type: str) -> list[str]:
    return rank_claim_candidates(
        clean_signal_list(
            candidates,
            min_len=12,
            max_len=220,
            allow_cta=claim_type == "cta",
        ),
        claim_type=claim_type,
    )


def score_claim_candidate(text: str, *, claim_type: str) -> int:
    lowered = text.lower()
    if len(text) < 12 or len(text) > 220:
        return 0
    if lowered in GENERIC_TOPIC_TERMS:
        return 0
    if is_low_signal_text(text, allow_cta=claim_type == "cta"):
        return 0
    if any(token in lowered for token in ("cookie", "privacy", "terms", "gizlilik", "çerez", "login", "giriş")):
        return 0

    score = 10
    benefit_tokens = (
        "increase",
        "improve",
        "optimize",
        "scale",
        "automate",
        "track",
        "measure",
        "manage",
        "grow",
        "reduce",
        "save",
        "build",
        "boost",
        "artır",
        "iyileştir",
        "ölç",
        "yönet",
        "otomasyon",
        "takip",
        "büyü",
        "kazan",
        "hızlı",
        "kolay",
        "verim",
    )
    audience_tokens = ("for", "için", "teams", "ekip", "brands", "marka", "business", "işletme", "kobi", "startup")
    proof_tokens = ("client", "müşteri", "trusted", "referans", "award", "ödül", "%", "+", "case", "teknopark")
    cta_tokens = ("cta:", "demo", "start", "book", "contact", "teklif", "başla", "dene", "get")

    if any(token in lowered for token in benefit_tokens):
        score += 18
    if any(token in lowered for token in audience_tokens):
        score += 10
    if any(token in lowered for token in proof_tokens):
        score += 12
    if any(char.isdigit() for char in text):
        score += 6

    if claim_type == "value_prop":
        if any(token in lowered for token in benefit_tokens):
            score += 12
        if any(token in lowered for token in audience_tokens):
            score += 8
    elif claim_type == "benefit":
        if any(token in lowered for token in benefit_tokens):
            score += 16
    elif claim_type == "proof":
        if any(token in lowered for token in proof_tokens):
            score += 18
    elif claim_type == "audience":
        if any(token in lowered for token in audience_tokens):
            score += 18
    elif claim_type == "cta":
        if any(token in lowered for token in cta_tokens):
            score += 22

    return score


def infer_company_name_candidates(pages: list[PageSnapshot], domain: str) -> list[str]:
    primary = pages[0]
    candidates = [
        primary.meta.get("ogSiteName", ""),
        primary.meta.get("ogTitle", ""),
        primary.title.split("|")[0].split("-")[0].strip() if primary.title else "",
        *primary.entity_labels[:4],
    ]
    domain_root = domain.split(".")[0].strip()
    if domain_root:
        candidates.append(" ".join(part.capitalize() for part in domain_root.split("-")))
    return unique_ordered([clean_text(value) for value in candidates if clean_text(value)])[:8]


def collect_offer_labels(pages: list[PageSnapshot], page_types: set[str]) -> list[str]:
    labels: list[str] = []

    for page in pages:
        if page.page_type not in page_types:
            continue
        labels.extend(page.entity_labels)
        labels.extend(page.headings[:6])
        labels.extend(page.value_props[:4])

    cleaned: list[str] = []
    for value in labels:
        text = clean_text(value)
        lower = text.lower()
        if not text or len(text) < 4 or len(text) > 120:
            continue
        if lower in GENERIC_TOPIC_TERMS:
            continue
        if is_low_signal_text(text):
            continue
        cleaned.append(text)

    return unique_ordered(cleaned)[:14]


def infer_offer_buckets(pages: list[PageSnapshot]) -> tuple[list[str], list[str]]:
    service_labels: list[str] = []
    product_labels: list[str] = []

    for page in pages:
        for value in [*page.entity_labels, *page.headings, *page.value_props]:
            text = clean_text(value)
            lower = text.lower()
            if not text or len(text) < 4 or len(text) > 120:
                continue
            if lower in GENERIC_TOPIC_TERMS:
                continue
            if is_low_signal_text(text):
                continue
            service_match = any(token in lower for token in SERVICE_OFFER_HINTS)
            product_match = any(token in lower for token in PRODUCT_OFFER_HINTS)
            if service_match and not product_match:
                service_labels.append(text)
                continue
            if product_match and not service_match:
                product_labels.append(text)
                continue
            if service_match and product_match:
                if any(token in lower for token in ("platform", "tool", "analytics", "erp", "saas", "ürün", "product")):
                    product_labels.append(text)
                else:
                    service_labels.append(text)

    return (
        clean_signal_list(service_labels, min_len=4, max_len=120)[:14],
        clean_signal_list(product_labels, min_len=4, max_len=120)[:14],
    )


def build_positioning_signals(
    hero_messages: list[str],
    core_value_props: list[str],
    service_offers: list[str],
    product_offers: list[str],
    pages: list[PageSnapshot],
    contact_signals: ContactSignals,
    site_signals: SiteSignals,
) -> list[str]:
    signals = list(hero_messages[:3]) + core_value_props[:3]
    primary = pages[0]

    if primary.description:
        signals.append(primary.description)

    if service_offers and product_offers:
        signals.append("Site aynı anda hem hizmet hem ürün/SaaS teklifi sinyali veriyor.")
    elif service_offers:
        signals.append("Teklif yapısı hizmet ve çözüm odaklı görünüyor.")
    elif product_offers:
        signals.append("Teklif yapısı ürün veya SaaS katmanı etrafında şekilleniyor.")

    if contact_signals.emails and (contact_signals.phones or contact_signals.socials):
        signals.append("Birden fazla temas kanalı güven ve dönüşüm için kullanılabilir durumda.")

    if site_signals.pricing_signals:
        signals.append("Fiyat veya planlama sinyalleri ziyaretçiye değer çerçevesi sunuyor.")

    return unique_ordered(signals)[:10]


def build_conversion_actions(
    pages: list[PageSnapshot],
    site_signals: SiteSignals,
    contact_signals: ContactSignals,
) -> list[str]:
    actions = [f"CTA: {value}" for value in site_signals.cta_texts[:10]]

    for page in pages:
        for form in page.forms[:2]:
            fields_text = ", ".join(form.fields[:4]) if form.fields else "alan detayı sınırlı"
            actions.append(f"{page.page_type} formu ({form.method}): {fields_text}")

    if site_signals.pricing_signals:
        actions.append("Fiyat veya teklif sinyali görülen sayfalar mevcut.")
    if any(page.page_type == "contact" for page in pages) or contact_signals.emails or contact_signals.phones:
        actions.append("Doğrudan temas ve talep toplama yolu mevcut.")

    return unique_ordered(actions)[:14]


def build_content_topics(pages: list[PageSnapshot]) -> list[str]:
    topics: list[str] = []
    for page in pages:
        topics.extend(page.headings)
        topics.extend(page.entity_labels)
        if page.page_type in {"blog", "service", "product", "faq"}:
            topics.extend(page.value_props[:4])

    cleaned: list[str] = []
    for value in topics:
        text = clean_text(value)
        lower = text.lower()
        if not text or len(text) < 4 or len(text) > 120:
            continue
        if lower in GENERIC_TOPIC_TERMS:
            continue
        if not is_topic_candidate(text):
            continue
        cleaned.append(text)

    return unique_ordered(cleaned)[:18]


def build_seo_signals(pages: list[PageSnapshot]) -> list[str]:
    page_types = {page.page_type for page in pages}
    structured_count = sum(1 for page in pages if page.structured_data)
    meta_missing = sum(1 for page in pages if not page.description)
    faq_count = sum(1 for page in pages if page.faq_items)
    long_heading_pages = sum(1 for page in pages if len(page.headings) >= 5)

    signals = [
        "Blog/insight sayfası bulundu." if "blog" in page_types else "Blog/insight sayfası görünmüyor.",
        "SSS veya FAQ sinyali bulundu." if "faq" in page_types or faq_count else "Belirgin FAQ sinyali sınırlı.",
        "Fiyat/pricing sayfası bulundu." if "pricing" in page_types else "Açık pricing sayfası bulunmadı.",
        "İletişim sayfası bulundu." if "contact" in page_types else "Belirgin iletişim sayfası bulunmadı.",
        f"Structured data görülen sayfa sayısı: {structured_count}.",
        f"Meta description eksik sayfa sayısı: {meta_missing}.",
    ]
    if long_heading_pages:
        signals.append(f"En az {long_heading_pages} sayfada güçlü heading hiyerarşisi var.")

    return unique_ordered(signals)[:10]


def build_geography_signals(
    website: str,
    domain: str,
    contact_signals: ContactSignals,
) -> list[str]:
    signals: list[str] = []
    if domain.endswith(".tr") or website.endswith(".tr") or ".com.tr" in website:
        signals.append("Alan adı Türkiye pazarına veya yerel güvene işaret ediyor.")
    if any(phone.startswith("+90") or phone.startswith("90") for phone in contact_signals.phones):
        signals.append("Telefon sinyallerinde +90 ülke kodu görünüyor.")
    signals.extend(contact_signals.addresses[:4])
    return unique_ordered(signals)[:8]


def build_language_signals(website: str, pages: list[PageSnapshot]) -> list[str]:
    languages = unique_ordered(
        [
            page.meta.get("language", "").lower()
            for page in pages
            if clean_text(page.meta.get("language", ""))
        ]
    )
    signals: list[str] = []
    if languages:
        signals.append(f"HTML dil etiketleri: {', '.join(languages[:6])}.")

    primary = pages[0]
    combined_text = " ".join([*primary.headings[:4], *primary.cta_texts[:6], primary.description]).lower()
    has_turkish_markers = any(marker in combined_text for marker in (" için ", "ile", "hemen", "başla", "çözüm"))
    has_english_markers = any(marker in combined_text for marker in ("get", "start", "book", "solutions", "contact"))
    if has_turkish_markers and has_english_markers:
        signals.append("Başlık ve CTA dilinde Türkçe + İngilizce karışık kullanım var.")
    elif has_turkish_markers:
        signals.append("Başlık ve CTA dilinde Türkçe baskın görünüyor.")
    elif has_english_markers:
        signals.append("Başlık ve CTA dilinde İngilizce baskın görünüyor.")

    if website.endswith(".tr") or ".com.tr" in website:
        signals.append("Domain uzantısı yerel dil ve pazar odağını destekliyor.")

    return unique_ordered(signals)[:8]


def build_market_signals(site_signals: SiteSignals, pages: list[PageSnapshot]) -> list[str]:
    signals: list[str] = []
    if site_signals.technologies:
        signals.append(f"Teknoloji sinyalleri: {', '.join(site_signals.technologies[:8])}.")
    if site_signals.currencies:
        signals.append(f"Para birimi sinyalleri: {', '.join(site_signals.currencies[:4])}.")
    if site_signals.page_mix:
        signals.append(f"Sayfa dağılımı: {', '.join(site_signals.page_mix[:6])}.")

    render_modes = unique_ordered([page.fetch_mode for page in pages if page.fetch_mode])
    if render_modes:
        signals.append(f"Render modları: {', '.join(render_modes[:4])}.")

    return unique_ordered(signals)[:10]


def build_visual_signals(pages: list[PageSnapshot], site_signals: SiteSignals) -> list[str]:
    signals: list[str] = []
    theme_colors = unique_ordered(
        [page.meta.get("themeColor", "") for page in pages if clean_text(page.meta.get("themeColor", ""))]
    )
    body_classes = " ".join(
        clean_text(page.meta.get("bodyClass", "")) for page in pages if clean_text(page.meta.get("bodyClass", ""))
    ).lower()

    if site_signals.brand_assets.brand_logo:
        signals.append(f"Ana marka logosu tespit edildi: {site_signals.brand_assets.brand_logo}")
    elif site_signals.logo_url:
        signals.append(f"Logo benzeri görsel tespit edildi: {site_signals.logo_url}")
    if site_signals.brand_assets.favicon:
        signals.append(f"Favicon varlığı tespit edildi: {site_signals.brand_assets.favicon}")
    if theme_colors:
        signals.append(f"Theme color sinyali: {', '.join(theme_colors[:4])}.")
    if "dark" in body_classes:
        signals.append("CSS sınıf sinyallerinde koyu tema izi var.")
    if "light" in body_classes:
        signals.append("CSS sınıf sinyallerinde açık tema izi var.")
    if "rounded" in body_classes:
        signals.append("CSS sınıf sinyallerinde yuvarlatılmış UI yaklaşımı görülüyor.")
    if "glass" in body_classes:
        signals.append("CSS sınıf sinyallerinde glass / panel estetiği izi var.")

    return unique_ordered(signals)[:8]


def extract_main_content(page: Selector) -> str:
    try:
        chunks = [
            clean_text(chunk)
            for chunk in Convertor._extract_content(page, extraction_type="text", main_content_only=True)
            if clean_text(chunk)
        ]
        return clean_text(" ".join(chunks))[:12000]
    except Exception:
        return clean_text(
            page.get_all_text(
                strip=True,
                ignore_tags=("script", "style", "noscript", "svg", "iframe"),
            )
        )[:12000]


def extract_meta_tags(page: Selector) -> dict[str, str]:
    pairs = {
        "canonical": page.css("link[rel='canonical']::attr(href)").get(default=""),
        "ogTitle": page.css("meta[property='og:title']::attr(content)").get(default=""),
        "ogSiteName": page.css("meta[property='og:site_name']::attr(content)").get(default=""),
        "ogImage": page.css("meta[property='og:image']::attr(content)").get(default=""),
        "twitterImage": page.css("meta[name='twitter:image']::attr(content)").get(default=""),
        "icon": page.css("link[rel='icon']::attr(href)").get(default=""),
        "shortcutIcon": page.css("link[rel='shortcut icon']::attr(href)").get(default=""),
        "appleTouchIcon": page.css("link[rel='apple-touch-icon']::attr(href)").get(default=""),
        "appleTouchIconPrecomposed": page.css("link[rel='apple-touch-icon-precomposed']::attr(href)").get(default=""),
        "maskIcon": page.css("link[rel='mask-icon']::attr(href)").get(default=""),
        "manifest": page.css("link[rel='manifest']::attr(href)").get(default=""),
        "msTileImage": page.css("meta[name='msapplication-TileImage']::attr(content)").get(default=""),
        "twitterCard": page.css("meta[name='twitter:card']::attr(content)").get(default=""),
        "language": page.css("html::attr(lang)").get(default=""),
        "themeColor": page.css("meta[name='theme-color']::attr(content)").get(default=""),
        "bodyClass": page.css("body::attr(class)").get(default=""),
    }
    return {key: clean_text(value) for key, value in pairs.items() if clean_text(value)}


def extract_hero_messages(page: Selector) -> list[str]:
    values = page.css(
        "main h1::text, [class*='hero'] h1::text, [class*='hero'] h2::text, "
        "header h1::text, main > section p::text, [class*='hero'] p::text"
    ).getall()
    cleaned: list[str] = []

    for value in values:
        text = clean_text(value)
        if not text or len(text) < 12 or len(text) > 180:
            continue
        if is_low_signal_text(text):
            continue
        cleaned.append(text)

    return unique_ordered(cleaned)[:8]


def extract_trust_signals(raw_text: str) -> list[str]:
    return extract_sentence_matches(raw_text, TRUST_KEYWORDS, min_len=18, max_len=180)[:10]


def extract_audience_signals(raw_text: str, headings: list[str], nav_labels: list[str]) -> list[str]:
    matches = extract_sentence_matches(raw_text, AUDIENCE_KEYWORDS, min_len=14, max_len=180)
    for value in headings:
        text = clean_text(value)
        lowered = text.lower()
        if text and not is_low_signal_text(text) and any(keyword in lowered for keyword in AUDIENCE_KEYWORDS):
            matches.append(text)
    return clean_signal_list(matches, min_len=14, max_len=180)[:10]


def extract_proof_points(raw_text: str, trust_signals: list[str]) -> list[str]:
    points = [
        sentence
        for sentence in split_sentences(raw_text)
        if 12 <= len(sentence) <= 180 and PROOF_POINT_PATTERN.search(sentence)
    ]
    points.extend(
        [
            signal
            for signal in trust_signals
            if PROOF_POINT_PATTERN.search(signal)
            or any(keyword in signal.lower() for keyword in ("müşteri", "client", "referans", "award", "ödül"))
        ]
    )
    return unique_ordered(points)[:10]


def extract_semantic_zones(
    page: Selector,
    *,
    raw_text: str,
    page_type: str,
    hero_messages: list[str],
    trust_signals: list[str],
    audience_signals: list[str],
    proof_points: list[str],
    pricing_signals: list[str],
    faq_items: list[FaqItem],
) -> dict[str, list[str]]:
    hero_zone = unique_ordered(
        hero_messages
        + extract_zone_texts(
            page,
            "main h1, main h2, [class*='hero'], [id*='hero'], header h1, main > section:first-child",
            identifier=f"{page_type}:hero",
        )
    )[:8]
    offer_zone = extract_zone_texts(
        page,
        "[class*='feature'], [class*='service'], [class*='product'], [class*='solution'], "
        "[class*='benefit'], [class*='card'], main section",
        identifier=f"{page_type}:offers",
    )
    proof_zone = unique_ordered(
        trust_signals
        + proof_points
        + extract_zone_texts(
            page,
            "[class*='testimonial'], [class*='review'], [class*='client'], [class*='partner'], "
            "[class*='trust'], [class*='case'], [class*='reference']",
            identifier=f"{page_type}:proof",
        )
    )[:10]
    pricing_zone = unique_ordered(
        pricing_signals
        + extract_zone_texts(
            page,
            "[class*='pricing'], [class*='price'], [class*='plan'], [data-price], table",
            identifier=f"{page_type}:pricing",
        )
    )[:10]
    faq_zone = unique_ordered(
        [faq.question for faq in faq_items if faq.question]
        + extract_zone_texts(
            page,
            "[class*='faq'], [class*='accordion'], details, summary",
            identifier=f"{page_type}:faq",
        )
    )[:8]
    contact_zone = unique_ordered(
        audience_signals[:2]
        + extract_zone_texts(
            page,
            "[class*='contact'], footer, a[href^='mailto:'], a[href^='tel:'], address",
            identifier=f"{page_type}:contact",
        )
    )[:8]

    if page_type in {"service", "product"}:
        offer_zone = unique_ordered(page.css("h2::text, h3::text").getall() + offer_zone)[:10]
    if page_type == "pricing":
        pricing_zone = unique_ordered(page.css("h1::text, h2::text, h3::text").getall() + pricing_zone)[:10]
    if page_type == "faq":
        faq_zone = unique_ordered(page.css("h1::text, h2::text, details summary::text").getall() + faq_zone)[:10]

    if not hero_zone:
        hero_zone = split_sentences(raw_text[:360])[:4]

    return {
        "hero": [clean_text(value) for value in hero_zone if clean_text(value)],
        "offers": [clean_text(value) for value in offer_zone if clean_text(value)],
        "proof": [clean_text(value) for value in proof_zone if clean_text(value)],
        "pricing": [clean_text(value) for value in pricing_zone if clean_text(value)],
        "faq": [clean_text(value) for value in faq_zone if clean_text(value)],
        "contact": [clean_text(value) for value in contact_zone if clean_text(value)],
    }


def extract_zone_texts(
    page: Selector,
    selectors: str,
    *,
    identifier: str,
    max_elements: int = 8,
) -> list[str]:
    elements = select_zone_elements(page, selectors, identifier=identifier, max_elements=max_elements)
    texts: list[str] = []

    for element in elements:
        try:
            text = clean_text(" ".join(element.css("::text").getall()))
        except Exception:
            text = clean_text(getattr(element, "text", ""))

        if not text:
            continue

        for fragment in split_sentences(text):
            cleaned = clean_text(fragment)
            if not cleaned:
                continue
            if len(cleaned) < 14 or len(cleaned) > 220:
                continue
            if cleaned.lower() in GENERIC_TOPIC_TERMS:
                continue
            texts.append(cleaned)

    return unique_ordered(texts)[: max_elements * 2]


def select_zone_elements(
    page: Selector,
    selectors: str,
    *,
    identifier: str,
    max_elements: int,
):
    try:
        elements = page.css(selectors, auto_save=True, identifier=identifier)
        if elements:
            return elements[:max_elements]
        elements = page.css(selectors, adaptive=True, identifier=identifier)
        return elements[:max_elements]
    except Exception:
        try:
            return page.css(selectors)[:max_elements]
        except Exception:
            return []


def extract_sentence_matches(
    raw_text: str,
    keywords: Iterable[str],
    *,
    min_len: int,
    max_len: int,
) -> list[str]:
    results: list[str] = []
    lowered_keywords = tuple(keyword.lower() for keyword in keywords)
    for sentence in split_sentences(raw_text):
        lowered = sentence.lower()
        if min_len <= len(sentence) <= max_len and any(keyword in lowered for keyword in lowered_keywords):
            results.append(sentence)
    return unique_ordered(results)


def extract_logo_candidates(page: Selector) -> list[str]:
    candidates: list[str] = []

    image_selectors = (
        "header img, nav img, [class*='header'] img, [class*='nav'] img, "
        "[class*='logo'] img, img[class*='logo'], img[alt*='logo'], "
        "a[href='/'] img, a[href='./'] img, picture img, img"
    )

    for image in page.css(image_selectors)[:40]:
        src = (
            image.attrib.get("src")
            or image.attrib.get("data-src")
            or image.attrib.get("data-lazy-src")
            or image.attrib.get("data-srcset", "").split(",")[0].strip().split(" ")[0]
            or image.attrib.get("srcset", "").split(",")[0].strip().split(" ")[0]
        )
        alt = clean_text(image.attrib.get("alt", ""))
        class_text = clean_text(" ".join(image.attrib.get("class", "").split()))
        parent_href = ""
        parent = getattr(image, "parent", None)
        if parent is not None and hasattr(parent, "attrib"):
            parent_href = clean_text(parent.attrib.get("href", ""))

        haystack = f"{alt} {class_text} {src} {parent_href}".lower()
        if not src:
            continue
        if any(keyword in haystack for keyword in ("logo", "brand", "icon", "navbar", "header", "/logo", "site-logo")):
            resolved = resolve_asset_url(page.url, src)
            if resolved:
                candidates.append(resolved)

    return unique_ordered(candidates)


def choose_logo_url(pages: list[PageSnapshot]) -> str:
    scored_candidates: list[tuple[int, str]] = []

    for page in pages:
        meta_candidates = [
            page.meta.get("icon", ""),
            page.meta.get("shortcutIcon", ""),
            page.meta.get("appleTouchIcon", ""),
            page.meta.get("ogImage", ""),
            page.meta.get("twitterImage", ""),
        ]
        for candidate in meta_candidates:
            resolved = resolve_asset_url(page.url, candidate)
            if not resolved:
                continue
            scored_candidates.append((score_logo_candidate(resolved, from_meta=True), resolved))

        for candidate in page.logo_candidates:
            scored_candidates.append((score_logo_candidate(candidate), candidate))

    if not scored_candidates:
        return ""

    scored_candidates.sort(key=lambda item: item[0], reverse=True)
    return scored_candidates[0][1]


def resolve_asset_url(page_url: str, value: str) -> str:
    cleaned = clean_text(value)
    if not cleaned or cleaned.startswith("data:"):
        return ""
    return urljoin(page_url, cleaned)


def score_logo_candidate(url: str, alt: str = "", from_meta: bool = False) -> int:
    lower_url = url.lower()
    lower_alt = alt.lower()
    score = 0

    if from_meta:
        score += 14
    if "logo" in lower_url or "logo" in lower_alt:
        score += 16
    if "brand" in lower_url or "brand" in lower_alt:
        score += 9
    if "icon" in lower_url:
        score += 8
    if "favicon" in lower_url:
        score += 10
    if any(lower_url.endswith(ext) for ext in (".svg", ".png", ".webp", ".ico")):
        score += 5
    if any(token in lower_url for token in ("hero", "banner", "cover", "og-image", "social-share")):
        score -= 7

    return score


def extract_structured_data(page: Selector) -> tuple[list[str], list[FaqItem], list[str]]:
    summaries: list[str] = []
    faq_items: list[FaqItem] = []
    entities: list[str] = []

    for blob in page.css("script[type='application/ld+json']::text").getall()[:10]:
        text_blob = clean_text(blob)
        if not text_blob:
            continue

        for item in iter_json_ld_items(text_blob):
            summaries.append(summarize_json_ld_item(item))
            faq_items.extend(extract_faq_items_from_json_ld(item))
            entity_name = clean_text(str(item.get("name", "")))
            if entity_name and entity_name.lower() not in {"home", "homepage"}:
                entities.append(entity_name)

    return unique_ordered(summaries), faq_items, unique_ordered(entities)


def iter_json_ld_items(blob: str) -> list[dict[str, Any]]:
    payload = safe_json_parse(blob)
    if payload is None:
        return []

    items: list[dict[str, Any]] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if "@graph" in node and isinstance(node["@graph"], list):
                for child in node["@graph"]:
                    visit(child)
            items.append(node)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(payload)
    return items


def safe_json_parse(blob: str) -> Any | None:
    try:
        return json.loads(blob)
    except Exception:
        return None


def summarize_json_ld_item(item: dict[str, Any]) -> str:
    item_type = item.get("@type")
    if isinstance(item_type, list):
        item_type = ", ".join(str(value) for value in item_type)

    fields = [
        clean_text(str(item_type or "Schema")),
        clean_text(str(item.get("name", ""))),
        clean_text(str(item.get("description", "")))[:180],
    ]
    return " | ".join(part for part in fields if part)


def extract_faq_items_from_json_ld(item: dict[str, Any]) -> list[FaqItem]:
    item_type = item.get("@type")
    item_types = {str(item_type).lower()} if not isinstance(item_type, list) else {str(value).lower() for value in item_type}
    if "faqpage" not in item_types:
        return []

    results: list[FaqItem] = []
    main_entity = item.get("mainEntity", [])
    if not isinstance(main_entity, list):
        main_entity = [main_entity]

    for entity in main_entity:
        if not isinstance(entity, dict):
            continue

        question = clean_text(str(entity.get("name", "")))
        accepted_answer = entity.get("acceptedAnswer", {})
        if isinstance(accepted_answer, dict):
            answer = clean_text(str(accepted_answer.get("text", "")))
        else:
            answer = clean_text(str(accepted_answer))

        if question and answer:
            results.append(FaqItem(question=question, answer=answer))

    return results


def extract_cta_texts(page: Selector) -> list[str]:
    raw_values = page.css(
        "button::text, [role='button']::text, input[type='submit']::attr(value), "
        "a[href*='contact']::text, a[href*='demo']::text, a[href*='pricing']::text, "
        "a[href*='quote']::text, a[href*='trial']::text, a[href*='book']::text"
    ).getall()
    cleaned = [
        clean_text(value)
        for value in raw_values
        if 2 <= len(clean_text(value)) <= 60
    ]
    return [
        value
        for value in unique_ordered(cleaned)
        if any(keyword in value.lower() for keyword in CTA_KEYWORDS)
    ]


def extract_value_props(page: Selector, zones: dict[str, list[str]] | None = None) -> list[str]:
    zone_candidates = []
    if zones:
        zone_candidates.extend(zones.get("hero", []))
        zone_candidates.extend(zones.get("offers", []))

    selector_candidates = page.css("h1::text, h2::text, h3::text, li::text, p::text").getall()
    candidates = unique_ordered([*zone_candidates, *selector_candidates])
    cleaned: list[str] = []

    for value in candidates:
        text = clean_text(value)
        if not text:
            continue
        if len(text) < 18 or len(text) > 180:
            continue
        if is_low_signal_text(text):
            continue
        if score_claim_candidate(text, claim_type="value_prop") <= 12:
            continue
        cleaned.append(text)

    return unique_ordered(cleaned)[:12]


def extract_nav_labels(page: Selector) -> list[str]:
    labels = [
        clean_text(value)
        for value in page.css("header a::text, nav a::text").getall()
        if clean_text(value)
    ]
    return [label for label in unique_ordered(labels) if len(label) <= 32][:18]


def extract_pricing_signals(page: Selector, raw_text: str) -> list[str]:
    signals = [
        clean_text(match.get_all_text(strip=True))
        for match in page.find_by_regex(PRICE_PATTERN, first_match=False, clean_match=True)
        if clean_text(match.get_all_text(strip=True))
    ]
    if not signals:
        signals = [clean_text(value) for value in PRICE_PATTERN.findall(raw_text)]
    return unique_ordered(signals)


def extract_forms(page: Selector) -> list[FormSnapshot]:
    results: list[FormSnapshot] = []

    for form in page.css("form")[:8]:
        fields: list[str] = []
        for field in form.css("input, select, textarea")[:12]:
            label = (
                field.attrib.get("name")
                or field.attrib.get("type")
                or field.attrib.get("placeholder")
                or field.tag
            )
            cleaned = clean_text(label)
            if cleaned:
                fields.append(cleaned)

        results.append(
            FormSnapshot(
                action=urljoin(page.url, form.attrib.get("action", "")),
                method=(form.attrib.get("method", "GET") or "GET").upper(),
                fields=unique_ordered(fields)[:12],
            )
        )

    return results


def extract_repeated_entities(page: Selector) -> list[str]:
    candidate_selectors = (
        "article",
        "[class*='product']",
        "[class*='service']",
        "[class*='card']",
        "[class*='feature']",
        "li",
    )

    for selector in candidate_selectors:
        for candidate in page.css(selector)[:5]:
            label = extract_element_label(candidate)
            if not label:
                continue

            try:
                similar = candidate.find_similar(
                    similarity_threshold=0.25,
                    ignore_attributes=("href", "src", "id", "data-id"),
                )
            except Exception:
                continue

            labels = unique_ordered([label] + [extract_element_label(item) for item in similar])
            labels = [value for value in labels if value and len(value) <= 120]
            if len(labels) >= 3:
                return labels[:12]

    return []


def extract_element_label(element: Selector) -> str:
    label = clean_text(
        element.css("h1::text, h2::text, h3::text, h4::text, strong::text").get(default="")
        or element.text
        or element.get_all_text(strip=True)
    )
    if len(label) > 120:
        label = label[:117].strip() + "..."
    if len(label) < 3:
        return ""
    return label


def detect_technologies(page: Selector) -> list[str]:
    html = safe_decode(getattr(page, "body", b"")) or page.html_content
    lowered = html.lower()
    detected = []

    for tech_name, signatures in TECH_SIGNATURES.items():
        if any(signature.lower() in lowered for signature in signatures):
            detected.append(tech_name)

    return detected


def detect_currencies(pricing_signals: list[str], raw_text: str) -> list[str]:
    sample = " ".join(pricing_signals) or raw_text
    results = []

    if "₺" in sample or re.search(r"\bTL\b", sample, re.IGNORECASE):
        results.append("TRY")
    if "$" in sample or re.search(r"\bUSD\b", sample, re.IGNORECASE):
        results.append("USD")
    if "€" in sample or re.search(r"\bEUR\b", sample, re.IGNORECASE):
        results.append("EUR")
    if "£" in sample or re.search(r"\bGBP\b", sample, re.IGNORECASE):
        results.append("GBP")

    return results


def extract_address_candidates(pages: list[PageSnapshot]) -> list[str]:
    candidates: list[str] = []

    for page in pages:
        for sentence in split_sentences(page.raw_text):
            if ADDRESS_HINT_PATTERN.search(sentence):
                candidates.append(sentence)

    return unique_ordered(candidates)[:6]


def split_sentences(text: str) -> list[str]:
    return [
        clean_text(part)
        for part in re.split(r"(?<=[.!?])\s+", text)
        if clean_text(part)
    ]


def classify_page(url: str, title: str) -> str:
    path = urlparse(url).path.lower().strip("/")
    haystack = f"{path} {title.lower()}"

    if not path:
        return "homepage"
    if any(token in haystack for token in ("pricing", "fiyat")):
        return "pricing"
    if any(token in haystack for token in ("product", "shop", "urun", "collection", "kategori")):
        return "product"
    if any(token in haystack for token in ("service", "hizmet", "solution", "cozum")):
        return "service"
    if any(token in haystack for token in ("about", "hakkimizda", "company", "kurumsal")):
        return "about"
    if any(token in haystack for token in ("contact", "iletisim")):
        return "contact"
    if any(token in haystack for token in ("faq", "sss", "yardim")):
        return "faq"
    if any(token in haystack for token in ("blog", "article", "news", "insight")):
        return "blog"
    if any(token in haystack for token in ("case", "testimonial", "review", "referans")):
        return "social-proof"
    return "general"


def prioritize_links(links: Iterable[str], domain: str, current_page_type: str = "general") -> list[str]:
    filtered: list[str] = []

    for link in links:
        normalized = canonicalize_url(link)
        parsed = urlparse(normalized)
        path_lower = parsed.path.lower()

        if not parsed.netloc or (parsed.netloc != domain and not parsed.netloc.endswith(f".{domain}")):
            continue
        if re.search(r"\.(jpg|jpeg|png|gif|svg|webp|pdf|zip|xml)$", parsed.path, re.IGNORECASE):
            continue
        if any(keyword in path_lower for keyword in SKIP_PATH_KEYWORDS):
            continue

        filtered.append(normalized)

    def sort_key(link: str) -> tuple[int, int, int, str]:
        path = urlparse(link).path.strip("/")
        lower_path = path.lower()
        segments = [segment for segment in path.split("/") if segment]
        segment_score = next(
            (
                index
                for index, keyword in enumerate(PRIORITY_SEGMENTS)
                if keyword and keyword in lower_path
            ),
            len(PRIORITY_SEGMENTS),
        )
        same_topic_bonus = 0 if current_page_type in lower_path else 1
        return (segment_score, same_topic_bonus, len(segments), link)

    return unique_ordered(sorted(filtered, key=sort_key))[:24]


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    path = parsed.path or "/"
    return urlunparse(
        (
            parsed.scheme or "https",
            parsed.netloc.replace("www.", ""),
            path.rstrip("/") or "/",
            "",
            "",
            "",
        )
    )


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def clean_signal_list(
    values: Iterable[str],
    *,
    min_len: int = 12,
    max_len: int = 220,
    allow_cta: bool = False,
) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = clean_text(value)
        if not text or len(text) < min_len or len(text) > max_len:
            continue
        if is_low_signal_text(text, allow_cta=allow_cta):
            continue
        cleaned.append(text)
    return unique_ordered(cleaned)


def is_topic_candidate(text: str) -> bool:
    normalized = clean_text(text)
    lowered = normalized.lower()
    if not normalized or is_low_signal_text(normalized):
        return False

    word_count = len(re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9]+", normalized))
    if word_count <= 3 and not any(token in lowered for token in TOPIC_HINT_TOKENS):
        return False
    if lowered in GENERIC_TOPIC_TERMS:
        return False
    return True


def is_low_signal_text(text: str, *, allow_cta: bool = False) -> bool:
    lowered = clean_text(text).lower()
    if not lowered:
        return True
    if lowered in GENERIC_TOPIC_TERMS:
        return True
    if any(phrase in lowered for phrase in LOW_SIGNAL_PHRASES):
        return True
    if "©" in text or "all rights reserved" in lowered:
        return True

    token_hits = sum(1 for token in NAVIGATION_NOISE_TOKENS if re.search(rf"\b{re.escape(token)}\b", lowered))
    if token_hits >= 4:
        return True

    if not allow_cta and lowered.startswith("cta:"):
        return True

    return False


def safe_decode(value: bytes | str) -> str:
    if isinstance(value, str):
        return value
    return value.decode("utf-8", errors="ignore")


def unique_ordered(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)

    return result


def standardize_crawl_notes(notes: Iterable[str]) -> list[str]:
    normalized_notes: list[str] = []

    for note in notes:
        cleaned = clean_text(note)
        if not cleaned:
            continue
        if re.match(r"^(INFO|WARN|ERROR):\s", cleaned):
            normalized_notes.append(cleaned)
        else:
            normalized_notes.append(f"INFO: {cleaned}")

    return unique_ordered(normalized_notes)[:16]


def normalize_phones(values: Iterable[str]) -> set[str]:
    normalized: set[str] = set()

    for value in values:
        cleaned = re.sub(r"[^\d+]", "", value)
        if len(re.sub(r"\D", "", cleaned)) < 7:
            continue
        normalized.add(cleaned)

    return normalized


def response_quality_score(response: Selector) -> int:
    text = clean_text(
        response.get_all_text(
            strip=True,
            ignore_tags=("script", "style", "noscript", "svg", "iframe"),
        )
    )
    return len(text) + (len(response.css("h1, h2, h3")) * 60) + (len(response.css("form")) * 40)


def needs_browser_render(response: Selector) -> bool:
    html = safe_decode(getattr(response, "body", b"")).lower()
    text = clean_text(
        response.get_all_text(
            strip=True,
            ignore_tags=("script", "style", "noscript", "svg", "iframe"),
        )
    )
    script_count = len(response.css("script"))
    heading_count = len(response.css("h1, h2, h3"))
    markers = ("__next", "__nuxt", "data-reactroot", "window.__", "application/ld+json")
    has_spa_markers = any(marker in html for marker in markers)

    return (len(text) < 300 and script_count > 10) or (heading_count == 0 and has_spa_markers)


def is_blocked_response(response: Any) -> bool:
    status = getattr(response, "status", 200)
    if status in BLOCKED_STATUS_CODES:
        return True

    body_text = safe_decode(getattr(response, "body", b""))[:4000].lower()
    return any(marker in body_text for marker in BLOCKED_BODY_MARKERS)


def looks_like_html_response(response: Any) -> bool:
    headers = getattr(response, "headers", {}) or {}
    content_type = str(headers.get("content-type", "")).lower()
    if "text/html" in content_type:
        return True
    body_preview = safe_decode(getattr(response, "body", b""))[:2000].lower()
    return "<html" in body_preview or "<body" in body_preview


def looks_like_html_httpx(response: httpx.Response) -> bool:
    content_type = response.headers.get("content-type", "").lower()
    return "text/html" in content_type or "<html" in response.text.lower()


def should_verify_ssl() -> bool:
    return os.getenv("HTTP_VERIFY_SSL", "true").lower() not in {"0", "false", "no"}
