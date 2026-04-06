from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .scrape import CrawlBundle, PageSnapshot

GEMINI_PROMPT_VERSION = "aylin-gemini-v4"
GEMINI_CHAT_PROMPT_VERSION = "aylin-chat-v1"


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
                "parts": [{"text": build_prompt(bundle, goals, connected_platforms)}],
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


async def generate_chat_reply_with_gemini(
    workspace_snapshot: dict[str, Any],
    recent_messages: list[dict[str, Any]],
    user_message: str,
) -> str | None:
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
                        "text": build_chat_prompt(
                            workspace_snapshot=workspace_snapshot,
                            recent_messages=recent_messages,
                            user_message=user_message,
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "text/plain",
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
    return text.strip() if text else None


def build_prompt(
    bundle: CrawlBundle,
    goals: list[str],
    connected_platforms: list[str],
) -> str:
    connected_text = ", ".join(connected_platforms) if connected_platforms else "Henüz bağlanmadı"
    focus_text = ", ".join(goals) if goals else "SEO, Sosyal Medya, İçerik, E-posta, Ücretli Reklamlar"
    note_text = " | ".join(bundle.notes[:10]) if bundle.notes else "Yok"
    email_text = join_or_none(bundle.contact_signals.emails[:8])
    phone_text = join_or_none(bundle.contact_signals.phones[:8])
    social_text = join_or_none(bundle.contact_signals.socials[:8])
    address_text = join_or_none(bundle.contact_signals.addresses[:5], separator=" | ")
    technologies_text = join_or_none(bundle.site_signals.technologies[:10])
    currencies_text = join_or_none(bundle.site_signals.currencies[:6])
    page_mix_text = join_or_none(bundle.site_signals.page_mix[:8], separator=" | ")
    cta_text = join_or_none(bundle.site_signals.cta_texts[:14], separator=" | ")
    entity_text = join_or_none(bundle.site_signals.entity_labels[:16], separator=" | ")
    pricing_text = join_or_none(bundle.site_signals.pricing_signals[:10], separator=" | ")
    faq_text = join_or_none(bundle.site_signals.faq_highlights[:8], separator=" | ")
    brand_assets_text = build_brand_assets_block(bundle)
    research_block = build_research_block(bundle)
    evidence_block = build_evidence_block(bundle)
    pages_block = "\n\n".join(build_page_block(page) for page in bundle.pages[:7])

    return f"""
Sen Aylin'sin. Türkçe konuşan, analitik ve ticari düşünmeyi bilen kıdemli bir dijital pazarlama stratejistisin.

Sana bir web sitesi için çok sayfalı tarama çıktısı, alan bazlı araştırma paketi ve kanıt blokları veriliyor.
Görevin yalnızca özet çıkarmak değil; işletmeyi, teklif mimarisini, hedef kitleyi ve büyüme fırsatlarını doğru çözmek.

Kurallar:
- Sadece verilen kanıtlara dayan.
- Kanıtı zayıf alanlarda kesin konuşma; gerektiğinde "site sinyallerine göre", "görünüşe göre", "muhtemelen" gibi temkinli ifade kullan.
- Yorum ile gözlemi karıştırma.
- Çıktının tamamı Türkçe olacak.
- Türkçeye çevrilebilir genel terimleri Türkçeleştir. Marka, ürün ve teknik özel isimleri koru.
- Kaynak sitedeki İngilizce sloganları veya başlıkları doğrudan kopyalama; gerekiyorsa doğal Türkçeyle yeniden ifade et.
- Hafıza dosyalarında bölüm başlıkları ve ara başlıklar Türkçe olacak. "Quick Wins" gibi İngilizce başlık kullanma.
- JSON dışında hiçbir şey yazma.

Site bilgileri:
- Website: {bundle.website}
- Alan adı: {bundle.domain}
- Odak alanları: {focus_text}
- Bağlı platformlar: {connected_text}
- Tarama notları: {note_text}

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
- Tekrarlayan varlıklar: {entity_text}
- Fiyat sinyalleri: {pricing_text}
- SSS sinyalleri: {faq_text}

Marka varlıkları:
{brand_assets_text}

Araştırma paketi:
{research_block}

Kanıt blokları:
{evidence_block}

İncelenen sayfalar:
{pages_block}

Görevler:
1. İşletmenin ne sattığını, nasıl sattığını ve teklif mimarisini net çöz.
2. Hedef kitleyi sadece genel tanımla bırakma; segment ve motivasyon cümlesi kur.
3. En güçlü farklılaştırıcı unsuru, varsa güven katmanını ve varsa net olmayan boşlukları belirle.
4. Tek bir ana büyüme fırsatı çıkar ve neden güçlü olduğunu düşünsel olarak açık ama kısa tut.
5. İlk 30 gün için uygulanabilir, kısa ve öncelik sıralı aksiyonlar üret.
6. Dört hafıza dosyasını gerçek çalışma dokümanı gibi doldur.

JSON şeması:
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
- `analysis.offer` tek cümlede net değer önerisi olmalı; genel tanım yapma.
- `analysis.audience` alıcı tipini ve satın alma motivasyonunu içermeli.
- `analysis.opportunity` tek, güçlü ve kanıtlanabilir büyüme fırsatını anlatmalı.
- `analysis.firstMonthPlan` kısa, uygulanabilir ve art arda yapılabilir üç aksiyon olmalı.
- Hafıza dosyalarında İngilizce başlık bırakma.
- İşletme Profili belgesi: iş modeli, teklif kümeleri, temas sinyalleri, fiyat sinyalleri ve kritik sayfalar.
- Marka Kılavuzu belgesi: ton, görsel yön, CTA dili, güven dili ve mesaj sütunları.
- Pazar Araştırması belgesi: rekabet çerçevesi, kategori boşlukları, SEO/içerik fırsatları ve riskler.
- 30 Günlük Strateji belgesi: kanal öncelikleri, haftalık mantık ve hızlı kazanımlar.
- Markdown fence kullanma.
""".strip()


def build_chat_prompt(
    *,
    workspace_snapshot: dict[str, Any],
    recent_messages: list[dict[str, Any]],
    user_message: str,
) -> str:
    analysis_result = workspace_snapshot.get("analysisResult", {}) if isinstance(workspace_snapshot, dict) else {}
    analysis = analysis_result.get("analysis", {}) if isinstance(analysis_result, dict) else {}
    strategic_summary = (
        analysis_result.get("strategicSummary", {}) if isinstance(analysis_result, dict) else {}
    )
    research_package = (
        analysis_result.get("researchPackage", {}) if isinstance(analysis_result, dict) else {}
    )
    contact_signals = (
        analysis_result.get("contactSignals", {}) if isinstance(analysis_result, dict) else {}
    )
    website = str(workspace_snapshot.get("website", "")).strip() if isinstance(workspace_snapshot, dict) else ""
    selected_goals = workspace_snapshot.get("selectedGoals", []) if isinstance(workspace_snapshot, dict) else []
    connected_platforms = (
        workspace_snapshot.get("connectedPlatforms", []) if isinstance(workspace_snapshot, dict) else []
    )

    return f"""
Sen Aylin'sin. Türkçe konuşan, net, stratejik ve güven veren bir dijital pazarlama danışmanısın.

Şu anda bir ilk analiz sonrası devam eden workspace sohbetindesin. Cevapların:
- Türkçe olacak
- kısa ama yüzeysel olmayacak
- mevcut araştırmaya dayanacak
- olmayan veriyi uydurmayacak
- mümkünse somut öneri verecek
- Kaynak sitedeki İngilizce sloganları aynen tekrar etmek yerine Türkçe anlamını açıkla
- Kullanıcı sadece selam veriyorsa analizi baştan tekrarlama; kısa karşıla ve tek bir net yön öner

Eğer kullanıcı daha derin veya kesin cevap istiyorsa ama veri yetersizse bunu açıkça söyle.
Eğer kullanıcı içerik, kampanya, teklif, kanal, hedef kitle veya büyüme önerisi soruyorsa mevcut analiz bağlamını kullan.
Gereksiz uzun intro yazma. Doğrudan yardımcı ol.

Workspace özeti:
- Website: {website or 'Yok'}
- Şirket: {safe_string(analysis.get('companyName')) or 'Yok'}
- Ana teklif: {safe_string(analysis.get('offer')) or 'Yok'}
- Hedef kitle: {safe_string(analysis.get('audience')) or 'Yok'}
- Ton: {safe_string(analysis.get('tone')) or 'Yok'}
- Ana fırsat: {safe_string(analysis.get('opportunity')) or safe_string(strategic_summary.get('primaryGrowthLever')) or 'Yok'}
- Odak alanları: {join_or_none(selected_goals if isinstance(selected_goals, list) else [])}
- Bağlı platformlar: {join_or_none(connected_platforms if isinstance(connected_platforms, list) else [])}
- Temas sinyalleri: e-posta={join_or_none(contact_signals.get('emails', []) if isinstance(contact_signals, dict) else [])}, telefon={join_or_none(contact_signals.get('phones', []) if isinstance(contact_signals, dict) else [])}

Araştırma sinyalleri:
{build_chat_research_block(research_package)}

Hafıza dosyaları:
{build_chat_memory_block(analysis_result.get('memoryFiles', []))}

Son mesaj geçmişi:
{build_chat_history_block(recent_messages)}

Kullanıcının yeni mesajı:
{user_message.strip()}

Şimdi yalnızca Aylin'in cevabını yaz. JSON yazma. Markdown kullanabilirsin ama kısa ve temiz tut.
""".strip()


def build_chat_research_block(research_package: Any) -> str:
    if not isinstance(research_package, dict):
        return "- Araştırma paketi yok"

    lines = [
        f"- Ana değer önerileri: {join_or_none(research_package.get('coreValueProps', []))}",
        f"- Destekleyici faydalar: {join_or_none(research_package.get('supportingBenefits', []))}",
        f"- Proof claim sinyalleri: {join_or_none(research_package.get('proofClaims', []))}",
        f"- Hedef kitle iddiaları: {join_or_none(research_package.get('audienceClaims', []))}",
        f"- CTA sinyalleri: {join_or_none(research_package.get('ctaClaims', []))}",
        f"- SEO sinyalleri: {join_or_none(research_package.get('seoSignals', []))}",
        f"- İçerik konuları: {join_or_none(research_package.get('contentTopics', []))}",
    ]
    return "\n".join(lines)


def build_chat_memory_block(memory_files: Any) -> str:
    if not isinstance(memory_files, list):
        return "- Hafıza dosyası yok"

    blocks: list[str] = []
    for item in memory_files[:4]:
        if not isinstance(item, dict):
            continue
        title = safe_string(item.get("title")) or safe_string(item.get("filename")) or "Dosya"
        content = safe_string(item.get("content"))
        excerpt = content[:900] if content else "İçerik yok"
        blocks.append(f"- {title}:\n{excerpt}")

    return "\n\n".join(blocks) if blocks else "- Hafıza dosyası yok"


def build_chat_history_block(recent_messages: list[dict[str, Any]]) -> str:
    relevant_messages: list[str] = []
    for message in recent_messages[-12:]:
        if not isinstance(message, dict):
            continue
        sender_type = safe_string(message.get("senderType"))
        message_type = safe_string(message.get("messageType"))
        content = safe_string(message.get("content"))

        if not content:
            continue
        if message_type == "process":
            continue
        if message_type == "memory_files":
            continue

        role = "Kullanıcı" if sender_type == "user" else "Aylin"
        relevant_messages.append(f"- {role}: {content}")

    return "\n".join(relevant_messages) if relevant_messages else "- Önceki sohbet mesajı yok"


def build_fallback_chat_reply(
    workspace_snapshot: dict[str, Any],
    user_message: str,
) -> str:
    analysis_result = workspace_snapshot.get("analysisResult", {}) if isinstance(workspace_snapshot, dict) else {}
    analysis = analysis_result.get("analysis", {}) if isinstance(analysis_result, dict) else {}
    strategic_summary = (
        analysis_result.get("strategicSummary", {}) if isinstance(analysis_result, dict) else {}
    )
    message_lower = user_message.lower()

    if any(keyword in message_lower for keyword in ("selam", "merhaba", "hey", "iyi", "nasılsın")):
        return (
            "Merhaba. İstersen buradan üç yönden birine hızlıca girebiliriz: ana teklif cümlesi, hedef kitle netliği ya da ilk 30 günlük pazarlama planı. "
            "Hangisinden başlayalım?"
        )

    if any(keyword in message_lower for keyword in ("seo", "arama", "anahtar kelime", "blog")):
        return (
            f"SEO tarafında en güçlü başlangıç noktası, {safe_string(strategic_summary.get('contentAngle')) or safe_string(analysis.get('opportunity')) or 'mevcut teklif etrafında konu kümeleri kurmak'} olur. "
            "İstersen bunu şimdi sana 3 içerik başlığı ve 1 landing page açısı olarak da çıkarabilirim."
        )

    if any(keyword in message_lower for keyword in ("reklam", "ads", "google", "meta", "kampanya")):
        return (
            f"Ücretli reklam tarafında önce tek bir ana teklif etrafında ilerlemek daha doğru olur. "
            f"Şu an en mantıklı giriş noktası: {safe_string(analysis.get('offer')) or 'ana değer önerisini sadeleştirmek'}. "
            "İstersen bunu reklam mesajı, hedef kitle ve teklif kırılımı olarak ayırabilirim."
        )

    if any(keyword in message_lower for keyword in ("hedef kitle", "kime", "müşteri", "audience")):
        return (
            f"Şu anki analize göre en olası hedef kitle çerçevesi şu: {safe_string(analysis.get('audience')) or safe_string(strategic_summary.get('bestFitAudience')) or 'hedef kitle sinyali sınırlı'}. "
            "Bunu istersek karar verici, ihtiyaç ve satın alma motivasyonu şeklinde daha net parçalayabilirim."
        )

    return (
        f"Elimdeki ilk analize göre en önemli odak şu görünüyor: {safe_string(analysis.get('opportunity')) or safe_string(strategic_summary.get('primaryGrowthLever')) or 'ana teklifi daha net ve güçlü hale getirmek'}. "
        "İstersen bunu şimdi SEO, içerik, sosyal medya, e-posta ya da reklam tarafından birine indirip somut aksiyonlara çevireyim."
    )


def build_brand_assets_block(bundle: CrawlBundle) -> str:
    assets = bundle.site_signals.brand_assets
    candidate_lines = []
    for candidate in assets.candidates[:6]:
        if isinstance(candidate, str):
            candidate_lines.append(candidate)
            continue

        candidate_lines.append(
            "{kind}: {url} (puan={score:.2f}, kaynak={source})".format(
                kind=getattr(candidate, "kind", "asset"),
                url=getattr(candidate, "url", "Yok"),
                score=float(getattr(candidate, "score", 0.0) or 0.0),
                source=getattr(candidate, "source", "bilinmiyor"),
            )
        )

    return "\n".join(
        [
            f"- Ana logo: {assets.brand_logo or 'Yok'}",
            f"- Favicon: {assets.favicon or 'Yok'}",
            f"- Touch icon: {assets.touch_icon or 'Yok'}",
            f"- Sosyal görsel: {assets.social_image or 'Yok'}",
            f"- Manifest: {assets.manifest_url or 'Yok'}",
            f"- Mask icon: {assets.mask_icon or 'Yok'}",
            f"- Tile image: {assets.tile_image or 'Yok'}",
            f"- Adaylar: {join_or_none(candidate_lines, separator=' | ')}",
        ]
    )


def build_research_block(bundle: CrawlBundle) -> str:
    research = bundle.research_package
    return "\n".join(
        [
            f"- Marka adı adayları: {join_or_none(research.company_name_candidates, separator=' | ')}",
            f"- Hero mesajları: {join_or_none(research.hero_messages, separator=' | ')}",
            f"- Semantik bölgeler / hero: {join_or_none(research.semantic_zones.get('hero', []), separator=' | ')}",
            f"- Semantik bölgeler / teklifler: {join_or_none(research.semantic_zones.get('offers', []), separator=' | ')}",
            f"- Semantik bölgeler / proof: {join_or_none(research.semantic_zones.get('proof', []), separator=' | ')}",
            f"- Semantik bölgeler / pricing: {join_or_none(research.semantic_zones.get('pricing', []), separator=' | ')}",
            f"- Konumlandırma sinyalleri: {join_or_none(research.positioning_signals, separator=' | ')}",
            f"- Ana değer önerileri: {join_or_none(research.core_value_props, separator=' | ')}",
            f"- Destekleyici faydalar: {join_or_none(research.supporting_benefits, separator=' | ')}",
            f"- Teklif sinyalleri: {join_or_none(research.offer_signals, separator=' | ')}",
            f"- Hizmet teklifleri: {join_or_none(research.service_offers, separator=' | ')}",
            f"- Ürün teklifleri: {join_or_none(research.product_offers, separator=' | ')}",
            f"- Hedef kitle sinyalleri: {join_or_none(research.audience_signals, separator=' | ')}",
            f"- Hedef kitle iddiaları: {join_or_none(research.audience_claims, separator=' | ')}",
            f"- Güven sinyalleri: {join_or_none(research.trust_signals, separator=' | ')}",
            f"- Proof claim sinyalleri: {join_or_none(research.proof_claims, separator=' | ')}",
            f"- Dönüşüm aksiyonları: {join_or_none(research.conversion_actions, separator=' | ')}",
            f"- CTA claim sinyalleri: {join_or_none(research.cta_claims, separator=' | ')}",
            f"- İçerik konuları: {join_or_none(research.content_topics, separator=' | ')}",
            f"- SEO sinyalleri: {join_or_none(research.seo_signals, separator=' | ')}",
            f"- Coğrafya sinyalleri: {join_or_none(research.geography_signals, separator=' | ')}",
            f"- Dil sinyalleri: {join_or_none(research.language_signals, separator=' | ')}",
            f"- Pazar sinyalleri: {join_or_none(research.market_signals, separator=' | ')}",
            f"- Görsel sinyaller: {join_or_none(research.visual_signals, separator=' | ')}",
        ]
    )


def build_evidence_block(bundle: CrawlBundle) -> str:
    blocks = bundle.research_package.evidence_blocks[:10]
    if not blocks:
        return "- Kanıt bloğu yok"

    lines: list[str] = []
    for block in blocks:
        evidence_urls = join_or_none(block.get("evidenceUrls", [])[:4], separator=" | ")
        lines.append(
            "- Tür: {type} | İddia: {claim} | Neden: {why} | Güven: {confidence} | URL'ler: {urls}".format(
                type=block.get("type", "bilinmiyor"),
                claim=block.get("claim", "Yok"),
                why=block.get("why", "Yok"),
                confidence=block.get("confidence", 0),
                urls=evidence_urls,
            )
        )
    return "\n".join(lines)


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
    zones_text = " | ".join(
        f"{zone}: {join_or_none(values[:4], separator=' / ')}"
        for zone, values in page.zones.items()
        if values
    ) or "Yok"

    return f"""URL: {page.url}
Sayfa tipi: {page.page_type}
Fetch modu: {page.fetch_mode}
HTTP durum: {page.status_code}
Başlık: {page.title or 'Yok'}
Açıklama: {page.description or 'Yok'}
Meta: {meta_text}
Başlık hiyerarşisi: {join_or_none(page.headings[:8], separator=' | ')}
Navigasyon: {join_or_none(page.nav_labels[:10], separator=' | ')}
Hero mesajları: {join_or_none(page.hero_messages[:4], separator=' | ')}
Semantik bölgeler: {zones_text}
CTA'lar: {join_or_none(page.cta_texts[:8], separator=' | ')}
Değer önerileri: {join_or_none(page.value_props[:8], separator=' | ')}
Hedef kitle sinyalleri: {join_or_none(page.audience_signals[:4], separator=' | ')}
Güven sinyalleri: {join_or_none(page.trust_signals[:4], separator=' | ')}
Proof point sinyalleri: {join_or_none(page.proof_points[:4], separator=' | ')}
Fiyat sinyalleri: {join_or_none(page.pricing_signals[:6], separator=' | ')}
Tekrarlayan varlıklar: {join_or_none(page.entity_labels[:10], separator=' | ')}
Formlar: {forms_text}
SSS: {faq_text}
Teknolojiler: {join_or_none(page.technologies[:6])}
Görsel alt metinleri: {join_or_none(page.image_alts[:6], separator=' | ')}
Structured data: {join_or_none(page.structured_data[:4], separator=' || ')}
Ana içerik özeti:
{(page.main_content or page.excerpt)[:1800]}"""


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


def safe_string(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def should_verify_ssl() -> bool:
    return os.getenv("HTTP_VERIFY_SSL", "true").lower() not in {"0", "false", "no"}
