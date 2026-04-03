from __future__ import annotations

from typing import Any

from .scrape import CrawlBundle, ResearchPackage


def build_strategic_summary(
    bundle: CrawlBundle,
    analysis_payload: dict[str, Any] | None,
    goals: list[str],
) -> dict[str, Any]:
    analysis = analysis_payload.get("analysis", {}) if isinstance(analysis_payload, dict) else {}
    research = bundle.research_package
    active_goals = goals or ["SEO", "Sosyal Medya", "İçerik"]

    positioning = first_non_empty(
        [
            *research.positioning_signals,
            analysis.get("offer"),
            bundle.primary_page.description,
        ]
    )
    differentiation = infer_differentiation(research, analysis)
    best_fit_audience = first_non_empty(
        [
            analysis.get("audience"),
            "; ".join(research.audience_signals[:4]) if research.audience_signals else "",
        ]
    )
    primary_growth_lever = first_non_empty(
        [
            analysis.get("opportunity"),
            infer_primary_growth_lever(research, active_goals),
        ]
    )
    conversion_gap = infer_conversion_gap(research, bundle)
    content_angle = infer_content_angle(research, active_goals)

    return {
        "positioning": positioning,
        "differentiation": differentiation,
        "bestFitAudience": best_fit_audience,
        "primaryGrowthLever": primary_growth_lever,
        "conversionGap": conversion_gap,
        "contentAngle": content_angle,
    }


def build_quality_review(
    bundle: CrawlBundle,
    analysis_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    analysis = analysis_payload.get("analysis", {}) if isinstance(analysis_payload, dict) else {}
    research = bundle.research_package
    memory_files = analysis_payload.get("memoryFiles", []) if isinstance(analysis_payload, dict) else []

    checks = [
        evaluate_check(
            "offer_clarity",
            "Teklif netliği",
            bool(as_text(analysis.get("offer"))) and bool(research.hero_messages or research.offer_signals),
            "Ana değer teklifi çıkarılabildi." if as_text(analysis.get("offer")) else "Teklif hâlâ yüzeysel.",
        ),
        evaluate_check(
            "audience_specificity",
            "Hedef kitle belirginliği",
            bool(research.audience_signals) or word_count(as_text(analysis.get("audience"))) >= 8,
            "Hedef kitle için somut sinyaller var."
            if research.audience_signals
            else "Hedef kitle cümleleri daha belirgin olmalı.",
        ),
        evaluate_check(
            "positioning",
            "Konumlandırma içgörüsü",
            bool(research.positioning_signals),
            "Positioning sinyalleri bulundu." if research.positioning_signals else "Konumlandırma sinyali zayıf.",
        ),
        evaluate_check(
            "trust_layer",
            "Güven katmanı",
            bool(research.trust_signals or research.proof_points),
            "Güven / proof sinyalleri bulundu."
            if research.trust_signals or research.proof_points
            else "Güven katmanı zayıf.",
        ),
        evaluate_check(
            "seo_surface",
            "SEO / içerik yüzeyi",
            bool(research.content_topics) and bool(research.seo_signals),
            "İçerik ve SEO sinyalleri yeterli."
            if research.content_topics and research.seo_signals
            else "İçerik yüzeyi zayıf.",
        ),
        evaluate_check(
            "memory_docs",
            "Hafıza dosyaları",
            len(memory_files) >= 4,
            f"{len(memory_files)} hafıza dosyası üretildi." if len(memory_files) >= 4 else "Dosya sayısı eksik.",
        ),
    ]

    passed_count = sum(1 for item in checks if item["passed"])
    score = int(round((passed_count / len(checks)) * 100))
    strengths = build_strengths(research, analysis)
    risks = build_risks(research, bundle)
    verdict = (
        "İlk analiz güçlü; stratejik karar vermek için iyi bir temel var."
        if score >= 80
        else "İlk analiz kullanılabilir; ama birkaç kritik boşluk var."
        if score >= 60
        else "İlk analiz yeniden derinleştirilmeli; hâlâ önemli boşluklar var."
    )

    return {
        "score": score,
        "verdict": verdict,
        "strengths": strengths[:4],
        "risks": risks[:4],
        "checks": checks,
    }


def infer_differentiation(research: ResearchPackage, analysis: dict[str, Any]) -> str:
    if research.service_offers and research.product_offers:
        return "Hizmet + ürün katmanını birlikte taşıması, markayı tek kanallı rakiplerden ayırabilir."
    if research.proof_points:
        return f"Markanın kanıt katmanında öne çıkan sinyal: {research.proof_points[0]}"
    if as_text(analysis.get("pricePosition")):
        return f"Fiyat konumu açısından öne çıkan çerçeve: {analysis['pricePosition']}"
    return "Ayrıştırıcı unsur henüz tamamen net değil; ama teklif dili güçlendirildiğinde belirginleşebilir."


def infer_primary_growth_lever(research: ResearchPackage, goals: list[str]) -> str:
    if research.seo_signals and research.content_topics:
        return (
            f"En güçlü kaldıraç, {goals[0]} odağında "
            f"{research.content_topics[0]} etrafında içerik ve landing page otoritesi kurmak."
        )
    if research.conversion_actions:
        return f"En hızlı kaldıraç, dönüşüm akışını {research.conversion_actions[0].lower()} etrafında sadeleştirmek."
    return "En hızlı kaldıraç, ana teklifi tek bir güçlü dönüşüm yoluna bağlamak."


def infer_conversion_gap(research: ResearchPackage, bundle: CrawlBundle) -> str:
    if not bundle.contact_signals.emails and not bundle.contact_signals.phones and not any(page.forms for page in bundle.pages):
        return "Doğrudan talep toplama yolu zayıf; temas noktaları daha görünür kurulmalı."
    if research.trust_signals:
        return "Dönüşümün ana boşluğu, güven sinyallerinin CTA çevresinde yeterince görünür olmaması olabilir."
    if bundle.site_signals.pricing_signals:
        return "Fiyat sinyali var; ama teklif bağlamı daha net anlatılmazsa ziyaretçi kararsız kalabilir."
    return "Ana boşluk, teklifin ikna sırası ve CTA etrafındaki netlikte görünüyor."


def infer_content_angle(research: ResearchPackage, goals: list[str]) -> str:
    if research.content_topics:
        return (
            f"{goals[0]} için en güçlü içerik açısı, "
            f"{', '.join(research.content_topics[:3])} etrafında problem-çözüm anlatısı kurmak."
        )
    if research.audience_signals:
        return f"İçerikte en iyi açı, {research.audience_signals[0]} sinyalini ticari faydaya çevirmek."
    return "İçerikte en iyi açı, teklif netliğini ve güven kanıtlarını birlikte taşımak."


def build_strengths(research: ResearchPackage, analysis: dict[str, Any]) -> list[str]:
    strengths: list[str] = []
    if research.positioning_signals:
        strengths.append("Markanın konumlandırma sinyali belirgin.")
    if research.trust_signals or research.proof_points:
        strengths.append("Güven ve proof katmanı için kullanılabilir sinyaller var.")
    if research.content_topics:
        strengths.append("İçerik kümeleri üretmek için yeterli konu yüzeyi bulunuyor.")
    if as_text(analysis.get("opportunity")):
        strengths.append("Büyüme fırsatı net bir cümleye indirgenebildi.")
    return strengths


def build_risks(research: ResearchPackage, bundle: CrawlBundle) -> list[str]:
    risks: list[str] = []
    if not research.trust_signals and not research.proof_points:
        risks.append("Güven ve sosyal kanıt sinyali zayıf.")
    if "Blog/insight sayfası görünmüyor." in research.seo_signals:
        risks.append("İçerik yüzeyi sınırlı; SEO otoritesi yavaş kurulabilir.")
    if not bundle.site_signals.pricing_signals:
        risks.append("Fiyat veya paket çerçevesi belirsiz görünüyor.")
    if not bundle.contact_signals.emails and not bundle.contact_signals.phones and not any(page.forms for page in bundle.pages):
        risks.append("Talep toplama yüzeyi zayıf.")
    return risks


def evaluate_check(check_id: str, label: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "label": label,
        "passed": passed,
        "detail": detail,
    }


def first_non_empty(values: list[Any]) -> str:
    for value in values:
        text = as_text(value)
        if text:
            return text
    return ""


def as_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def word_count(value: str) -> int:
    return len([part for part in value.split() if part.strip()])
