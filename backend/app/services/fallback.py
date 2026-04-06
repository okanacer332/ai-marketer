from __future__ import annotations

from urllib.parse import urlparse

from .scrape import CrawlBundle, PageSnapshot, ResearchPackage

FALLBACK_PROMPT_VERSION = "aylin-fallback-v3"
FALLBACK_ENGINE_VERSION = "heuristic-fallback-v3"


def build_fallback_analysis(
    bundle: CrawlBundle,
    goals: list[str],
    connected_platforms: list[str],
) -> dict:
    company_name = infer_company_name(bundle)
    active_goals = goals or ["SEO", "Sosyal Medya", "İçerik", "Ücretli Reklamlar"]

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
        "palette": infer_palette(bundle.domain, bundle.research_package),
    }

    return {
        "analysis": analysis,
        "memoryFiles": [],
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
        return "Hem hizmet hem ürün katmanı olan hibrit bir dijital işletme"
    if research.product_offers:
        return "Ürün, platform veya SaaS mantığıyla değer sunan dijital bir işletme"
    if research.service_offers:
        return "Hizmet, çözüm veya danışmanlık odağında çalışan bir işletme"
    if any("software" in page.raw_text.lower() or "saas" in page.raw_text.lower() for page in bundle.pages):
        return "Yazılım veya SaaS ekseninde konumlanan dijital bir işletme"
    return "Web sitesi üzerinden talep toplayan dijital bir işletme"


def infer_offer(bundle: CrawlBundle) -> str:
    research = bundle.research_package
    company_name = infer_company_name(bundle)
    if research.service_offers and research.product_offers:
        return (
            f"{company_name}, özel çözüm geliştirme hizmetlerini kendi ürün ve platformlarıyla destekleyen "
            "hibrit bir teknoloji partneri gibi konumlanıyor."
        )
    if research.service_offers:
        top_services = ", ".join(filter_meaningful_items(research.service_offers, limit=3))
        if top_services:
            return f"{company_name}, {top_services} etrafında şekillenen hizmet odaklı bir teknoloji partneri gibi görünüyor."
    if research.product_offers:
        top_products = ", ".join(filter_meaningful_items(research.product_offers, limit=3))
        if top_products:
            return f"{company_name}, {top_products} etrafında şekillenen ürün ve platform odaklı bir yapı sunuyor."

    candidates = [
        bundle.primary_page.description,
        *research.positioning_signals,
        *research.core_value_props,
        *research.offer_signals,
        *research.hero_messages,
    ]
    for candidate in filter_meaningful_items(candidates, limit=8):
        return candidate

    return "Site, ziyaretçiye net bir değer önermeye çalışan bir ürün veya hizmet anlatısı kuruyor."


def infer_audience(bundle: CrawlBundle) -> str:
    research = bundle.research_package
    audience_claims = filter_audience_items(research.audience_claims)
    audience_signals = filter_audience_items(research.audience_signals)

    if audience_claims:
        joined = "; ".join(audience_claims[:3])
        return f"Site sinyallerine göre en olası hedef kitle kümeleri şunlar: {joined}"

    if audience_signals:
        joined = "; ".join(audience_signals[:3])
        return f"Site sinyallerine göre hedef kitle şu kümelerde yoğunlaşıyor: {joined}"

    text = " ".join(page.raw_text[:1200] for page in bundle.pages).lower()
    if research.service_offers and research.product_offers:
        return "Dijital dönüşüm, otomasyon ve yeni ürün geliştirme ihtiyacı olan işletme sahipleri, operasyon ekipleri ve teknoloji karar vericileri"
    if any(token in text for token in ("agency", "ajans", "marka", "brand", "b2b", "enterprise")):
        return "Karar vermeden önce uzmanlık, güven ve yatırım geri dönüşü görmek isteyen iş ekipleri ve karar vericiler"
    if any(token in text for token in ("shop", "store", "ürün", "kargo", "alışveriş")):
        return "Ürün karşılaştıran, güven sinyali ve net fayda arayan son kullanıcılar veya e-ticaret alıcıları"
    if any(token in text for token in ("demo", "trial", "platform", "dashboard", "integration")):
        return "Önce ürünü anlamak, sonra denemek isteyen dijital ekipler ve profesyonel alıcılar"
    return "Web sitesinde netlik, güven ve hızlı karar desteği arayan potansiyel müşteriler"


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
        return "Premium, kendinden emin ve teknoloji odaklı"
    if any(token in combined for token in ("free", "demo", "trial", "başla", "get", "start")):
        return "Net, aksiyon çağıran ve dönüşüm odaklı"
    return "Profesyonel, anlaşılır ve güven oluşturmaya çalışan"


def infer_price_position(bundle: CrawlBundle) -> str:
    pricing_inputs = bundle.site_signals.pricing_signals + bundle.research_package.semantic_zones.get("pricing", [])
    signals = " ".join(pricing_inputs).lower()

    if any(token in signals for token in ("enterprise", "custom", "özel teklif", "teklif al")):
        return "Yüksek değerli veya satış ekibi destekli fiyatlama"
    if any(token in signals for token in ("free", "ücretsiz", "$", "usd", "eur", "tl", "₺")):
        return "Fiyat sinyali açık, karşılaştırılabilir ve dönüşüm odaklı"
    return "Fiyat sinyali zayıf; değer üzerinden konumlanmaya çalışan"


def infer_competitors(bundle: CrawlBundle) -> list[str]:
    research = bundle.research_package
    if research.service_offers and research.product_offers:
        return [
            "Hem hizmet hem ürün taşıyan hibrit teknoloji markaları",
            "Tek kategoriye odaklanan ama otorite iletişimi daha güçlü rakipler",
            "Vaka anlatımı ve sosyal kanıtı daha görünür kullanan benzer işletmeler",
        ]

    technologies = {tech.lower() for tech in bundle.site_signals.technologies}
    page_types = {page.page_type for page in bundle.pages}

    if "shopify" in technologies or "woocommerce" in technologies:
        return [
            "Aynı kategoride güçlü ürün sayfaları kuran niş e-ticaret markaları",
            "Performans pazarlaması güçlü doğrudan tüketici markaları",
            "Fiyat ve güven sinyalini daha net anlatan pazar liderleri",
        ]
    if "pricing" in page_types or any(page.forms for page in bundle.pages):
        return [
            "Aynı hizmeti teklif formu ve vaka anlatımıyla satan ajans veya servis markaları",
            "Kategoride daha güçlü SEO içeriği olan rakipler",
            "Dönüşüm akışı daha kısa ve net olan alternatif çözümler",
        ]
    return [
        "Arama sonuçlarında görünürlüğü daha yüksek kategori oyuncuları",
        "Aynı problemi daha net mesajla çözen dijital rakipler",
        "Sosyal kanıt ve güven öğelerini daha güçlü kullanan markalar",
    ]


def infer_opportunity(bundle: CrawlBundle, goals: list[str], connected_platforms: list[str]) -> str:
    research = bundle.research_package
    offer_frame = infer_offer(bundle)
    proof_claim = first_non_empty(filter_meaningful_items(research.proof_claims)) or first_non_empty(filter_meaningful_items(research.trust_signals)) or "güven katmanı"
    seo_hint = first_non_empty(research.seo_signals) or "içerik yapısı"
    cta_hint = first_non_empty(clean_cta_items(research.cta_claims, bundle.site_signals.cta_texts)) or "ana dönüşüm çağrısı"
    platform_hint = (
        f" Bağlı platformlar hazır olduğunda {', '.join(connected_platforms)} verisiyle bu strateji daha da keskinleşebilir."
        if connected_platforms
        else ""
    )

    return (
        f"En güçlü büyüme fırsatı, '{offer_frame}' etrafındaki ana teklifi daha görünür ve ikna edici bir talep akışına çevirmek. "
        f"Şu an {cta_hint.lower()} tarafında bir çağrı var; ancak {proof_claim.lower()} ve {seo_hint.lower()} daha görünür hale getirildiğinde "
        f"{', '.join(goals[:3])} birlikte daha verimli çalışabilir.{platform_hint}"
    )


def build_first_month_plan(bundle: CrawlBundle, goals: list[str]) -> list[str]:
    research = bundle.research_package
    primary_cta = first_non_empty(clean_cta_items([], bundle.site_signals.cta_texts)) or first_non_empty(clean_cta_items(research.cta_claims, [])) or "ana CTA"
    proof_hint = first_non_empty(filter_meaningful_items(research.proof_claims)) or first_non_empty(filter_meaningful_items(research.trust_signals)) or "güven sinyalleri"
    seo_hint = first_non_empty(research.seo_signals) or "SEO yüzeyi"
    content_hint = first_non_empty(filter_meaningful_items(research.content_topics)) or first_non_empty(filter_meaningful_items(research.supporting_benefits)) or "teklif etrafındaki içerik kümeleri"

    return [
        f"Teklif hiyerarşisini sadeleştir ve '{primary_cta}' etrafında tek bir ana dönüşüm yolu kur.",
        f"{goals[0]} odağında {seo_hint.lower()} ve {content_hint.lower()} etrafında üç güçlü açılış sayfası veya içerik kümesi oluştur.",
        f"{proof_hint} sinyalini form, CTA ve teklif bloklarının etrafında görünür hale getir.",
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
    goals_text = ", ".join(goals)
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

    return [
        {
            "id": "business-profile",
            "filename": "isletme-profili.md",
            "title": "İşletme Profili",
            "blurb": "İş modeli, teklif mimarisi ve hedef kitle özeti.",
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

## Ana Değer Önerileri
{bullet_list(research.core_value_props, empty='- Ana değer önerisi sinyali sınırlı')}

## Hizmet / Ürün Yapısı
{bullet_list(research.service_offers + research.product_offers, empty='- Teklif kırılımı sınırlı')}

## Hedef Kitle Sinyalleri
{bullet_list(research.audience_claims or research.audience_signals, empty='- Hedef kitle sinyali sınırlı')}

## Fiyat ve Dönüşüm Sinyalleri
{bullet_list(bundle.site_signals.pricing_signals + research.cta_claims, empty='- Açık fiyat ve dönüşüm sinyali sınırlı')}

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
- Konumlandırma özeti: {first_non_empty(research.positioning_signals) or analysis['offer']}

## Görsel Yön
{bullet_list(research.visual_signals, empty='- Görsel sinyal sınırlı')}

## CTA Stili
{bullet_list(research.cta_claims or bundle.site_signals.cta_texts, empty='- CTA sinyali sınırlı')}

## Güven Dili
{bullet_list(research.proof_claims or research.trust_signals, empty='- Güven sinyali sınırlı')}

## Mesaj Sütunları
{bullet_list(research.core_value_props + research.supporting_benefits[:4], empty='- Mesaj sütunu sinyali sınırlı')}
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
{bullet_list(research.market_signals, empty='- Pazar sinyali sınırlı')}

## SEO ve İçerik Fırsatları
{bullet_list(research.seo_signals + research.content_topics[:6], empty='- SEO ve içerik sinyali sınırlı')}

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
- En güçlü hizmet veya ürün kümelerini ayrı landing page mantığıyla yeniden paketle.
- Form çevresine sosyal kanıt, süreç anlatımı ve itiraz giderici kısa bloklar ekle.
- SEO sinyallerinden çıkan eksikleri blog, SSS ve karşılaştırma içeriklerine dönüştür.
""",
        },
    ]


def bullet_list(values: list[str], *, empty: str) -> str:
    cleaned = [value.strip() for value in values if isinstance(value, str) and value.strip()]
    return "\n".join(f"- {value}" for value in cleaned[:10]) or empty


def filter_meaningful_items(values: list[str], *, limit: int = 10) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        text = value.strip()
        lowered = text.lower()
        if not text:
            continue
        if any(marker in lowered for marker in ("selected", "devamını oku", "read more", "made with", "services projects blog contact", "copyright")):
            continue
        if "@" in text and "telefon" in lowered:
            continue
        cleaned.append(text)
    return cleaned[:limit]


def filter_audience_items(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in filter_meaningful_items(values, limit=8):
        lowered = value.lower()
        if any(marker in lowered for marker in ("email", "telefon", "konum", "bize ulaşın", "gönder", "24 saat", "nda")):
            continue
        cleaned.append(value)
    return cleaned[:4]


def clean_cta_items(primary: list[str], fallback: list[str]) -> list[str]:
    values: list[str] = []
    for item in [*primary, *fallback]:
        if not isinstance(item, str):
            continue
        text = item.replace("CTA:", "").strip()
        if not text:
            continue
        values.append(text)
    return values[:6]


def first_non_empty(values: list[str]) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
