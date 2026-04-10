import { useEffect, useRef, useState, type CSSProperties } from 'react'
import {
  IconArrowsExchange2,
  IconBulb,
  IconChartBar,
  IconChecks,
  IconFileText,
  IconMail,
  IconMessage2,
  IconRocket,
  IconSearch,
  IconShieldCheck,
  IconSparkles,
  IconTargetArrow,
  IconUsers,
  IconWorld,
} from '@tabler/icons-react'

import './RevolutLanding.css'
import {
  howWeWorkSteps,
  impactMetrics,
  revolutHeroAssets,
  revolutHomepageNav,
  revolutScrollCards,
  solutionItems,
  whyUsItems,
  workflowCapabilities,
} from './revolutHomepageContent'

type RevolutLandingProps = {
  onStart: () => void
  onLogin: () => void
}

type TopbarVariant = 'light' | 'dark'

const iconMap = {
  bulb: IconBulb,
  chart: IconChartBar,
  checks: IconChecks,
  file: IconFileText,
  mail: IconMail,
  message: IconMessage2,
  rocket: IconRocket,
  search: IconSearch,
  sparkles: IconSparkles,
  target: IconTargetArrow,
  users: IconUsers,
  world: IconWorld,
} as const

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function easeInOutCubic(value: number) {
  return value < 0.5 ? 4 * value * value * value : 1 - Math.pow(-2 * value + 2, 3) / 2
}

function useHeroScrollProgress() {
  const [progress, setProgress] = useState(0)
  const targetRef = useRef(0)
  const currentRef = useRef(0)

  useEffect(() => {
    let frame = 0
    let active = true

    const updateTarget = () => {
      const viewport = typeof window !== 'undefined' ? window.innerHeight : 1
      targetRef.current = clamp(window.scrollY / Math.max(viewport * 2.2, 1), 0, 1)
    }

    const animate = () => {
      if (!active) {
        return
      }

      const delta = targetRef.current - currentRef.current
      currentRef.current += delta * 0.055

      if (Math.abs(delta) < 0.0015) {
        currentRef.current = targetRef.current
      }

      setProgress((current) =>
        Math.abs(current - currentRef.current) > 0.001 ? currentRef.current : current,
      )

      frame = requestAnimationFrame(animate)
    }

    updateTarget()
    frame = requestAnimationFrame(animate)
    window.addEventListener('scroll', updateTarget, { passive: true })
    window.addEventListener('resize', updateTarget)

    return () => {
      active = false
      cancelAnimationFrame(frame)
      window.removeEventListener('scroll', updateTarget)
      window.removeEventListener('resize', updateTarget)
    }
  }, [])

  return easeInOutCubic(progress)
}

function RevolutTopbar({
  onLogin,
  onStart,
  variant,
}: RevolutLandingProps & {
  variant: TopbarVariant
}) {
  return (
    <header className={`revolut-home-topbar revolut-home-topbar-${variant}`}>
      <button type="button" className="revolut-home-logo">
        Olric.
      </button>

      <nav className="revolut-home-nav" aria-label="Ana gezinme">
        {revolutHomepageNav.map((item) => (
          <button key={item} type="button" className="revolut-home-nav-link">
            {item}
          </button>
        ))}
      </nav>

      <div className="revolut-home-topbar-actions">
        <button type="button" className="revolut-home-login" onClick={onLogin}>
          Giriş yap
        </button>
        <button type="button" className="revolut-home-signup" onClick={onStart}>
          Olric ile başlayın
        </button>
      </div>
    </header>
  )
}

function ScrollCard({
  caption,
  eyebrow,
  figure,
  label,
  tone,
}: (typeof revolutScrollCards)[number]) {
  return (
    <article className={`revolut-scroll-card revolut-scroll-card-${tone}`}>
      <img src={revolutHeroAssets.portrait} alt="Olric" className="revolut-scroll-card-image" />

      <div className="revolut-scroll-card-overlay">
        <span>{eyebrow}</span>
        <strong>{figure}</strong>
        <button type="button">{label}</button>
      </div>

      <div className="revolut-scroll-card-footer">
        <p>{caption}</p>
      </div>
    </article>
  )
}

function HeroScene({ onStart }: Pick<RevolutLandingProps, 'onStart'>) {
  return (
    <section className="revolut-hero-scene" aria-label="Hero">
      <div className="revolut-hero-copy">
        <h1>Pazarlama &amp; Ötesi</h1>
        <p>
          Markanızı anlayan, konumunuzu netleştiren ve ilk günden itibaren sonuç odaklı bir
          pazarlama sistemi kuran otonom çalışma katmanı.
        </p>
        <button type="button" className="revolut-home-download" onClick={onStart}>
          Olric ile başlayın
        </button>
      </div>

      <div className="revolut-hero-visual">
        <div className="revolut-hero-frame" aria-hidden="true" />

        <img
          src={revolutHeroAssets.heroPortrait}
          alt="Olric"
          className="revolut-hero-portrait"
        />

        <div className="revolut-hero-insight">
          <strong>24/7</strong>
          <button type="button">Çalışıyor</button>
        </div>

        <div className="revolut-hero-safety-card">
          <div className="revolut-hero-badge revolut-hero-badge-left">
            <span className="revolut-hero-badge-icon-shell" aria-hidden="true">
              <IconShieldCheck stroke={2.2} />
            </span>
            <span className="revolut-hero-badge-text">PROTECTED</span>
          </div>
          <div className="revolut-hero-badge revolut-hero-badge-right">
            <span className="revolut-hero-badge-kicker">CURRENT ACCOUNT</span>
            <span className="revolut-hero-badge-stack">
              <IconArrowsExchange2 stroke={2.2} />
              <span>SWITCH GUARANTEE</span>
            </span>
          </div>
        </div>
      </div>
    </section>
  )
}

function SalaryScene({ onStart }: Pick<RevolutLandingProps, 'onStart'>) {
  return (
    <section className="revolut-salary-scene" aria-label="İkinci sahne">
      <div className="revolut-salary-copy">
        <h2>Pazarlamanız, yeniden kuruldu</h2>
        <p>
          Olric web sitenizi okur, ilk çıktıları hazırlar, öncelikleri sıralar ve onayınıza göre
          düzenli bir çalışma akışı kurar.
        </p>
        <button type="button" className="revolut-salary-button" onClick={onStart}>
          İlk analizi başlat
        </button>
      </div>

      <div className="revolut-salary-cards" aria-label="Örnek Olric kartları">
        {revolutScrollCards.map((card) => (
          <ScrollCard key={card.eyebrow} {...card} />
        ))}
      </div>
    </section>
  )
}

function HowWeWorkSection() {
  return (
    <section className="revolut-how-section revolut-content-shell" aria-labelledby="how-we-work">
      <div className="revolut-section-heading">
        <p className="revolut-section-kicker">Nasıl çalışır</p>
        <h2 id="how-we-work">Önce markayı çözer, sonra büyüme sistemini kurar.</h2>
        <p className="revolut-section-summary">
          Olric ilk olarak markayı, teklif yapısını ve hedef kitleyi netleştirir. Ardından içerik,
          SEO ve kampanya akışını sizin önceliklerinize göre düzenler.
        </p>
      </div>

      <div className="revolut-how-grid">
        {howWeWorkSteps.map((item) => {
          const IconComponent = iconMap[item.icon]

          return (
            <article key={item.step} className="revolut-how-card">
              <div className="revolut-how-card-topline">
                <span className="revolut-how-step">{item.step}</span>
                <span className="revolut-how-icon" aria-hidden="true">
                  <IconComponent stroke={1.9} />
                </span>
              </div>
              <h3>{item.title}</h3>
              <p>{item.description}</p>
            </article>
          )
        })}
      </div>
    </section>
  )
}

function WorkflowSection() {
  return (
    <section
      className="revolut-workflow-section revolut-content-shell"
      aria-labelledby="workflow-capabilities"
    >
      <div className="revolut-section-heading revolut-section-heading-compact">
        <p className="revolut-section-kicker">Yetenekler</p>
        <h2 id="workflow-capabilities">İnsan uzmanlığından türetilmiş 50+ pazarlama akışı</h2>
        <p className="revolut-workflow-subtitle">Tekrarlayan işi hızlandırmak için hazırlandı</p>
        <p className="revolut-section-summary">
          Araştırma, içerik, SEO, reklam ve raporlama gibi tekrar eden pazarlama işlerini daha
          hızlı ve daha tutarlı bir düzene oturtur.
        </p>
      </div>

      <div className="revolut-workflow-grid">
        {workflowCapabilities.map((item) => {
          const IconComponent = iconMap[item.icon]

          return (
            <article key={item.label} className="revolut-workflow-card">
              <span className="revolut-workflow-icon" aria-hidden="true">
                <IconComponent stroke={1.9} />
              </span>
              <span>{item.label}</span>
            </article>
          )
        })}
      </div>
    </section>
  )
}

function WhyUsSection() {
  return (
    <section className="revolut-why-section revolut-content-shell" aria-labelledby="why-us">
      <div className="revolut-section-heading revolut-section-heading-wide">
        <p className="revolut-section-kicker">Neden Olric?</p>
        <h2 id="why-us">
          Yeni pazarlama ekibinizle tanışın.
          <br />
          <span className="revolut-highlight revolut-highlight-lavender">Hazır olduğunuz anda başlar.</span>{' '}
          <span className="revolut-highlight revolut-highlight-sky">Siz dinlenirken ilerler.</span>
        </h2>
        <p className="revolut-section-summary">
          İhtiyacınız olan uzmanlığı seçersiniz. Olric araştırmadan raporlamaya kadar işi taşır;
          siz ise büyüme yönünü kontrol edersiniz.
        </p>
      </div>

      <div className="revolut-why-grid">
        {whyUsItems.map((item) => {
          const IconComponent = iconMap[item.icon]

          return (
            <article key={item.title} className={`revolut-why-card revolut-why-card-${item.tone}`}>
              <span className="revolut-why-icon" aria-hidden="true">
                <IconComponent stroke={1.9} />
              </span>
              <h3>{item.title}</h3>
              <p>{item.description}</p>
            </article>
          )
        })}
      </div>
    </section>
  )
}

function SolutionsSection() {
  return (
    <section className="revolut-solutions-section revolut-content-shell" aria-labelledby="solutions">
      <div className="revolut-section-heading revolut-section-heading-wide revolut-section-heading-center">
        <p className="revolut-section-kicker revolut-section-kicker-green">Kullanım alanları</p>
        <h2 id="solutions">
          Startup’lardan kurumsal ekiplere,
          <br />
          <span className="revolut-highlight revolut-highlight-sky">her ölçekte</span> uyum sağlar
        </h2>
        <p className="revolut-section-summary">
          Basit başlangıç, doğrudan entegrasyon ve esnek akışlarla birlikte Olric, operasyon
          büyüdükçe sizinle aynı hızda ölçeklenir.
        </p>
      </div>

      <div className="revolut-solutions-grid">
        {solutionItems.map((item) => {
          const IconComponent = iconMap[item.icon]

          return (
            <article
              key={item.title}
              className={`revolut-solution-card revolut-solution-card-${item.tone}`}
            >
              <span className="revolut-solution-icon" aria-hidden="true">
                <IconComponent stroke={1.9} />
              </span>
              <div className="revolut-solution-copy">
                <h3>{item.title}</h3>
                <p>{item.description}</p>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}

function MetricsSection() {
  return (
    <section className="revolut-metrics-section revolut-content-shell" aria-label="Etki metrikleri">
      <div className="revolut-metrics-grid">
        {impactMetrics.map((item) => (
          <article key={item.value} className={`revolut-metric-card revolut-metric-card-${item.tone}`}>
            <strong>{item.value}</strong>
            <p>{item.label}</p>
            <span>{item.sublabel}</span>
          </article>
        ))}
      </div>
    </section>
  )
}

export function RevolutLanding({ onLogin, onStart }: RevolutLandingProps) {
  const progress = useHeroScrollProgress()
  const heroOpacity = 1 - clamp(progress * 1.08, 0, 1)
  const salaryOpacity = clamp((progress - 0.24) / 0.54, 0, 1)
  const wipeOpacity = clamp((progress - 0.1) / 0.36, 0, 1)
  const fullWhiteOpacity = clamp((progress - 0.58) / 0.2, 0, 1)

  const stageStyle = {
    '--landing-progress': progress.toString(),
    '--landing-hero-opacity': heroOpacity.toString(),
    '--landing-salary-opacity': salaryOpacity.toString(),
    '--landing-wipe-opacity': wipeOpacity.toString(),
    '--landing-full-white-opacity': fullWhiteOpacity.toString(),
  } as CSSProperties

  return (
    <section className="revolut-homepage">
      <section className="revolut-scroll-experience" style={stageStyle}>
        <div className="revolut-scroll-sticky">
          <div className="revolut-scroll-surface">
            <RevolutTopbar onLogin={onLogin} onStart={onStart} variant="light" />
            <RevolutTopbar onLogin={onLogin} onStart={onStart} variant="dark" />
            <HeroScene onStart={onStart} />
            <SalaryScene onStart={onStart} />
          </div>
        </div>
      </section>

      <HowWeWorkSection />
      <WorkflowSection />
      <WhyUsSection />
      <SolutionsSection />
      <MetricsSection />
    </section>
  )
}
