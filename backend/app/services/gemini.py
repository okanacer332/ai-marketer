from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .scrape import CrawlBundle, PageSnapshot, ResearchPackage

GEMINI_PROMPT_VERSION = "aylin-gemini-v2"


async def generate_analysis_with_gemini(
    bundle: CrawlBundle,
    goals: list[str],
    connected_platforms: list[str],
) -> dict[str, Any] | None:
    api_key = os.getenv("GEMINI_API_KEY", "")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    if not api_key:
        return None

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": build_prompt(bundle, goals, connected_platforms),
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }

    async with httpx.AsyncClient(timeout=60.0, verify=should_verify_ssl()) as client:
        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": api_key},
            json=payload,
        )
        response.raise_for_status()

    text = extract_candidate_text(response.json())
    if not text:
        return None

    parsed = json.loads(text)
    parsed["memoryFiles"] = ensure_memory_file_ids(parsed.get("memoryFiles", []))
    return parsed


def build_prompt(
    bundle: CrawlBundle,
    goals: list[str],
    connected_platforms: list[str],
) -> str:
    connected_text = ", ".join(connected_platforms) if connected_platforms else "Henüz bağlanmadı"
    focus_text = ", ".join(goals) if goals else "SEO, Sosyal Medya, İçerik, E-posta, Ücretli Reklamlar"
    note_text = " | ".join(bundle.notes[:10]) if bundle.notes else "Yok"
    email_text = ", ".join(bundle.contact_signals.emails[:8]) if bundle.contact_signals.emails else "Yok"
    phone_text = ", ".join(bundle.contact_signals.phones[:8]) if bundle.contact_signals.phones else "Yok"
    social_text = ", ".join(bundle.contact_signals.socials[:8]) if bundle.contact_signals.socials else "Yok"
    address_text = " | ".join(bundle.contact_signals.addresses[:5]) if bundle.contact_signals.addresses else "Yok"
    technologies_text = join_or_none(bundle.site_signals.technologies[:10])
    currencies_text = join_or_none(bundle.site_signals.currencies[:6])
    page_mix_text = join_or_none(bundle.site_signals.page_mix[:8], separator=" | ")
    cta_text = join_or_none(bundle.site_signals.cta_texts[:14], separator=" | ")
    entity_text = join_or_none(bundle.site_signals.entity_labels[:16], separator=" | ")
    pricing_text = join_or_none(bundle.site_signals.pricing_signals[:10], separator=" | ")
    faq_text = join_or_none(bundle.site_signals.faq_highlights[:8], separator=" | ")
    pages_block = "\n\n".join(build_page_block(page) for page in bundle.pages[:7])
    research_block = build_research_block(bundle.research_package)

    return f"""
Sen Aylin'sin. Türkçe konuşan, üst seviye bir dijital pazarlama stratejisti ve araştırmacısısın.

        Sana çok sayfalı bir website taraması ve bu taramadan çıkarılmış bir araştırma paketi veriliyor.
Görevin, işletmeyi gerçekten anlayan bir ilk analiz üretmek.

Çalışma ilkeleri:
- Sadece verilen kanıtlara dayan.
- Emin olmadığın yerde kesin konuşma; "görünüşe göre", "site sinyallerine göre", "muhtemelen" gibi temkinli ifadeler kullan.
- Yüzeysel özet istemiyorum; ticari olarak işe yarayan, spesifik ve uygulanabilir sentez istiyorum.
- Çıktının tamamı Türkçe olacak.
- JSON dışında hiçbir şey yazma.

Website: {bundle.website}
Alan adı: {bundle.domain}
İstenen odak alanları: {focus_text}
Bağlı platformlar: {connected_text}
Tarama notları: {note_text}

Temas sinyalleri:
- E-posta: {email_text}
- Telefon: {phone_text}
- Sosyal bağlantılar: {social_text}
- Adres ipuçları: {address_text}

Site genel sinyalleri:
- Teknolojiler: {technologies_text}
- Para birimleri: {currencies_text}
- Sayfa dağılımı: {page_mix_text}
- CTA örnekleri: {cta_text}
- Tekrarlayan ürün/hizmet başlıkları: {entity_text}
- Fiyat sinyalleri: {pricing_text}
- SSS sinyalleri: {faq_text}

Araştırma paketi:
{research_block}

İncelenen sayfalar:
{pages_block}

Görev:
1. İşletmenin tam olarak ne sattığını, teklif mimarisini ve iş modelini çöz.
2. Hedef kitleyi ana segmentler ve satın alma motivasyonlarıyla birlikte yorumla.
3. Konumlandırmayı ayakta tutan veya zayıflatan temel sinyalleri belirle.
4. Güven, netlik, dönüşüm akışı ve içerik tarafındaki en kritik boşlukları çıkar.
5. SEO, içerik, sosyal medya, e-posta ve ücretli reklamlar için ilk güçlü kaldıraçları bul.
6. Dört hafıza dosyasını profesyonel, dolu ve markaya özgü şekilde yaz.

Tam olarak aşağıdaki JSON şemasına uyan tek bir nesne döndür:
{{
  "analysis": {{
    "companyName": "string",
    "domain": "string",
    "sector": "string",
    "offer": "string",
    "audience": "string",
    "tone": "string",
    "pricePosition": "string",
    "competitors": ["string", "string", "string"],
    "opportunity": "string",
    "firstMonthPlan": ["string", "string", "string"],
    "palette": ["#123456", "#234567", "#345678", "#456789"]
  }},
  "memoryFiles": [
    {{
      "filename": "isletme-profili.md",
      "title": "İşletme Profili",
      "blurb": "kısa cümle",
      "content": "markdown"
    }},
    {{
      "filename": "marka-kilavuzu.md",
      "title": "Marka Kılavuzu",
      "blurb": "kısa cümle",
      "content": "markdown"
    }},
    {{
      "filename": "pazar-arastirmasi.md",
      "title": "Pazar Araştırması",
      "blurb": "kısa cümle",
      "content": "markdown"
    }},
    {{
      "filename": "strateji.md",
      "title": "30 Günlük Strateji",
      "blurb": "kısa cümle",
      "content": "markdown"
    }}
  ]
}}

Kalite kuralları:
- `analysis.companyName` gerçek marka adı gibi okunmalı.
- `analysis.offer` işletmenin değer teklifini tek cümlede, mümkün olduğunca net anlatmalı.
- `analysis.audience` sadece "müşteriler" dememeli; segment ve motivasyon içermeli.
- `analysis.opportunity` tek paragrafta en güçlü büyüme fırsatını anlatmalı.
- `analysis.firstMonthPlan` kısa ama uygulanabilir üç aksiyon olmalı.
- İşletme Profili belgesinde iş modeli, ürün/hizmet kümeleri, temas sinyalleri, fiyat sinyalleri ve kritik sayfalar olmalı.
- Marka Kılavuzu belgesinde ton, görsel yön, CTA dili, güven dili ve mesaj sütunları olmalı.
- Pazar Araştırması belgesinde rekabet çerçevesi, kategori boşlukları, SEO/içerik fırsatları ve riskler olmalı.
- 30 Günlük Strateji belgesinde kanal öncelikleri, haftalık aksiyon mantığı ve quick win listesi olmalı.
- Belgeleri birer kısa paragrafla geçiştirme; gerçek çalışma dokümanı gibi yaz.
- Markdown fence kullanma.
""".strip()


def build_research_block(research_package: ResearchPackage) -> str:
    return "\n".join(
        [
            f"- Marka adı adayları: {join_or_none(research_package.company_name_candidates, separator=' | ')}",
            f"- Hero mesajları: {join_or_none(research_package.hero_messages, separator=' | ')}",
            f"- Konumlandırma sinyalleri: {join_or_none(research_package.positioning_signals, separator=' | ')}",
            f"- Teklif sinyalleri: {join_or_none(research_package.offer_signals, separator=' | ')}",
            f"- Hizmet teklifleri: {join_or_none(research_package.service_offers, separator=' | ')}",
            f"- Ürün teklifleri: {join_or_none(research_package.product_offers, separator=' | ')}",
            f"- Hedef kitle sinyalleri: {join_or_none(research_package.audience_signals, separator=' | ')}",
            f"- Güven sinyalleri: {join_or_none(research_package.trust_signals, separator=' | ')}",
            f"- Kanıt / proof point sinyalleri: {join_or_none(research_package.proof_points, separator=' | ')}",
            f"- Dönüşüm aksiyonları: {join_or_none(research_package.conversion_actions, separator=' | ')}",
            f"- İçerik konuları: {join_or_none(research_package.content_topics, separator=' | ')}",
            f"- SEO sinyalleri: {join_or_none(research_package.seo_signals, separator=' | ')}",
            f"- Coğrafya sinyalleri: {join_or_none(research_package.geography_signals, separator=' | ')}",
            f"- Dil sinyalleri: {join_or_none(research_package.language_signals, separator=' | ')}",
            f"- Pazar sinyalleri: {join_or_none(research_package.market_signals, separator=' | ')}",
            f"- Görsel sinyaller: {join_or_none(research_package.visual_signals, separator=' | ')}",
        ]
    )


def build_page_block(page: PageSnapshot) -> str:
    forms_text = (
        " | ".join(
            f"{form.method} {form.action} [{', '.join(form.fields[:5])}]"
            for form in page.forms[:3]
        )
        if page.forms
        else "Yok"
    )
    faq_text = (
        " | ".join(f"{faq.question} -> {faq.answer[:120]}" for faq in page.faq_items[:3])
        if page.faq_items
        else "Yok"
    )
    meta_text = (
        " | ".join(f"{key}: {value}" for key, value in page.meta.items())
        if page.meta
        else "Yok"
    )
    tech_text = join_or_none(page.technologies[:6])
    image_text = join_or_none(page.image_alts[:6], separator=" | ")
    hero_text = join_or_none(page.hero_messages[:4], separator=" | ")
    audience_text = join_or_none(page.audience_signals[:4], separator=" | ")
    trust_text = join_or_none(page.trust_signals[:4], separator=" | ")
    proof_text = join_or_none(page.proof_points[:4], separator=" | ")

    return f"""URL: {page.url}
Sayfa tipi: {page.page_type}
Fetch modu: {page.fetch_mode}
HTTP durum: {page.status_code}
Başlık: {page.title or 'Yok'}
Açıklama: {page.description or 'Yok'}
Meta: {meta_text}
Başlık hiyerarşisi: {join_or_none(page.headings[:8], separator=' | ')}
Navigasyon: {join_or_none(page.nav_labels[:10], separator=' | ')}
Hero mesajları: {hero_text}
CTA'lar: {join_or_none(page.cta_texts[:8], separator=' | ')}
Değer önerileri: {join_or_none(page.value_props[:8], separator=' | ')}
Hedef kitle sinyalleri: {audience_text}
Güven sinyalleri: {trust_text}
Proof point sinyalleri: {proof_text}
Fiyat sinyalleri: {join_or_none(page.pricing_signals[:6], separator=' | ')}
Tekrarlayan varlıklar: {join_or_none(page.entity_labels[:10], separator=' | ')}
Formlar: {forms_text}
SSS: {faq_text}
Teknolojiler: {tech_text}
Görsel alt metinleri: {image_text}
Structured data: {join_or_none(page.structured_data[:4], separator=' || ')}
Ana içerik özeti:
{(page.main_content or page.excerpt)[:2200]}"""


def extract_candidate_text(response_json: dict[str, Any]) -> str:
    candidates = response_json.get("candidates", [])
    if not candidates:
        return ""

    parts = candidates[0].get("content", {}).get("parts", [])
    text_parts = [part.get("text", "") for part in parts if part.get("text")]
    return "\n".join(text_parts).strip()


def ensure_memory_file_ids(memory_files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    desired_ids = [
        "business-profile",
        "brand-guidelines",
        "market-research",
        "strategy",
    ]
    desired_filenames = [
        "isletme-profili.md",
        "marka-kilavuzu.md",
        "pazar-arastirmasi.md",
        "strateji.md",
    ]

    for index, file_data in enumerate(memory_files):
        file_data["id"] = desired_ids[index] if index < len(desired_ids) else f"memory-{index + 1}"
        if index < len(desired_filenames) and not file_data.get("filename"):
            file_data["filename"] = desired_filenames[index]

    return memory_files


def join_or_none(values: list[str], *, separator: str = ", ") -> str:
    cleaned = [value for value in values if isinstance(value, str) and value.strip()]
    return separator.join(cleaned) if cleaned else "Yok"


def should_verify_ssl() -> bool:
    return os.getenv("HTTP_VERIFY_SSL", "true").lower() not in {"0", "false", "no"}
