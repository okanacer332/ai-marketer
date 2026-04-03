from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
import json
import os
import re
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from scrapling import Selector
from scrapling.core.shell import Convertor

try:
    from scrapling.fetchers import FetcherSession, AsyncDynamicSession, AsyncStealthySession

    SCRAPLING_FETCHERS_AVAILABLE = True
    SCRAPLING_FETCHERS_ERROR = ""
except Exception as exc:  # pragma: no cover
    FetcherSession = None  # type: ignore[assignment]
    AsyncDynamicSession = None  # type: ignore[assignment]
    AsyncStealthySession = None  # type: ignore[assignment]
    SCRAPLING_FETCHERS_AVAILABLE = False
    SCRAPLING_FETCHERS_ERROR = str(exc)


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
}
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
    meta: dict[str, str] = field(default_factory=dict)


@dataclass
class ContactSignals:
    emails: list[str]
    phones: list[str]
    socials: list[str]
    addresses: list[str] = field(default_factory=list)


@dataclass
class SiteSignals:
    technologies: list[str]
    currencies: list[str]
    cta_texts: list[str]
    faq_highlights: list[str]
    entity_labels: list[str]
    page_mix: list[str]
    pricing_signals: list[str]
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


async def crawl_website(url: str, max_pages: int = 12, max_depth: int = 2) -> CrawlBundle:
    website = normalize_url(url)
    domain = urlparse(website).netloc.replace("www.", "")

    if SCRAPLING_FETCHERS_AVAILABLE and FetcherSession is not None:
        return await crawl_with_scrapling(website, domain, max_pages=max_pages, max_depth=max_depth)

    fallback_note = "INFO: Scrapling fetcher katmanı kullanılamadı, selector tabanlı yedek akış kullanıldı."
    if SCRAPLING_FETCHERS_ERROR:
        fallback_note = f"{fallback_note} Neden: {SCRAPLING_FETCHERS_ERROR}"

    bundle = await crawl_with_httpx_fallback(website, domain, max_pages=max_pages, max_depth=max_depth)
    bundle.notes.insert(0, fallback_note)
    bundle.notes = standardize_crawl_notes(bundle.notes)
    bundle.crawl_meta.notes = bundle.notes
    return bundle


async def crawl_with_scrapling(website: str, domain: str, max_pages: int, max_depth: int) -> CrawlBundle:
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(website, 0)])
    pages: list[PageSnapshot] = []
    notes: list[str] = []
    failures = 0

    static_session_manager = FetcherSession(  # type: ignore[operator]
        impersonate=["chrome", "firefox", "safari"],
        stealthy_headers=True,
        timeout=20,
        retries=2,
        retry_delay=1,
        follow_redirects=True,
        verify=should_verify_ssl(),
        headers={"Accept-Language": DEFAULT_ACCEPT_LANGUAGE},
        selector_config=SCRAPE_SELECTOR_CONFIG,
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
                response, fetch_mode, fetch_notes = await fetch_with_best_effort(static_session, current_url)
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

            selector = Selector(response.text, url=str(response.url))
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
    )


async def fetch_with_best_effort(static_session: Any, url: str) -> tuple[Any, str, list[str]]:
    notes: list[str] = []
    static_response = await static_session.get(url)
    best_response = static_response
    best_mode = "static"

    if is_blocked_response(static_response):
        notes.append(f"{url} için korumalı yanıt algılandı, tarayıcı katmanına yükseltildi.")
        dynamic_response = await try_dynamic_fetch(url)
        if dynamic_response is not None:
            return dynamic_response, "dynamic", notes

        stealth_response = await try_stealth_fetch(url)
        if stealth_response is not None:
            return stealth_response, "stealth", notes

        return best_response, best_mode, notes

    if needs_browser_render(static_response):
        dynamic_response = await try_dynamic_fetch(url)
        if dynamic_response is not None and response_quality_score(dynamic_response) > response_quality_score(static_response):
            notes.append(f"{url} için dinamik render daha zengin içerik döndürdü.")
            best_response = dynamic_response
            best_mode = "dynamic"
        else:
            stealth_response = await try_stealth_fetch(url)
            if stealth_response is not None and response_quality_score(stealth_response) > response_quality_score(best_response):
                notes.append(f"{url} için stealth render daha zengin içerik döndürdü.")
                best_response = stealth_response
                best_mode = "stealth"

    return best_response, best_mode, notes


async def try_dynamic_fetch(url: str) -> Any | None:
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
            selector_config=SCRAPE_SELECTOR_CONFIG,
        ) as session:
            return await session.fetch(url)
    except Exception:
        return None


async def try_stealth_fetch(url: str) -> Any | None:
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
            selector_config=SCRAPE_SELECTOR_CONFIG,
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
    value_props = extract_value_props(page)
    nav_labels = extract_nav_labels(page)
    pricing_signals = extract_pricing_signals(page, raw_text)
    forms = extract_forms(page)
    hero_messages = extract_hero_messages(page)
    trust_signals = extract_trust_signals(raw_text)
    audience_signals = extract_audience_signals(raw_text, headings, nav_labels)
    proof_points = extract_proof_points(raw_text, trust_signals)
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

    site_signals = build_site_signals(pages)
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


def build_site_signals(pages: list[PageSnapshot]) -> SiteSignals:
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
    logo_url = choose_logo_url(pages)

    return SiteSignals(
        technologies=technologies,
        currencies=currencies,
        cta_texts=cta_texts,
        faq_highlights=faq_highlights,
        entity_labels=entity_labels,
        page_mix=page_mix,
        pricing_signals=pricing_signals,
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
    inferred_service_offers, inferred_product_offers = infer_offer_buckets(pages)
    service_offers = unique_ordered(collect_offer_labels(pages, {"service"}) + inferred_service_offers)[:14]
    product_offers = unique_ordered(collect_offer_labels(pages, {"product"}) + inferred_product_offers)[:14]
    offer_signals = unique_ordered(
        [
            *hero_messages,
            *[value for page in pages for value in page.value_props],
            *[label for page in pages for label in page.entity_labels],
            *[heading for page in pages for heading in page.headings],
        ]
    )[:18]
    audience_signals = unique_ordered([value for page in pages for value in page.audience_signals])[:14]
    trust_signals = unique_ordered([value for page in pages for value in page.trust_signals])[:14]
    proof_points = unique_ordered([value for page in pages for value in page.proof_points])[:12]
    conversion_actions = build_conversion_actions(pages, site_signals, contact_signals)
    content_topics = build_content_topics(pages)
    seo_signals = build_seo_signals(pages)
    geography_signals = build_geography_signals(website, domain, contact_signals)
    language_signals = build_language_signals(website, pages)
    market_signals = build_market_signals(site_signals, pages)
    visual_signals = build_visual_signals(pages, site_signals)
    positioning_signals = build_positioning_signals(
        hero_messages=hero_messages,
        service_offers=service_offers,
        product_offers=product_offers,
        pages=pages,
        contact_signals=contact_signals,
        site_signals=site_signals,
    )

    return ResearchPackage(
        company_name_candidates=company_name_candidates,
        hero_messages=hero_messages,
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
    )


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

    return unique_ordered(service_labels)[:14], unique_ordered(product_labels)[:14]


def build_positioning_signals(
    hero_messages: list[str],
    service_offers: list[str],
    product_offers: list[str],
    pages: list[PageSnapshot],
    contact_signals: ContactSignals,
    site_signals: SiteSignals,
) -> list[str]:
    signals = list(hero_messages[:3])
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

    if site_signals.logo_url:
        signals.append(f"Logo varlığı tespit edildi: {site_signals.logo_url}")
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
        cleaned.append(text)

    return unique_ordered(cleaned)[:8]


def extract_trust_signals(raw_text: str) -> list[str]:
    return extract_sentence_matches(raw_text, TRUST_KEYWORDS, min_len=18, max_len=180)[:10]


def extract_audience_signals(raw_text: str, headings: list[str], nav_labels: list[str]) -> list[str]:
    matches = extract_sentence_matches(raw_text, AUDIENCE_KEYWORDS, min_len=14, max_len=180)
    for value in [*headings, *nav_labels]:
        text = clean_text(value)
        lowered = text.lower()
        if text and any(keyword in lowered for keyword in AUDIENCE_KEYWORDS):
            matches.append(text)
    return unique_ordered(matches)[:10]


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

    for image in page.css("img")[:24]:
        src = (
            image.attrib.get("src")
            or image.attrib.get("data-src")
            or image.attrib.get("data-lazy-src")
            or image.attrib.get("srcset", "").split(",")[0].strip().split(" ")[0]
        )
        alt = clean_text(image.attrib.get("alt", ""))
        class_text = clean_text(" ".join(image.attrib.get("class", "").split()))
        if not src:
            continue
        if any(keyword in f"{alt} {class_text} {src}".lower() for keyword in ("logo", "brand", "icon", "navbar")):
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


def extract_value_props(page: Selector) -> list[str]:
    candidates = page.css("h2::text, h3::text, li::text, p::text").getall()
    cleaned = []

    for value in candidates:
        text = clean_text(value)
        if not text:
            continue
        if len(text) < 18 or len(text) > 160:
            continue
        if text.lower() in {"menu", "blog", "home", "pricing", "contact"}:
            continue
        cleaned.append(text)

    return unique_ordered(cleaned)


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
