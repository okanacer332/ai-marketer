import type { Analysis, MemoryFile } from './types'

const aylinAvatar = '/Aylin.png'

export type Step =
  | 'specialist'
  | 'signup'
  | 'website'
  | 'goals'
  | 'integrations'
  | 'workspace'

export type Specialist = {
  id: string
  name: string
  role: string
  summary: string
  skills: string[]
  available: boolean
  avatar: string
}

export type Goal = {
  id: string
  label: string
  short: string
  blurb: string
}

export type Platform = {
  id: string
  name: string
  blurb: string
}

export const specialists: Specialist[] = [
  {
    id: 'aylin',
    name: 'Olric',
    role: 'Bütünleşik dijital pazarlamacı',
    summary:
      'SEO, sosyal medya, reklam ve kampanya planlamasını tek bir büyüme sorumlusu gibi uçtan uca yönetir.',
    skills: ['SEO sistemi', 'Reklam kreatif döngüsü', 'İçerik ve sosyal medya operasyonu'],
    available: true,
    avatar: aylinAvatar,
  },
  {
    id: 'can',
    name: 'Can',
    role: 'SEO ve içerik yöneticisi',
    summary:
      'Ticari niyet odaklı arama stratejisi, landing page fikri ve içerik planı oluşturur.',
    skills: ['Konu kümeleri', 'Rakip boşlukları', 'Dönüşüm odaklı metin'],
    available: false,
    avatar: aylinAvatar,
  },
  {
    id: 'zeynep',
    name: 'Zeynep',
    role: 'E-posta ve otomasyon uzmanı',
    summary:
      'Geliri geri kazandıran ve mevcut müşteriyi sıcak tutan yaşam döngüsü akışları tasarlar.',
    skills: ['Akışlar ve tetikler', 'Sadakat kampanyaları', 'Teklif kurgusu'],
    available: false,
    avatar: aylinAvatar,
  },
  {
    id: 'mert',
    name: 'Mert',
    role: 'Performans kreatif stratejisti',
    summary:
      'Ürün içgörülerini reklam konseptlerine, kancalara ve test planlarına dönüştürür.',
    skills: ['Kreatif testleri', 'Ücretli medya briefleri', 'Kitle açıları'],
    available: false,
    avatar: aylinAvatar,
  },
]

export const goalOptions: Goal[] = [
  {
    id: 'social-media',
    label: 'Sosyal Medya',
    short: 'SM',
    blurb: 'Kısa format kanallara doğal hissettiren içerik planları oluştur.',
  },
  {
    id: 'seo',
    label: 'SEO',
    short: 'SEO',
    blurb: 'Talep yakalamayı sistemli bir içerik ve landing page akışına çevir.',
  },
  {
    id: 'content-writing',
    label: 'İçerik Yazarlığı',
    short: 'İY',
    blurb: 'Blog yazıları, kategori metinleri ve eğitici dönüşüm içerikleri üret.',
  },
  {
    id: 'email-marketing',
    label: 'E-posta Pazarlaması',
    short: 'EP',
    blurb: 'Müşteri yolculuğunu kampanyalara çevirerek tekrar satın alımı artır.',
  },
  {
    id: 'paid-ads',
    label: 'Ücretli Reklamlar',
    short: 'ÜR',
    blurb: 'Reklam kanallarını daha güçlü açılar, kanıtlar ve test fikirleriyle besle.',
  },
]

export const platformOptions: Platform[] = [
  {
    id: 'google-analytics',
    name: 'Google Analytics',
    blurb: 'Trafik modeli, yüksek niyetli sayfalar ve yardımcı dönüşüm yollarını sunar.',
  },
  {
    id: 'meta-ads',
    name: 'Meta Ads',
    blurb: 'Kreatif performansı, kitleler ve maliyet sinyalleriyle reklam kararlarını güçlendirir.',
  },
  {
    id: 'instagram',
    name: 'Instagram',
    blurb: 'İçerik dili, yorumlar ve kullanıcıların zaten ilgi gösterdiği sinyalleri getirir.',
  },
  {
    id: 'shopify',
    name: 'Shopify veya Ticimax',
    blurb: 'Katalog, ürün yerleşimi ve ürün bazlı davranış verilerini taşır.',
  },
]

export const capabilityTags = [
  'SEO blog yazıları',
  'E-posta akışları',
  'Rakip haritalama',
  'Hedef kitle araştırması',
  'Landing page stratejisi',
  'Kreatif testleri',
  'Teklif kancaları',
  'Büyüme deneyleri',
  'Reklam metni güncelleme',
  'Marka hafızası',
]

export const chatTasks = [
  'İçeriği topluyorum',
  'Önemli sayfaları ve teklif yapısını tarıyorum',
  'Pazar ve fırsat sinyallerini yorumluyorum',
  'Çalışma dosyalarını kaydediyorum',
]

export function normalizeWebsite(input: string) {
  const trimmed = input.trim()

  if (!trimmed) {
    return ''
  }

  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed
  }

  return `https://${trimmed}`
}

function readDomain(input: string) {
  const normalized = normalizeWebsite(input)

  if (!normalized) {
    return ''
  }

  try {
    return new URL(normalized).hostname.replace(/^www\./, '')
  } catch {
    return normalized
      .replace(/^https?:\/\//, '')
      .replace(/^www\./, '')
      .split('/')[0]
  }
}

function humanizeName(value: string) {
  return value
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

export function buildAnalysis(website: string, goals: string[], platforms: string[]) {
  const domain = readDomain(website) || 'yourbrand.com'
  const rootName = domain.split('.')[0] || 'yourbrand'
  const companyName = humanizeName(rootName) || 'Markanız'
  const activeGoals = goals.length > 0 ? goals : ['Sosyal Medya', 'SEO', 'İçerik Yazarlığı']
  const connectedText =
    platforms.length > 0
      ? ` ve ${platforms.join(', ')} bağlantılarından gelen ek sinyallerle`
      : ''

  return {
    companyName,
    domain,
    logoUrl: null,
    brandAssets: null,
    sector: 'teklifini dijital kanallarda daha net anlatmak isteyen bir işletme',
    offer: 'ziyaretçiye net değer önerisi sunan bir ürün ya da hizmet yapısı',
    audience: 'güven, açıklık ve doğru yönlendirme bekleyen potansiyel müşteriler',
    tone: 'akıllı, insani ve doğrudan',
    pricePosition: 'değer odaklı, netleştirildikçe daha güçlü konumlanabilecek',
    competitors: [
      'kategori liderleri',
      'arama görünürlüğü güçlü rakipler',
      'mesajını daha net anlatan benzer markalar',
    ],
    opportunity: `${companyName}, hikâyesini ${activeGoals
      .slice(0, 3)
      .join(', ')} boyunca aynı çizgide anlatıp en güçlü ürün vaadini tekrar edilebilir bir müşteri kazanım sistemine dönüştürebilir${connectedText}.`,
    firstMonthPlan: [
      'Ana vaadi netleştir ve satın alma niyetli müşteri problemleri etrafında içerik kurgula.',
      'Organik ve ücretli kanallar için kanıt odaklı kampanya açıları hazırla.',
      'Net deneyler ve haftalık çıktılarla bir aylık operasyon ritmi kur.',
    ],
    palette: ['#191C1F', '#4DA3FF', '#E7FFDD', '#FFE3F3'],
  }
}

export function buildMemoryFiles(analysis: Analysis, website: string, goals: string[]) {
  const selectedGoals =
    goals.length > 0 ? goals.join(', ') : 'SEO, İçerik Yazarlığı, Sosyal Medya'

  const files: MemoryFile[] = [
    {
      id: 'business-profile',
      filename: 'isletme-profili.md',
      title: 'İşletme Profili',
      blurb: 'Teklif, hedef kitle, fiyat algısı ve ilk önceliklerin özeti.',
      content: `# İşletme Profili

## Özet
- Şirket: ${analysis.companyName}
- Website: ${normalizeWebsite(website) || `https://${analysis.domain}`}
- Ana teklif: ${analysis.sector}
- Ürün vaadi: ${analysis.offer}
- Ana hedef kitle: ${analysis.audience}
- Fiyat konumu: ${analysis.pricePosition}
- İstenen destek: ${selectedGoals}

## İlk değerlendirme
${analysis.companyName}, değerini hızlı anlattığında ve net bir sonuca bağladığında daha güçlü görünüyor. Buradaki asıl fırsat yalnızca daha fazla pazarlama yapmak değil; markayı inandırıcı ve farklı kılan çizgiyi daha iyi paketlemek.

## Çalışma ilkesi
Her kampanya şu soruya yanıt vermeli:
"Neden bu markaya şimdi güvenmeliyim?"
`,
    },
    {
      id: 'brand-guidelines',
      filename: 'marka-kilavuzu.md',
      title: 'Marka Kılavuzu',
      blurb: 'Ton, renk yönü, başlık kuralları ve korunacak iletişim çizgisi.',
      content: `# Marka Kılavuzu

## Ses ve ton
- Ton: ${analysis.tone}
- Kişilik: bilgili, yardımsever, enerjik
- Yazım kuralı: zekâdan önce netlik
- Müşteri tavrı: yönlendir ama baskı kurma

## Görsel yön
- Ana palet: ${analysis.palette.join(', ')}
- Hissiyat: editoryal, modern ve güven veren
- Kontrast stratejisi: sakin nötrlerle tek bir canlı vurgu rengi kullan

## Metin prensipleri
1. Özelliği değil sonucu öne çıkar.
2. Mümkün olan her yerde kanıt kullan.
3. Başlıkları spesifik ve düşük jargonlu tut.
4. Genel bir araç gibi değil, becerikli bir ekip arkadaşı gibi konuş.
`,
    },
    {
      id: 'market-research',
      filename: 'pazar-arastirmasi.md',
      title: 'Pazar Araştırması',
      blurb: 'Rakipler, arama ve mesaj boşlukları, en hızlı büyüme alanları.',
      content: `# Pazar Araştırması

## Muhtemel rakip kümesi
- ${analysis.competitors.join('\n- ')}

## Gözlenen boşluk
Birçok rakip özellik ya da fiyat üzerinden yarışırken ${analysis.companyName}, netlik, kanıt ve kime hitap ettiğini daha iyi anlatarak ayrışabilir.

## Arama ve kanal fırsatı
- Niyet gücü yüksek karşılaştırma ve problem tanımı etrafında sayfalar hazırla.
- Müşteri itirazlarını içerik temalarına ve reklam kancalarına çevir.
- Aynı içgörüyü SEO, sosyal medya, reklam ve yaşam döngüsü mesajlarında tekrar kullan.

## Çalışma tezi
${analysis.opportunity}
`,
    },
    {
      id: 'strategy',
      filename: 'strateji.md',
      title: '30 Günlük Strateji',
      blurb: 'İlk ay uygulanacak öncelikler ve operasyon ritmi.',
      content: `# Strateji

## İlk ay öncelikleri
${analysis.firstMonthPlan.map((item, index) => `${index + 1}. ${item}`).join('\n')}

## Operasyon ritmi
- 1. hafta: konumlandırma sentezi ve kanal briefleri
- 2. hafta: landing page'ler ve ilk içerik paketi
- 3. hafta: sosyal medya ve reklam kreatif iterasyonları
- 4. hafta: e-posta katmanı ve performans değerlendirmesi

## Başarı sinyali
Marka hikâyesi her temas noktasında daha kolay tekrar edilir hâle geldikçe müşteri kazanımı ucuzlar ve dönüşümü savunmak kolaylaşır.
`,
    },
  ]

  return files
}
