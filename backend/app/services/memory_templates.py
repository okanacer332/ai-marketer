from __future__ import annotations

import re
from typing import Any, Iterable

from .output_normalizer import normalize_markdown_output, normalize_text_output
from .scrape import CrawlBundle


MEMORY_FILE_SPECS = [
    {
        "id": "business-profile",
        "filename": "business-profile.md",
        "title": "İşletme Profili",
        "blurb": "İş modeli, teklif yapısı ve hedef kitle özeti.",
        "requiredHeadings": ("# İşletme Profili", "## Genel Bakış", "## Hedef Kitle"),
    },
    {
        "id": "brand-guidelines",
        "filename": "brand-guidelines.md",
        "title": "Marka Kılavuzu",
        "blurb": "Ton, görsel yön ve CTA davranışı için rehber.",
        "requiredHeadings": ("# Marka Kılavuzu", "## Marka Hissi", "## CTA Stili"),
    },
    {
        "id": "market-research",
        "filename": "market-research.md",
        "title": "Pazar Araştırması",
        "blurb": "Kategori, rakip çerçevesi ve içerik fırsatları.",
        "requiredHeadings": ("# Pazar Araştırması", "## Muhtemel Rakip Çerçevesi", "## SEO ve İçerik Fırsatları"),
    },
    {
        "id": "strategy",
        "filename": "strategy.md",
        "title": "30 Günlük Strateji",
        "blurb": "İlk ayın kanal, teklif ve içerik öncelikleri.",
        "requiredHeadings": ("# 30 Günlük Strateji", "## Kuzey Yıldızı", "## Hızlı Kazanımlar"),
    },
]

NOISE_SNIPPETS = (
    "services projects blog contact",
    "made with by",
    "copyright",
    "all rights reserved",
    "devamını oku",
    "read more",
    "selected",
)
NAVIGATION_TOKENS = (
    "home",
    "about",
    "services",
    "projects",
    "blog",
    "contact",
    "pricing",
    "faq",
    "en",
    "tr",
)
PAGE_TYPE_LABELS = {
    "general": "Genel",
    "service": "Hizmet",
    "product": "Ürün",
    "pricing": "Fiyat",
    "blog": "İçerik",
    "faq": "SSS",
    "contact": "İletişim",
    "about": "Hakkımızda",
}


def normalize_memory_files(
    memory_files: list[dict[str, Any]] | None,
    bundle: CrawlBundle,
    analysis: dict[str, Any],
    goals: list[str],
    connected_platforms: list[str],
    strategic_summary: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    defaults = build_default_memory_files(
        bundle=bundle,
        analysis=analysis,
        goals=goals,
        connected_platforms=connected_platforms,
        strategic_summary=strategic_summary or {},
    )
    provided_map = build_memory_file_map(memory_files or [])
    normalized: list[dict[str, Any]] = []

    for spec, fallback in zip(MEMORY_FILE_SPECS, defaults):
        candidate = provided_map.get(spec["id"]) or provided_map.get(spec["filename"]) or {}
        candidate_content = candidate.get("content") if isinstance(candidate, dict) else ""
        use_candidate = content_meets_threshold(candidate_content, spec["requiredHeadings"]) and not content_has_quality_issues(candidate_content)

        normalized.append(
            {
                "id": spec["id"],
                "filename": spec["filename"],
                "title": clean_line(candidate.get("title")) or fallback["title"],
                "blurb": clean_line(candidate.get("blurb")) or fallback["blurb"],
                "content": clean_markdown(candidate_content) if use_candidate else fallback["content"],
            }
        )

    return normalized


def build_default_memory_files(
    bundle: CrawlBundle,
    analysis: dict[str, Any],
    goals: list[str],
    connected_platforms: list[str],
    strategic_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    research = bundle.research_package
    goals_text = ", ".join(clean_line(goal) for goal in goals if clean_line(goal)) if goals else "SEO, Sosyal Medya, İçerik"
    connected_text = ", ".join(clean_line(platform) for platform in connected_platforms if clean_line(platform)) if connected_platforms else "Henüz platform bağlanmadı"
    company_name = clean_line(analysis.get("companyName")) or "Bu marka"
    main_offer = clip_text(clean_line(analysis.get("offer")), 340)
    audience_summary = clip_text(
        clean_line(strategic_summary.get("bestFitAudience")) or clean_line(analysis.get("audience")),
        280,
    )
    positioning = clip_text(build_positioning_summary(analysis, strategic_summary, research), 260)
    differentiation = clip_text(
        clean_line(strategic_summary.get("differentiation")) or "Ayrıştırıcı unsur daha da keskinleştirilmeli.",
        220,
    )
    conversion_gap = clip_text(
        clean_line(strategic_summary.get("conversionGap")) or "Dönüşüm yolu daha net kurgulanmalı.",
        220,
    )
    content_angle = clip_text(
        clean_line(strategic_summary.get("contentAngle")) or "İçerik açısı henüz daha sistemli kurulmalı.",
        220,
    )
    growth_lever = clip_text(
        clean_line(strategic_summary.get("primaryGrowthLever")) or clean_line(analysis.get("opportunity")),
        320,
    )

    contact_lines = build_contact_lines(bundle)
    page_lines = build_page_lines(bundle)
    service_lines = format_signal_lines(research.service_offers, limit=6, empty="- Öne çıkan hizmet kümesi henüz netleşmedi.")
    product_lines = format_signal_lines(research.product_offers, limit=6, empty="- Öne çıkan ürün veya platform kümesi henüz netleşmedi.")
    audience_lines = format_signal_lines(
        research.audience_claims or research.audience_signals,
        limit=4,
        empty="- Hedef kitle sinyali sınırlı.",
    )
    pricing_lines = format_signal_lines(
        bundle.site_signals.pricing_signals + research.cta_claims,
        limit=5,
        empty="- Açık fiyat veya teklif sinyali görünmüyor.",
    )
    visual_lines = format_signal_lines(research.visual_signals, limit=4, empty="- Görsel sinyal sınırlı.")
    cta_lines = format_signal_lines(research.cta_claims or bundle.site_signals.cta_texts, limit=5, empty="- Belirgin CTA sinyali sınırlı.")
    trust_lines = format_signal_lines(research.trust_signals, limit=5, empty="- Güven dili sınırlı.")
    proof_lines = format_signal_lines(research.proof_claims or research.proof_points, limit=5, empty="- Görünür kanıt katmanı sınırlı.")
    message_lines = build_message_lines(main_offer, differentiation, research)
    market_lines = format_signal_lines(research.market_signals, limit=5, empty="- Kategori sinyali sınırlı.")
    geo_lines = format_signal_lines(
        [*research.geography_signals[:4], *research.language_signals[:4]],
        limit=6,
        empty="- Coğrafya ve dil sinyali sınırlı.",
    )
    seo_lines = format_signal_lines(research.seo_signals, limit=6, empty="- SEO ve içerik sinyali sınırlı.")
    topic_lines = format_signal_lines(research.content_topics, limit=6, empty="- İçerik konusu sinyali sınırlı.")
    competitor_lines = build_competitor_lines(analysis.get("competitors"), bundle)
    plan_lines = build_numbered_plan(analysis.get("firstMonthPlan"))
    quick_win_lines = build_quick_win_lines(bundle, goals)

    return [
        {
            "id": "business-profile",
            "filename": "business-profile.md",
            "title": "İşletme Profili",
            "blurb": "İş modeli, teklif yapısı ve hedef kitle özeti.",
            "content": f"""# İşletme Profili

## Genel Bakış
- Şirket: {company_name}
- Web sitesi: {bundle.website}
- Sektör yorumu: {clean_line(analysis.get('sector'))}
- Ana teklif: {main_offer}
- Fiyat pozisyonu: {clean_line(analysis.get('pricePosition'))}
- İstenen odak alanları: {goals_text}
- Bağlı platformlar: {connected_text}

## Konumlandırma
- Konumlandırma özeti: {positioning}
- Farklılaştırıcı unsur: {differentiation}

## Hedef Kitle
- Ana hedef kitle özeti: {audience_summary}
{audience_lines}

## Teklif Yapısı
### Öne Çıkan Hizmet Kümeleri
{service_lines}

### Öne Çıkan Ürün / Platform Kümeleri
{product_lines}

## Fiyat ve Dönüşüm Sinyalleri
{pricing_lines}

## Temas Noktaları
{contact_lines}

## Kritik Sayfalar
{page_lines}
""",
        },
        {
            "id": "brand-guidelines",
            "filename": "brand-guidelines.md",
            "title": "Marka Kılavuzu",
            "blurb": "Ton, görsel yön ve CTA davranışı için rehber.",
            "content": f"""# Marka Kılavuzu

## Marka Hissi
- Ton: {clean_line(analysis.get('tone'))}
- Ana vaat: {main_offer}
- Konumlandırma: {positioning}

## Görsel Yön
{visual_lines}

## Mesaj Sütunları
{message_lines}

## CTA Stili
{cta_lines}

## Güven Katmanı
{trust_lines}

## Kanıt Katmanı
{proof_lines}

## İçerik Üslubu
- Faydayı, uzmanlığı ve sonucu aynı cümle içinde buluştur.
- CTA öncesinde güven oluşturan kısa köprü metinler kullan.
- Görsel dil ile metin tonu aynı çizgide ilerlesin; sert veya dağınık geçişlerden kaçın.
""",
        },
        {
            "id": "market-research",
            "filename": "market-research.md",
            "title": "Pazar Araştırması",
            "blurb": "Kategori, rakip çerçevesi ve içerik fırsatları.",
            "content": f"""# Pazar Araştırması

## Muhtemel Rakip Çerçevesi
{competitor_lines}

## Pazar Sinyalleri
{market_lines}

## Coğrafya ve Dil
{geo_lines}

## SEO ve İçerik Fırsatları
{seo_lines}

## İçerik Konuları
{topic_lines}

## Riskler
- {conversion_gap}
- İçerik ve otorite katmanı rakiplerle karşılaştırıldığında daha görünür kurulmalı.
- Güven öğeleri CTA çevresinde zayıf kalırsa dönüşüm maliyeti yükselir.
""",
        },
        {
            "id": "strategy",
            "filename": "strategy.md",
            "title": "30 Günlük Strateji",
            "blurb": "İlk ayın kanal, teklif ve içerik öncelikleri.",
            "content": f"""# 30 Günlük Strateji

## Kuzey Yıldızı
{growth_lever}

## Kanal Önceliği
- Öncelikli odak: {goals_text}
- İçerik açısı: {content_angle}

## İlk 30 Gün Planı
{plan_lines}

## Hızlı Kazanımlar
{quick_win_lines}
""",
        },
    ]


def build_memory_file_map(memory_files: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for file_data in memory_files:
        if not isinstance(file_data, dict):
            continue
        file_id = clean_line(file_data.get("id"))
        filename = clean_line(file_data.get("filename"))
        if file_id:
            result[file_id] = file_data
        if filename:
            result[filename] = file_data
    return result


def content_meets_threshold(content: Any, headings: tuple[str, ...]) -> bool:
    text = clean_markdown(content)
    if len(text) < 320:
        return False
    return sum(1 for heading in headings if heading in text) >= 2


def content_has_quality_issues(content: Any) -> bool:
    text = clean_markdown(content).lower()
    issue_markers = (
        "bu alan için daha spesifik rekabet sinyali",
        "site sinyallerine göre en olası hedef kitle kümeleri",
        "general formu",
        "proof layer",
        "positioning:",
        "quick wins",
        "selected",
        "made with by",
        "services projects blog contact",
    )
    return any(marker in text for marker in issue_markers)


def build_positioning_summary(
    analysis: dict[str, Any],
    strategic_summary: dict[str, Any],
    research: Any,
) -> str:
    positioning = clean_line(strategic_summary.get("positioning"))
    if positioning and not looks_like_noise(positioning):
        return positioning

    if research.service_offers and research.product_offers:
        return "Marka, hem hizmet hem de ürün katmanını birlikte taşıyan hibrit bir teknoloji partneri gibi konumlanıyor."
    if research.product_offers:
        return "Marka, ürün ve platform odaklı bir değer teklifiyle konumlanıyor."
    if research.service_offers:
        return "Marka, hizmet ve çözüm ortağı ekseninde konumlanıyor."
    return clean_line(analysis.get("offer"))


def build_contact_lines(bundle: CrawlBundle) -> str:
    lines = []
    if bundle.contact_signals.emails:
        lines.append(f"- E-posta: {', '.join(bundle.contact_signals.emails[:6])}")
    if bundle.contact_signals.phones:
        lines.append(f"- Telefon: {', '.join(bundle.contact_signals.phones[:6])}")
    if bundle.contact_signals.socials:
        lines.append(f"- Sosyal bağlantılar: {', '.join(bundle.contact_signals.socials[:6])}")
    if bundle.contact_signals.addresses:
        lines.append(f"- Adres ipuçları: {' | '.join(bundle.contact_signals.addresses[:3])}")
    return "\n".join(lines) or "- Belirgin temas sinyali bulunamadı."


def build_page_lines(bundle: CrawlBundle) -> str:
    lines = []
    for page in bundle.pages[:8]:
        label = PAGE_TYPE_LABELS.get(page.page_type, page.page_type.capitalize())
        title = clean_line(page.title) or page.url
        lines.append(f"- {label}: {title}")
    return "\n".join(lines) or "- Kritik sayfa özeti üretilemedi."


def build_competitor_lines(competitors: Any, bundle: CrawlBundle) -> str:
    cleaned = [clean_line(item) for item in competitors or [] if clean_line(item)]
    cleaned = [item for item in cleaned if "daha spesifik rekabet sinyali" not in item.lower()]
    if len(cleaned) >= 3:
        return format_signal_lines(cleaned[:3], limit=3, empty="- Rakip çerçevesi henüz netleşmedi.")

    research = bundle.research_package
    if research.service_offers and research.product_offers:
        fallback = [
            "Hizmet ve ürün katmanını aynı anda taşıyan hibrit teknoloji markaları.",
            "Tek kategoriye odaklanan ama konumlandırması daha keskin rakipler.",
            "Vaka anlatımı ve güven katmanını daha görünür kullanan benzer oyuncular.",
        ]
    elif research.product_offers:
        fallback = [
            "Aynı problemi daha net anlatan ürün odaklı SaaS markaları.",
            "Kategoride içerik otoritesi daha güçlü rakip platformlar.",
            "Fiyat ve deneme akışını daha sade sunan alternatif çözümler.",
        ]
    else:
        fallback = [
            "Aynı hizmeti daha net teklif hiyerarşisiyle sunan ajans ve servis markaları.",
            "SEO görünürlüğü ve vaka anlatımı daha güçlü rakipler.",
            "Talep toplama akışı daha kısa ve güven veren alternatif çözümler.",
        ]
    return "\n".join(f"- {item}" for item in fallback)


def build_numbered_plan(items: Any) -> str:
    cleaned = [clean_line(item) for item in items or [] if clean_line(item)]
    if not cleaned:
        cleaned = [
            "Ana teklifi tek bir güçlü değer cümlesi etrafında sadeleştir.",
            "En görünür hizmet veya ürün kümeleri için ayrı açılış sayfaları hazırla.",
            "Güven sinyallerini form ve CTA çevresinde görünür hale getir.",
        ]
    return "\n".join(f"{index}. {item}" for index, item in enumerate(cleaned[:3], start=1))


def build_quick_win_lines(bundle: CrawlBundle, goals: list[str]) -> str:
    items = [
        "Ana teklif hiyerarşisini sadeleştir ve tek bir güçlü CTA belirle.",
        "En güçlü hizmet veya ürün kümeleri için ayrı açılış sayfası mantığı kur.",
        "Güven öğelerini form ve teklif bloklarının çevresinde görünür hale getir.",
    ]
    if "SEO" in goals:
        items.append("Arama niyeti güçlü içerik kümelerini haftalık üretim ritmine bağla.")
    elif bundle.contact_signals.emails or bundle.contact_signals.phones:
        items.append("İletişim noktalarını tüm kritik sayfalarda daha görünür hale getir.")
    return "\n".join(f"- {item}" for item in items[:4])


def build_message_lines(main_offer: str, differentiation: str, research: Any) -> str:
    items = [main_offer, differentiation]
    items.extend(research.service_offers[:2])
    items.extend(research.product_offers[:1])
    return format_signal_lines(
        items,
        limit=5,
        empty="- Mesaj sütunu için daha net bir değer önerisi kurulmalı.",
    )


def format_signal_lines(
    values: Iterable[Any],
    *,
    limit: int,
    empty: str,
) -> str:
    cleaned: list[str] = []
    for value in values:
        text = clean_line(value)
        if not text:
            continue
        cleaned.append(text)
    unique_lines = unique_preserve_order(cleaned)
    if not unique_lines:
        return empty
    return "\n".join(f"- {item}" for item in unique_lines[:limit])


def clean_markdown(value: Any) -> str:
    text = normalize_markdown_output(get_text(value))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_line(value: Any) -> str:
    text = normalize_text_output(get_text(value))
    if not text:
        return ""

    text = text.replace("CTA: ", "")
    text = re.sub(r"^[a-zA-ZçğıöşüÇĞİÖŞÜ ]+ formu:\s*", "Form alanları: ", text)
    text = re.sub(r"\s+", " ", text).strip(" -")
    if looks_like_noise(text):
        return ""
    return text


def looks_like_noise(text: str) -> bool:
    lowered = text.lower()
    if not lowered:
        return True
    if any(snippet in lowered for snippet in NOISE_SNIPPETS):
        return True
    navigation_hits = sum(1 for token in NAVIGATION_TOKENS if re.search(rf"\b{re.escape(token)}\b", lowered))
    if navigation_hits >= 4:
        return True
    if lowered in {"selected", "contact", "projects", "project", "blog"}:
        return True
    return False


def clip_text(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 1].rstrip(" ,.;:") + "…"


def unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def get_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""
