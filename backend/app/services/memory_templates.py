from __future__ import annotations

from typing import Any

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
        "requiredHeadings": ("# 30 Günlük Strateji", "## Kuzey Yıldızı", "## Quick Wins"),
    },
]


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
        use_candidate = content_meets_threshold(candidate_content, spec["requiredHeadings"])

        normalized.append(
            {
                "id": spec["id"],
                "filename": spec["filename"],
                "title": get_text(candidate.get("title")) or fallback["title"],
                "blurb": get_text(candidate.get("blurb")) or fallback["blurb"],
                "content": get_text(candidate_content) if use_candidate else fallback["content"],
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
    goals_text = ", ".join(goals) if goals else "SEO, Sosyal Medya, İçerik"
    connected_text = ", ".join(connected_platforms) if connected_platforms else "Henüz platform bağlanmadı"
    pages_markdown = "\n".join(
        f"- {page.page_type}: {page.title or page.url}"
        for page in bundle.pages[:8]
    )
    contact_lines = "\n".join(
        line
        for line in [
            f"- E-posta: {', '.join(bundle.contact_signals.emails[:6])}" if bundle.contact_signals.emails else "",
            f"- Telefon: {', '.join(bundle.contact_signals.phones[:6])}" if bundle.contact_signals.phones else "",
            f"- Sosyal: {', '.join(bundle.contact_signals.socials[:6])}" if bundle.contact_signals.socials else "",
            f"- Adres: {' | '.join(bundle.contact_signals.addresses[:3])}" if bundle.contact_signals.addresses else "",
        ]
        if line
    ) or "- Belirgin temas sinyali bulunamadı"
    trust_text = "\n".join(f"- {value}" for value in research.trust_signals[:8]) or "- Güven sinyali sınırlı"
    proof_text = "\n".join(f"- {value}" for value in research.proof_points[:8]) or "- Proof point sinyali sınırlı"
    audience_text = "\n".join(f"- {value}" for value in research.audience_signals[:8]) or "- Hedef kitle sinyali sınırlı"
    service_text = "\n".join(f"- {value}" for value in research.service_offers[:8]) or "- Hizmet sinyali sınırlı"
    product_text = "\n".join(f"- {value}" for value in research.product_offers[:8]) or "- Ürün sinyali sınırlı"
    pricing_text = "\n".join(f"- {value}" for value in bundle.site_signals.pricing_signals[:8]) or "- Açık fiyat sinyali görünmüyor"
    cta_text = "\n".join(f"- {value}" for value in bundle.site_signals.cta_texts[:10]) or "- Belirgin CTA sinyali sınırlı"
    seo_text = "\n".join(f"- {value}" for value in research.seo_signals[:8]) or "- SEO sinyali sınırlı"
    visual_text = "\n".join(f"- {value}" for value in research.visual_signals[:6]) or "- Görsel sinyal sınırlı"
    market_text = "\n".join(f"- {value}" for value in research.market_signals[:8]) or "- Pazar sinyali sınırlı"
    geo_text = "\n".join(f"- {value}" for value in (research.geography_signals[:4] + research.language_signals[:4])) or "- Coğrafya / dil sinyali sınırlı"
    topics_text = "\n".join(f"- {value}" for value in research.content_topics[:12]) or "- İçerik konusu sinyali sınırlı"
    positioning = get_text(strategic_summary.get("positioning")) or get_text(analysis.get("offer"))
    differentiation = get_text(strategic_summary.get("differentiation")) or "Ayrıştırıcı unsur daha da keskinleştirilmeli."
    conversion_gap = get_text(strategic_summary.get("conversionGap")) or "Dönüşüm yolu daha net kurgulanmalı."
    content_angle = get_text(strategic_summary.get("contentAngle")) or "İçerik açısı henüz daha sistemli kurulmalı."
    growth_lever = get_text(strategic_summary.get("primaryGrowthLever")) or get_text(analysis.get("opportunity"))

    return [
        {
            "id": "business-profile",
            "filename": "business-profile.md",
            "title": "İşletme Profili",
            "blurb": "İş modeli, teklif yapısı ve hedef kitle özeti.",
            "content": f"""# İşletme Profili

## Genel Bakış
- Şirket: {get_text(analysis.get('companyName'))}
- Website: {bundle.website}
- Sektör yorumu: {get_text(analysis.get('sector'))}
- Ana teklif: {get_text(analysis.get('offer'))}
- Fiyat pozisyonu: {get_text(analysis.get('pricePosition'))}
- İstenen odak alanları: {goals_text}
- Bağlı platformlar: {connected_text}

## Konumlandırma
- Positioning özeti: {positioning}
- Farklılaştırıcı unsur: {differentiation}

## Hedef Kitle
- Ana hedef kitle özeti: {get_text(analysis.get('audience'))}
{audience_text}

## Teklif Yapısı
### Hizmet Kümeleri
{service_text}

### Ürün / Platform Kümeleri
{product_text}

## Fiyat ve Dönüşüm Sinyalleri
{pricing_text}

## Temas Noktaları
{contact_lines}

## Kritik Sayfalar
{pages_markdown}
""",
        },
        {
            "id": "brand-guidelines",
            "filename": "brand-guidelines.md",
            "title": "Marka Kılavuzu",
            "blurb": "Ton, görsel yön ve CTA davranışı için rehber.",
            "content": f"""# Marka Kılavuzu

## Marka Hissi
- Ton: {get_text(analysis.get('tone'))}
- Ana vaat: {get_text(analysis.get('offer'))}
- Positioning: {positioning}

## Görsel Yön
{visual_text}

## CTA Stili
{cta_text}

## Güven Dili
{trust_text}

## Proof Layer
{proof_text}

## İçerik Üslubu
- Netlik, uzmanlık ve sonuç cümlelerini birlikte taşı.
- CTA öncesinde güven oluşturan kısa köprü metinler kullan.
- Görsel dil ile metin tonu aynı premium / net çizgide akmalı.
""",
        },
        {
            "id": "market-research",
            "filename": "market-research.md",
            "title": "Pazar Araştırması",
            "blurb": "Kategori, rakip çerçevesi ve içerik fırsatları.",
            "content": f"""# Pazar Araştırması

## Muhtemel Rakip Çerçevesi
- {safe_list_item(analysis.get('competitors'), 0)}
- {safe_list_item(analysis.get('competitors'), 1)}
- {safe_list_item(analysis.get('competitors'), 2)}

## Pazar Sinyalleri
{market_text}

## Coğrafya ve Dil
{geo_text}

## SEO ve İçerik Fırsatları
{seo_text}

## İçerik Konuları
{topics_text}

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
1. {safe_list_item(analysis.get('firstMonthPlan'), 0)}
2. {safe_list_item(analysis.get('firstMonthPlan'), 1)}
3. {safe_list_item(analysis.get('firstMonthPlan'), 2)}

## Quick Wins
- Teklif hiyerarşisini sadeleştir ve tek ana CTA belirle.
- En güçlü hizmet / ürün kümeleri için ayrı landing page mantığı kur.
- Güven öğelerini form ve CTA çevresinde görünür hale getir.
- İçerik kümelerini haftalık üretim ritmine bağla.
""",
        },
    ]


def build_memory_file_map(memory_files: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for file_data in memory_files:
        if not isinstance(file_data, dict):
            continue
        file_id = get_text(file_data.get("id"))
        filename = get_text(file_data.get("filename"))
        if file_id:
            result[file_id] = file_data
        if filename:
            result[filename] = file_data
    return result


def content_meets_threshold(content: Any, headings: tuple[str, ...]) -> bool:
    text = get_text(content)
    if len(text) < 320:
        return False
    return sum(1 for heading in headings if heading in text) >= 2


def safe_list_item(value: Any, index: int) -> str:
    if isinstance(value, list) and index < len(value) and isinstance(value[index], str) and value[index].strip():
        return value[index].strip()
    return "Bu alan için daha spesifik rekabet sinyali üretmek gerekiyor."


def get_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""
