# Revolut Landing Entegrasyon Notları

## Amaç

Bu doküman, `awesome-design-md-main` deposunun ne yaptığı, nasıl kullanıldığı ve özellikle `design-md/revolut` örneğinin `ai-marketer` içindeki landing page'e nasıl entegre edileceğini ayrıntılı şekilde açıklar.

Hedef:
- landing page'i mevcut halinden çıkarıp Revolut benzeri bir tasarım sistemine taşımak
- sadece benzemek değil, aynı düzen mantığını, aynı tipografik hiyerarşiyi, aynı yüzey yaklaşımını ve aynı bileşen dilini kullanmak
- Aylin karakterini bu tasarım sisteminin merkezine yerleştirmek

---

## 1. `awesome-design-md-main` Nedir?

`awesome-design-md-main`, farklı markalardan çıkarılmış hazır `DESIGN.md` koleksiyonudur.

Ana mantık:
- her marka için bir tasarım sistemi dokümanı vardır
- bu dokümanlar AI ajanlarına "bu sayfa nasıl görünmeli" bilgisini verir
- Figma, token parser ya da özel schema gerekmez
- markdown tabanlı bir tasarım sistemi gibi çalışır

Repo yapısı:

```text
awesome-design-md-main/
  README.md
  design-md/
    revolut/
      DESIGN.md
      README.md
      preview.html
      preview-dark.html
```

### Repo ne işe yarıyor?

Bu repo doğrudan çalışan bir frontend kütüphanesi değil.

Bu repo:
- component library vermez
- React component export etmez
- npm paketi gibi kullanılmaz

Bu repo şunu verir:
- görsel kurallar
- tipografi hiyerarşisi
- renk rolleri
- buton, kart, form, nav davranışları
- responsive davranış kuralları

Yani entegrasyon biçimi "import et ve kullan" değil, "tasarım sistemini okuyup projeye uygula" şeklindedir.

---

## 2. `awesome-design-md-main` Nasıl Kullanılıyor?

Ana README'deki önerilen kullanım çok net:

1. İlgili sitenin `DESIGN.md` dosyasını al
2. Proje köküne veya çalışma bağlamına koy
3. AI ajanına "bu tasarım dilini kullan" de
4. UI'ı bu kurallar üzerinden üret

Repo içindeki her tasarım örneğinde genelde 3 dosya var:

- `DESIGN.md`
  Tasarımın sözel sistem dokümanı

- `preview.html`
  Açık tema örnek katalog

- `preview-dark.html`
  Koyu tema örnek katalog

### Bu projede bize ne kazandıracak?

Bizim kullanımımız doğrudan şu olacak:

- `DESIGN.md` = tasarımın kuralları
- `preview.html` = görsel referans ve component davranışı
- `preview-dark.html` = koyu yüzey kullanımlarında referans

Yani `revolut` klasörü bizim için:
- renk sistemi referansı
- tipografi referansı
- landing section yapısı için stil referansı
- buton/form radius ve padding sistemi için doğrudan örnek

---

## 3. `design-md/revolut` Ne Diyor?

### 3.1 Genel Tasarım Karakteri

Revolut örneği açıkça şu karakteri tarif ediyor:

- fintech güveni
- yüksek kontrast
- büyük ve agresif tipografi
- siyah / beyaz merkezli yüzey
- renkleri sınırlı ve kontrollü kullanma
- gölge yerine düz yüzey mantığı
- her butonda pill radius

En önemli karakter:

- "banking confidence"
- "big type"
- "flat surfaces"
- "premium but accessible"

Bu bizim ürün için çok uygun çünkü:
- kullanıcı ilk anda güven hissetmeli
- karışık SaaS paneli değil, net bir premium ürün hissi olmalı
- Aylin bir "yardımcı bot" değil, profesyonel çalışan sistem gibi algılanmalı

---

## 4. Revolut Tasarım Sisteminin Teknik Özeti

### 4.1 Ana Renkler

`DESIGN.md` ve `preview.html` üzerinden çıkan temel yüzey sistemi:

- Ana koyu: `#191c1f`
- Beyaz: `#ffffff`
- Açık yüzey: `#f4f4f4`
- Mavi vurgu: `#494fdf`
- Action blue: `#4f55f1`
- İkincil metin slate: `#505a63`
- Muted gray: `#8d969e`
- Border: `#c9c9cd`

Semantik renkler:
- danger: `#e23b4a`
- warning: `#ec7e00`
- teal: `#00a87e`
- pink: `#e61e49`
- yellow: `#b09000`

### 4.2 En kritik kural

Revolut pazarlama yüzeyinde her rengi her yerde kullanmıyor.

Asıl yüzey mantığı:
- siyah / beyaz / açık gri
- accent olarak kontrollü mavi
- semantik renkleri ürün alanı ya da uyarı katmanında saklama

Bu bizim için şu anlama geliyor:
- landing’de yeşil, mor, kahverengi, sıcak pastel gibi dağınık kararlar kaldırılmalı
- ana yüzeyler neredeyse monokrom olmalı
- mavi sadece vurgu ve focus için kullanılmalı

---

## 5. Tipografi

### 5.1 Dokümandaki hedef font

Revolut `DESIGN.md` şunu söylüyor:

- Display: `Aeonik Pro`
- Body/UI: `Inter`

### 5.2 Preview dosyalarındaki gerçek durum

`preview.html` ve `preview-dark.html` içinde display font olarak `DM Sans` kullanılmış.

Bu çok önemli bir nüans:

- Tasarım dokümanı Aeonik Pro referansı veriyor
- Ama örnek HTML lisans ve erişilebilirlik sebebiyle `DM Sans` kullanıyor

### 5.3 Bizim projede ne yapmalıyız?

Bu üç seçenekten biri:

1. **En güvenli yol**
   `Inter + DM Sans`

2. **Daha yakın yol**
   lisanslıysa `Aeonik Pro + Inter`

3. **Yakın ama açık kaynak alternatif**
   `Sora / Space Grotesk / Manrope + Inter`

### Karar önerisi

Bu proje için en doğru entegrasyon sırası:

- ilk uygulama: `DM Sans + Inter`
- istenirse ikinci turda `Aeonik Pro` lisanslı sağlanırsa ona geçiş

Sebep:
- şu an projede aynı görünümü hızlı ve yasal olarak üretmek daha önemli
- görsel karakterin büyük bölümü sadece font adı değil; ağırlık, tracking, line-height ve whitespace ile geliyor

---

## 6. Revolut'un En Kritik UI Kuralları

### 6.1 Buton sistemi

Revolut'ta en sert ve net sistem burası:

- tüm ana butonlar `9999px` radius
- padding geniş
- buton küçük değil, rahat
- primary dark pill
- secondary light pill
- outlined pill
- dark yüzey üstünde ghost pill

Bizim projede entegrasyon sonucu şu olmalı:

- tüm CTA'lar aynı aileden gelmeli
- karışık `18px`, `20px`, `14px` radius kullanımı temizlenmeli
- landing ve onboarding boyunca ana CTA'lar pill olmalı

### 6.2 Yüzey mantığı

Revolut'un belki en önemli farkı:

- neredeyse sıfır shadow
- depth, kontrast ve section ayrımıyla kuruluyor

Bu yüzden:
- bizim şu anki blur, glow, glassmorphism yoğunluğu azaltılmalı
- section ayrımı için:
  - beyaz yüzey
  - açık gri yüzey
  - koyu section
  - ince border
  yeterli olmalı

### 6.3 Border radius ölçeği

Revolut sistemi:
- küçük elementler: `12px`
- kartlar: `20px`
- pill öğeler: `9999px`

Bu projede tek bir radius scale tanımlanmalı:

- `--radius-sm: 12px`
- `--radius-md: 20px`
- `--radius-lg: 28px` sadece büyük özel hero yüzeylerinde gerekiyorsa
- `--radius-pill: 9999px`

---

## 7. Layout ve Whitespace Mantığı

Revolut'un görünürde sade durmasının ana nedeni boşluk.

Temel spacing mantığı:
- 8px bazlı sistem
- büyük section araları
- büyük tipografi + nefes alan boş yüzey
- çok fazla küçük kart değil, az ama kararlı blok

Bu nedenle bizim landing'de yapılması gerekenler:

- fazla sayıda küçük info kartı kaldırılmalı
- hero çevresindeki yüzen kartlar çok sınırlı kullanılmalı
- section'lar büyük yatay bantlar gibi düşünülmeli
- her blok tek ana fikir taşımalı

---

## 8. Mevcut Projede Nereye Entegre Edilecek?

### Etkilenecek ana dosyalar

- `src/App.tsx`
  landing section sırası ve içerik yapısı

- `src/index.css`
  ana token sistemi

- `src/styles/shell.css`
  landing, onboarding ve genel buton/component sistemleri

- `public/Aylin.jpg`
  hero görseli / portrait panel

### Gerekirse yeni dosyalar

- `src/styles/landing-revolut.css`
  tavsiye edilir

Sebep:
- mevcut `shell.css` çok büyüdü
- yeni landing radikal biçimde değişecek
- landing'i ayrı dosyada tutmak bakım maliyetini azaltır

---

## 9. İçerik Yapısını Revolut'a Nasıl Çevireceğiz?

Revolut örneğinin en güçlü tarafı:
- section'lar ürün mesajını çok net sırayla taşıyor

Bizim landing için önerilen yeni sıra:

### 1. Header
- sol: `AGENT AYLİN`
- orta: sade nav
- sağ: `Giriş yap` veya kullanıcı durumu

### 2. Hero
- dev tipografi
- kısa ama çok net açıklama
- iki CTA
- sağda Aylin'in portrait paneli

### 3. Güven / manifesto bandı
- "önce okur / sonra kurar / sonra yürütür"
- 3 ya da 4 kısa blok

### 4. Nasıl çalışır
- 4 adımlı süreç
- koyu section olabilir

### 5. Yetenekler
- capability grid
- küçük ama düzenli kartlar

### 6. İlk çıktılar
- `.md` dosyalarını daha ürünleşmiş şekilde sunan section

### 7. Neden biz
- tam ekip yerine agent yaklaşımını savunan section

### 8. Sosyal kanıt
- kısa testimonial blokları

### 9. Final CTA
- tekrar tek aksiyon

---

## 10. Aylin Görseli Bu Sisteme Nasıl Oturmalı?

Revolut örneğinde tasarım mantığı:
- ürünün ya da telefon arayüzünün merkezi bir premium objeye dönüşmesi

Bizde bu rolü:
- Aylin'in portresi
- ya da Aylin + belge / chat / output kompozisyonu
oynayabilir

En doğru kullanım:

- hero'nun sağında koyu büyük portrait panel
- panel içinde küçük status chip'ler
- altına kısa açıklama

Yapılmaması gerekenler:
- her yerde tekrar tekrar Aylin yüzü
- fazla sticker, glow, bubble
- çizgi film / duygusal maskot estetiği

Hedef his:
- premium agent
- ciddi ama sıcak
- teknoloji + güven

---

## 11. Font Entegrasyonu Nasıl Yapılacak?

### Tavsiye edilen ilk kurulum

Google Fonts üzerinden:
- `Inter`
- `DM Sans`

`index.css`:

```css
--font-display: 'DM Sans', system-ui, sans-serif;
--font-body: 'Inter', system-ui, sans-serif;
```

### Display kuralları

- hero: 72px - 96px arası
- weight: `500`
- line-height: `1.00`
- negative tracking

### Body kuralları

- 16px / 18px
- `Inter`
- geniş ama kontrollü satır aralığı

---

## 12. Renk Entegrasyonu Nasıl Yapılacak?

Önerilen landing token seti:

```css
--landing-bg: #ffffff;
--landing-surface: #f4f4f4;
--landing-ink: #191c1f;
--landing-muted: #505a63;
--landing-muted-2: #8d969e;
--landing-border: #c9c9cd;
--landing-accent: #494fdf;
--landing-accent-2: #4f55f1;
--landing-danger: #e23b4a;
--landing-success: #00a87e;
```

### Kullanım kuralı

- sayfa zemini: beyaz
- section alternation: beyaz / açık gri / koyu
- ana CTA: koyu
- secondary CTA: açık gri
- outline CTA: koyu border
- accent mavi: sadece highlight, focus ring, küçük UI detaylarında

---

## 13. Şu Anki Tasarımla Revolut Arasındaki Fark

Mevcut halimiz:
- daha yumuşak
- daha "glass" hissi var
- daha çok dekoratif ambient kullanıyor
- renkler daha karışık

Revolut yaklaşımı:
- daha sert
- daha düz yüzeyli
- daha büyük tipografi
- daha az renk
- daha kararlı boşluk

Bu yüzden entegrasyon sadece "rengi değiştir" işi değil.

Tam yapılması gereken:
- landing sayfasını section section yeniden kurmak
- radius sistemini sadeleştirmek
- buton sistemini yeniden standardize etmek
- shadow'ları azaltmak
- typography scale'i yeniden yazmak

---

## 14. Entegrasyon Stratejisi

### Faz 1
- mevcut landing'i dondur
- `landing-v3` gibi ayrı bir Revolut tabanlı yapı kur

### Faz 2
- font sistemi: `DM Sans + Inter`
- yeni token sistemi

### Faz 3
- hero ve topbar'ı Revolut mantığına taşı

### Faz 4
- section yapısını yeniden kur

### Faz 5
- butonlar, kartlar, form alanları, radius ve spacing standardizasyonu

### Faz 6
- onboarding adımlarını da aynı sistemle hizala

### Faz 7
- workspace'e sadece renk ve tipografi yansıt, ama landing kadar birebir kopyalama yapma

---

## 15. Kritik Notlar

### Font lisansı

`Aeonik Pro` ticari lisans gerektirebilir. Bu yüzden:
- doğrudan kullanmadan önce lisans netliği şart
- hızlı ve güvenli entegrasyon için `DM Sans` daha gerçekçi

### Görsel / marka kimliği

Revolut'un tasarım sistemi alınabilir; ancak metin ve marka anlatısı bizim ürüne özgü kalmalı.

Yani:
- görsel dil Revolut
- ürün hikâyesi Aylin

### Aynı şablon kullanımı

Evet, aynı template mantığı kullanılabilir:
- büyük hero
- pill CTA
- geniş boşluk
- section-driven marketing layout

Ama bunu `Aylin` ürününe adapte ederek yapacağız.

---

## 16. Sonuç

`awesome-design-md-main` bu projeye doğrudan component sağlayan bir kütüphane değil; AI destekli tasarım referans deposu.

`revolut` klasörü bize şunları veriyor:
- kullanılacak renk sistemi
- tipografi mantığı
- radius ve buton sistemi
- gölgesiz yüzey yaklaşımı
- whitespace ve section düzeni

Bu nedenle en doğru entegrasyon yaklaşımı:

1. `revolut/DESIGN.md` kurallarını tasarım kaynağı yapmak
2. `preview.html` üzerinden component davranışlarını birebir referans almak
3. landing'i yeniden kurmak
4. aynı dili onboarding'e taşımak
5. workspace'e daha hafif biçimde yansıtmak

---

## Önerilen Sonraki Adım

Bir sonraki turda doğrudan şu işi yapacağız:

- mevcut landing'i Revolut tabanlı `landing-v3` olarak baştan inşa etmek
- `DM Sans + Inter`
- `#191c1f / #ffffff / #f4f4f4 / #494fdf`
- sıfır shadow ya da çok minimale inmiş shadow
- tam pill CTA sistemi
- Aylin portrait panelini Revolut'un ürün objesi mantığında konumlamak

