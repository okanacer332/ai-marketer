from __future__ import annotations

from urllib.parse import urlparse

from .scrape import CrawlBundle, PageSnapshot, ResearchPackage

FALLBACK_PROMPT_VERSION = "aylin-fallback-v2"
FALLBACK_ENGINE_VERSION = "heuristic-fallback-v2"


def build_fallback_analysis(
    bundle: CrawlBundle,
    goals: list[str],
    connected_platforms: list[str],
) -> dict:
    company_name = infer_company_name(bundle)
    active_goals = goals or ["SEO", "Sosyal Medya", "İçerik", "Ücretli Reklamlar"]
    research = bundle.research_package

    analysis = {
        "companyName": company_name,
        "domain": bundle.domain,
        "sector": infer_sector(bundle),
        "offer": infer_offer(bundle),
        "audience": infer_audience(bundle),
        "tone": infer_tone(bundle),
        "pricePosition": infer_price_position(bundle),
        "competitors": infer_competitors(bundle),
        "opportunity": infer_opportunity(bundle, active_goals, connected_platforms),
        "firstMonthPlan": build_first_month_plan(bundle, active_goals),
        "palette": infer_palette(bundle.domain, research),
    }

    return {
        "analysis": analysis,
        "memoryFiles": build_memory_files(analysis, bundle, active_goals, connected_platforms),
    }


def infer_company_name(bundle: CrawlBundle) -> str:
    research = bundle.research_package
    for candidate in research.company_name_candidates:
        value = candidate.strip()
        if value:
            return value

    primary = bundle.primary_page
    candidates = [
        primary.meta.get("ogSiteName", ""),
        primary.title.split("|")[0].split("-")[0].strip() if primary.title else "",
        bundle.site_signals.entity_labels[0] if bundle.site_signals.entity_labels else "",
    ]

    for candidate in candidates:
        value = candidate.strip()
        if value:
            return value

    domain_root = urlparse(bundle.website).netloc.replace("www.", "").split(".")[0]
    return " ".join(part.capitalize() for part in domain_root.split("-"))


def infer_sector(bundle: CrawlBundle) -> str:
    research = bundle.research_package
    if research.service_offers and research.product_offers:
        return "hem hizmet hem ürün/SaaS katmanı olan hibrit bir teknoloji işletmesi"
    if research.product_offers:
        return "ürün veya SaaS mantığıyla değer sunan dijital bir ürün işletmesi"
    if research.service_offers:
        return "hizmet, çözüm veya danışmanlık odağında çalışan bir işletme"
    if any("software" in page.raw_text.lower() or "saas" in page.raw_text.lower() for page in bundle.pages):
        return "yazılım veya SaaS odaklı bir dijital işletme"
    return "web sitesi üzerinden talep toplayan ve teklif anlatan dijital bir işletme"


def infer_offer(bundle: CrawlBundle) -> str:
    research = bundle.research_package
    for candidate in [
        *research.hero_messages,
        *research.positioning_signals,
        *research.offer_signals,
        bundle.primary_page.description,
    ]:
        value = candidate.strip()
        if value:
            return value

    return "Site, ziyaretçiye net bir değer önerisi sunmaya çalışan bir ürün veya hizmet anlatısı kuruyor."


def infer_audience(bundle: CrawlBundle) -> str:
    research = bundle.research_package
    if research.audience_signals:
        return "Site sinyallerine göre hedef kitle şu kümelerde yoğunlaşıyor: " + "; ".join(research.audience_signals[:4])

    text = " ".join(page.raw_text[:1200] for page in bundle.pages).lower()
    if any(token in text for token in ("agency", "ajans", "marka", "brand", "b2b", "enterprise")):
        return "karar vermeden önce kanıt, uzmanlık ve net ROI görmek isteyen işletme ekipleri ve karar vericiler"
    if any(token in text for token in ("shop", "store", "ürün", "kargo", "alışveriş")):
        return "ürün karşılaştıran, güven sinyali ve net fayda arayan son kullanıcılar veya e-ticaret alıcıları"
    if any(token in text for token in ("demo", "trial", "platform", "dashboard", "integration")):
        return "önce ürünü anlamak, sonra denemek isteyen dijital ekipler ve araç araştıran profesyoneller"
    return "web sitesinde netlik, güven ve hızlı karar desteği arayan potansiyel müşteriler"


def infer_tone(bundle: CrawlBundle) -> str:
    research = bundle.research_package
    combined = " ".join(
        [
            *research.visual_signals,
            *bundle.site_signals.cta_texts,
            bundle.primary_page.description,
        ]
    ).lower()

    if any(token in combined for token in ("dark", "premium", "sharp", "enterprise")):
        return "premium, kendinden emin ve teknoloji odaklı"
    if any(token in combined for token in ("free", "demo", "trial", "başla", "get", "start")):
        return "net, hızlı aksiyon çağıran ve dönüşüm odaklı"
    return "profesyonel, anlaşılır ve güven oluşturmaya çalışan"


def infer_price_position(bundle: CrawlBundle) -> str:
    signals = " ".join(bundle.site_signals.pricing_signals).lower()

    if any(token in signals for token in ("enterprise", "custom", "teklif")):
        return "yüksek değerli veya satış ekibi destekli fiyatlama"
    if any(token in signals for token in ("free", "ücretsiz", "$", "usd", "eur", "tl", "₺")):
        return "fiyat sinyali açık, karşılaştırılabilir ve dönüşüm odaklı"
    return "fiyat sinyali zayıf; değer üzerinden konumlanmaya çalışan"


def infer_competitors(bundle: CrawlBundle) -> list[str]:
    research = bundle.research_package
    if research.service_offers and research.product_offers:
        return [
            "aynı anda hem yazılım hizmeti hem ürün portföyü taşıyan hibrit teknoloji markaları",
            "tek bir kategoriye odaklı ama otorite iletişimi daha güçlü rakipler",
            "vaka anlatımı ve sosyal kanıtı daha görünür kullanan benzer işletmeler",
        ]

    technologies = {tech.lower() for tech in bundle.site_signals.technologies}
    page_types = {page.page_type for page in bundle.pages}

    if "shopify" in technologies or "woocommerce" in technologies:
        return [
            "aynı kategoride güçlü ürün sayfaları kuran niş e-ticaret markaları",
            "performans pazarlaması güçlü doğrudan tüketici markaları",
            "fiyat ve güven sinyalini daha net anlatan pazar liderleri",
        ]
    if "pricing" in page_types or any(page.forms for page in bundle.pages):
        return [
            "aynı hizmeti teklif formu ve vaka anlatımıyla satan ajans veya servis markaları",
            "kategoride daha güçlü SEO içeriği olan rakipler",
            "dönüşüm akışı daha kısa ve net olan alternatif çözümler",
        ]
    return [
        "arama sonuçlarında görünürlüğü daha yüksek kategori oyuncuları",
        "aynı problemi daha net mesajla çözen dijital rakipler",
        "sosyal kanıt ve güven öğelerini daha güçlü kullanan markalar",
    ]


def infer_opportunity(bundle: CrawlBundle, goals: list[str], connected_platforms: list[str]) -> str:
    research = bundle.research_package
    strongest_page = choose_strongest_page(bundle.pages)
    page_hint = strongest_page.title or strongest_page.url
    cta_hint = bundle.site_signals.cta_texts[0] if bundle.site_signals.cta_texts else "ana teklif"
    seo_hint = research.seo_signals[0] if research.seo_signals else "içerik yapısı"
    trust_hint = research.trust_signals[0] if research.trust_signals else "güven katmanı"
    platform_hint = (
        f" Bağlı platformlar hazır olduğunda {', '.join(connected_platforms)} verisiyle bu strateji daha da derinleşebilir."
        if connected_platforms
        else ""
    )

    return (
        f"En güçlü büyüme fırsatı, {page_hint} etrafında toplanan teklifi daha net bir dönüşüm akışına çevirmek. "
        f"Site şu anda '{cta_hint}' gibi çağrılarla talep toplamaya çalışıyor; ancak {seo_hint.lower()} ve "
        f"{trust_hint.lower()} tarafında daha görünür bir anlatı kurulduğunda {', '.join(goals[:3])} birlikte yükseltilebilir."
        f"{platform_hint}"
    )


def build_first_month_plan(bundle: CrawlBundle, goals: list[str]) -> list[str]:
    research = bundle.research_package
    page_mix = ", ".join(bundle.site_signals.page_mix[:3]) if bundle.site_signals.page_mix else "ana teklif sayfaları"
    cta_hint = bundle.site_signals.cta_texts[0] if bundle.site_signals.cta_texts else "ana CTA"
    trust_hint = research.trust_signals[0] if research.trust_signals else "güven sinyalleri"
    seo_hint = research.seo_signals[0] if research.seo_signals else "içerik fırsatları"

    return [
        f"{page_mix} etrafındaki teklif mimarisini sadeleştir ve '{cta_hint}' çağrısını tek bir birincil dönüşüm akışına bağla.",
        f"{goals[0]} odağında, {seo_hint.lower()} beslenen 3 güçlü landing page veya içerik kurgusu üret.",
        f"{trust_hint} etrafında sosyal kanıt, SSS ve form kopyalarını görünür şekilde yeniden düzenle.",
    ]


def infer_palette(domain: str, research: ResearchPackage) -> list[str]:
    theme_color = next(
        (
            signal.split(": ", 1)[1].split(",")[0].strip()
            for signal in research.visual_signals
            if signal.startswith("Theme color sinyali:")
        ),
        "",
    )
    if theme_color.startswith("#") and len(theme_color) in {4, 7}:
        checksum = sum(ord(char) for char in domain)
        companion_palettes = [
            [theme_color, "#0F172A", "#E2E8F0", "#F8FAFC"],
            [theme_color, "#11213B", "#D7DEEB", "#FFFFFF"],
            [theme_color, "#183153", "#F6F1E9", "#4FA095"],
        ]
        return companion_palettes[checksum % len(companion_palettes)]

    checksum = sum(ord(char) for char in domain)
    palettes = [
        ["#13343B", "#1F8A70", "#F2C14E", "#F8F5EF"],
        ["#183153", "#E86A33", "#F6F1E9", "#4FA095"],
        ["#0D3B66", "#3AAFA9", "#F4D35E", "#FAF7F0"],
    ]
    return palettes[checksum % len(palettes)]


def choose_strongest_page(pages: list[PageSnapshot]) -> PageSnapshot:
    def score(page: PageSnapshot) -> int:
        return (
            len(page.cta_texts) * 4
            + len(page.forms) * 5
            + len(page.pricing_signals) * 4
            + len(page.headings)
            + len(page.value_props)
            + len(page.trust_signals)
        )

    return max(pages, key=score)


def build_memory_files(
    analysis: dict,
    bundle: CrawlBundle,
    goals: list[str],
    connected_platforms: list[str],
) -> list[dict]:
    research = bundle.research_package
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
    tech_text = ", ".join(bundle.site_signals.technologies[:8]) if bundle.site_signals.technologies else "Belirgin teknoloji sinyali yok"
    pricing_text = "\n".join(f"- {value}" for value in bundle.site_signals.pricing_signals[:8]) or "- Açık fiyat sinyali görünmüyor"
    cta_text = "\n".join(f"- {value}" for value in bundle.site_signals.cta_texts[:10]) or "- Belirgin CTA sinyali sınırlı"
    trust_text = "\n".join(f"- {value}" for value in research.trust_signals[:8]) or "- Güven sinyali sınırlı"
    proof_text = "\n".join(f"- {value}" for value in research.proof_points[:8]) or "- Güçlü proof point sinyali sınırlı"
    audience_text = "\n".join(f"- {value}" for value in research.audience_signals[:8]) or "- Hedef kitle sinyali sınırlı"
    seo_text = "\n".join(f"- {value}" for value in research.seo_signals[:8]) or "- SEO sinyali sınırlı"
    visual_text = "\n".join(f"- {value}" for value in research.visual_signals[:6]) or "- Görsel sinyal sınırlı"
    connected_text = ", ".join(connected_platforms) if connected_platforms else "Henüz platform bağlanmadı"
    goals_text = ", ".join(goals)

    return [
        {
            "id": "business-profile",
            "filename": "isletme-profili.md",
            "title": "İşletme Profili",
            "blurb": "İş modeli, teklif mimarisi ve hedef kitle okuması.",
            "content": f"""# İşletme Profili

## Genel Bakış
- Şirket: {analysis['companyName']}
- Website: {bundle.website}
- Sektör yorumu: {analysis['sector']}
- Ana teklif: {analysis['offer']}
- Hedef kitle: {analysis['audience']}
- Fiyat pozisyonu: {analysis['pricePosition']}
- İstenen odak alanları: {goals_text}
- Bağlı platformlar: {connected_text}

## Konumlandırma Sinyalleri
{chr(10).join(f"- {value}" for value in research.positioning_signals[:6]) or "- Belirgin positioning sinyali sınırlı"}

## Hizmet / Ürün Yapısı
{chr(10).join(f"- {value}" for value in (research.service_offers[:8] + research.product_offers[:8])) or "- Teklif kırılımı sınırlı"}

## Hedef Kitle Sinyalleri
{audience_text}

## Fiyat ve Dönüşüm Sinyalleri
{pricing_text}

## Temas Noktaları
{contact_lines}

## İncelenen Kritik Sayfalar
{pages_markdown}
""",
        },
        {
            "id": "brand-guidelines",
            "filename": "marka-kilavuzu.md",
            "title": "Marka Kılavuzu",
            "blurb": "Ton, görsel yön ve CTA yaklaşımı için operasyonel çerçeve.",
            "content": f"""# Marka Kılavuzu

## Marka Hissi
- Ton: {analysis['tone']}
- Ana vaat: {analysis['offer']}
- Marka adı adayları: {', '.join(research.company_name_candidates[:4]) or analysis['companyName']}

## Görsel Yön
{visual_text}

## CTA Stili
{cta_text}

## Güven Dili
{trust_text}

## Proof Point Katmanı
{proof_text}

## Dil Kuralları
- Fazla teknikleşmeden, somut faydayı önceleyen cümleler kullan.
- Ziyaretçinin risk algısını azaltan güven dili kur.
- CTA metinlerinde tek bir ana aksiyonu öne çıkar.
- İçerikte marka ismi, teklif ve sonuç cümleleri birbiriyle tutarlı akmalı.

## Görsel Palet Önerisi
- Önerilen palet: {', '.join(analysis['palette'])}
- Teknoloji sinyalleri: {tech_text}
""",
        },
        {
            "id": "market-research",
            "filename": "pazar-arastirmasi.md",
            "title": "Pazar Araştırması",
            "blurb": "Kategori çerçevesi, rekabet okuması ve içerik fırsatları.",
            "content": f"""# Pazar Araştırması

## Muhtemel Rakip Çerçevesi
- {analysis['competitors'][0]}
- {analysis['competitors'][1]}
- {analysis['competitors'][2]}

## Pazar Sinyalleri
{chr(10).join(f"- {value}" for value in research.market_signals[:8]) or "- Pazar sinyali sınırlı"}

## Coğrafya ve Dil Sinyalleri
{chr(10).join(f"- {value}" for value in (research.geography_signals[:6] + research.language_signals[:6])) or "- Coğrafya / dil sinyali sınırlı"}

## SEO ve İçerik Fırsatları
{seo_text}

## İçerik Konuları
{chr(10).join(f"- {value}" for value in research.content_topics[:12]) or "- İçerik konusu sinyali sınırlı"}

## Riskler
- Güven katmanı zayıfsa teklifin ikna gücü düşer.
- Pricing veya dönüşüm yolu net değilse reklam ve SEO verimi birlikte düşer.
- Hedef kitle cümleleri dağınıksa içerik üretimi de parçalı kalır.
""",
        },
        {
            "id": "strategy",
            "filename": "strateji.md",
            "title": "30 Günlük Strateji",
            "blurb": "İlk ay uygulanacak kanal, teklif ve içerik öncelikleri.",
            "content": f"""# 30 Günlük Strateji

## Kuzey Yıldızı
{analysis['opportunity']}

## İlk 30 Gün Öncelikleri
1. {analysis['firstMonthPlan'][0]}
2. {analysis['firstMonthPlan'][1]}
3. {analysis['firstMonthPlan'][2]}

## Quick Wins
- Ana teklif sayfasında tek bir birincil CTA belirle ve tüm varyasyonları buna bağla.
- En güçlü hizmet / ürün kümelerini ayrı landing page mantığıyla yeniden paketle.
- Form çevresine sosyal kanıt, süreç anlatımı ve itiraz giderici kısa bloklar ekle.
- SEO sinyallerinden çıkan eksikleri blog, FAQ ve karşılaştırma içeriklerine dönüştür.

## Kanal Yorumu
- Öncelikli odak: {goals_text}
- İlk hafta: teklif netliği ve dönüşüm akışı
- İkinci hafta: SEO / içerik temeli
- Üçüncü hafta: yeniden pazarlama ve e-posta mantığı
- Dördüncü hafta: kampanya optimizasyonu ve ölçüm düzeni
""",
        },
    ]
