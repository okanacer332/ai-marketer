from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


PHRASE_REPLACEMENTS = {
    "Company Overview": "Genel Bakış",
    "What They Do": "Ne Yapıyor",
    "Core Product": "Ana Ürün",
    "Business Model": "İş Modeli",
    "Target Audience": "Hedef Kitle",
    "Target Segments": "Hedef Segmentler",
    "Brand Personality": "Marka Kişiliği",
    "Visual Identity": "Görsel Kimlik",
    "Color Palette": "Renk Paleti",
    "Typography": "Tipografi",
    "UI Components": "Arayüz Bileşenleri",
    "UI Style": "Arayüz Dili",
    "Voice & Messaging": "Ses Tonu ve Mesajlaşma",
    "Key Messaging Pillars": "Temel Mesaj Sütunları",
    "Services": "Hizmetler",
    "Products": "Ürünler",
    "Pricing": "Fiyatlandırma",
    "Website": "Web Sitesi",
    "Market Context": "Pazar Bağlamı",
    "Competitive Landscape": "Rekabet Görünümü",
    "Keyword Opportunities": "Anahtar Kelime Fırsatları",
    "Market Opportunity": "Pazar Fırsatı",
    "North Star Goal": "Ana Hedef",
    "Quick Wins": "Hızlı Kazanımlar",
    "Strategy": "Strateji",
    "Content Writing": "İçerik Yazarlığı",
    "Social Media": "Sosyal Medya",
    "Email Marketing": "E-posta Pazarlaması",
    "Paid Ads": "Ücretli Reklamlar",
    "Funnel Strategy": "Huni Stratejisi",
    "Primary CTA": "Birincil CTA",
    "Secondary CTA": "İkincil CTA",
    "Tone": "Ton",
    "Energy": "Enerji",
    "Voice": "Ses",
    "File": "Dosya",
    "Saved": "Kaydedildi",
    "Proof Layer": "Kanıt Katmanı",
    "Positioning": "Konumlandırma",
    "Positioning summary": "Konumlandırma özeti",
    "Website": "Web sitesi",
}

TEXT_REPLACEMENTS = {
    "3-day free trial": "3 günlük ücretsiz deneme",
    "Works while you sleep.": "Siz uyurken çalışır.",
    "No credit card": "Kredi kartı gerektirmez",
    "Free report": "Ücretsiz rapor",
    "Growth lever": "Büyüme kaldıracı",
    "Landing page": "Açılış sayfası",
    "Case study": "Vaka çalışması",
    "Thought leadership": "Uzmanlık içeriği",
    "Quick Wins": "Hızlı Kazanımlar",
    "Get a Quote": "Teklif Al",
    "Start Your Project": "Projeni Başlat",
    "Real projects, measurable impact.": "Gerçek projeler, ölçülebilir etki.",
    "A selection of software we've built for clients worldwide.": "Dünya genelindeki müşteriler için geliştirdiğimiz projelerden seçkiler.",
    "Smart technology, measurable results.": "Akıllı teknoloji, ölçülebilir sonuçlar.",
    "We bring your business into the future with web, mobile and desktop software solutions.": "İşletmenizi web, mobil ve masaüstü yazılım çözümleriyle geleceğe taşıyoruz.",
    "We accelerate your business's digital transformation with modern technologies and proven methods.": "İşletmenizin dijital dönüşümünü modern teknolojiler ve doğrulanmış yöntemlerle hızlandırıyoruz.",
    "Fast, scalable and SEO-friendly web apps built with React, Next.js and modern web technologies.": "React, Next.js ve modern web teknolojileriyle hızlı, ölçeklenebilir ve SEO uyumlu web uygulamaları geliştiriyoruz.",
    "Cross-platform mobile apps for iOS and Android with React Native. One codebase, two platforms.": "React Native ile iOS ve Android için çapraz platform mobil uygulamalar geliştiriyoruz. Tek kod tabanı, iki platform.",
    "AI integrations, machine learning models and business process automation to boost productivity.": "Verimliliği artırmak için yapay zeka entegrasyonları, makine öğrenmesi modelleri ve iş süreçleri otomasyonu sunuyor.",
    "Let's Scale Your Business": "İşinizi birlikte büyütelim",
    "Web Applications": "Web Uygulamaları",
    "Mobile Apps": "Mobil Uygulamalar",
    "Desktop Software": "Masaüstü Yazılımlar",
    "AI & Automation": "Yapay Zeka ve Otomasyon",
    "Future-Proof Software": "Geleceğe Hazır Yazılım",
    "Projects": "Projeler",
    "Contact": "İletişim",
    "Built with the Industry's Most": "Sektörün En Gelişmiş Araçlarıyla",
    "IT outsourcing": "BT outsourcing",
}

MEMORY_TITLE_BY_FILENAME = {
    "isletme-profili.md": "İşletme Profili",
    "marka-kilavuzu.md": "Marka Kılavuzu",
    "pazar-arastirmasi.md": "Pazar Araştırması",
    "strateji.md": "30 Günlük Strateji",
    "business-profile.md": "İşletme Profili",
    "brand-guidelines.md": "Marka Kılavuzu",
    "market-research.md": "Pazar Araştırması",
    "strategy.md": "30 Günlük Strateji",
}


def normalize_analysis_payload_language(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(payload)
    analysis = normalized.get("analysis")
    if isinstance(analysis, dict):
        for key in ("sector", "offer", "audience", "tone", "pricePosition", "opportunity"):
            if isinstance(analysis.get(key), str):
                analysis[key] = normalize_text_output(analysis[key])
        if isinstance(analysis.get("firstMonthPlan"), list):
            analysis["firstMonthPlan"] = [
                normalize_text_output(str(item))
                for item in analysis["firstMonthPlan"]
                if str(item).strip()
            ]
        if isinstance(analysis.get("competitors"), list):
            analysis["competitors"] = [
                normalize_text_output(str(item))
                for item in analysis["competitors"]
                if str(item).strip()
            ]

    strategic_summary = normalized.get("strategicSummary")
    if isinstance(strategic_summary, dict):
        for key, value in strategic_summary.items():
            if isinstance(value, str):
                strategic_summary[key] = normalize_text_output(value)

    quality_review = normalized.get("qualityReview")
    if isinstance(quality_review, dict):
        if isinstance(quality_review.get("verdict"), str):
            quality_review["verdict"] = normalize_text_output(quality_review["verdict"])
        if isinstance(quality_review.get("strengths"), list):
            quality_review["strengths"] = [
                normalize_text_output(str(item))
                for item in quality_review["strengths"]
                if str(item).strip()
            ]
        if isinstance(quality_review.get("risks"), list):
            quality_review["risks"] = [
                normalize_text_output(str(item))
                for item in quality_review["risks"]
                if str(item).strip()
            ]
        if isinstance(quality_review.get("checks"), list):
            for item in quality_review["checks"]:
                if not isinstance(item, dict):
                    continue
                for key in ("label", "detail"):
                    if isinstance(item.get(key), str):
                        item[key] = normalize_text_output(item[key])

    memory_files = normalized.get("memoryFiles")
    if isinstance(memory_files, list):
        for item in memory_files:
            if not isinstance(item, dict):
                continue
            filename = str(item.get("filename", "")).strip()
            if filename in MEMORY_TITLE_BY_FILENAME:
                item["title"] = MEMORY_TITLE_BY_FILENAME[filename]
            if isinstance(item.get("blurb"), str):
                item["blurb"] = normalize_text_output(item["blurb"])
            if isinstance(item.get("content"), str):
                item["content"] = normalize_markdown_output(item["content"])

    return normalized


def normalize_markdown_output(content: str) -> str:
    normalized = normalize_text_output(content)
    normalized = normalized.replace("## Proof Layer", "## Kanıt Katmanı")
    normalized = normalized.replace("## Positioning", "## Konumlandırma")
    normalized = normalized.replace("## Quick Wins", "## Hızlı Kazanımlar")
    normalized = normalized.replace("Positioning özeti", "Konumlandırma özeti")
    return normalized


def normalize_text_output(value: str) -> str:
    normalized = value
    for source, target in PHRASE_REPLACEMENTS.items():
        normalized = normalized.replace(source, target)
    for source, target in TEXT_REPLACEMENTS.items():
        normalized = normalized.replace(source, target)
    normalized = re.sub(r"\bWebsite\b", "Web sitesi", normalized)
    normalized = re.sub(r"\bPositioning\b", "Konumlandırma", normalized)
    normalized = re.sub(r"\bProof point\b", "Kanıt", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s{2,}", " ", normalized)
    return normalized
