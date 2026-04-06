# Revolut Şablon Çıkartımı

Bu not, `awesome-design-md-main/design-md/revolut` içeriğinin tam olarak ne anlattığını ve bunun canlı `revolut.com` ana sayfasından hangi noktalarda ayrıldığını netleştirmek için hazırlandı.

## 1. Çok önemli ayrım

Repo içindeki `revolut` klasörü iki farklı şey içeriyor:

1. `DESIGN.md`
Bu dosya bir **tasarım sistemi özeti**.
Canlı ana sayfanın tam HTML iskeletini vermez.

2. `preview.html` ve `preview-dark.html`
Bunlar bir **tasarım katalog demo sayfası**.
Canlı Revolut homepage'i değildir.
Renk, tipografi, buton, card, form ve spacing davranışını gösteren örnek sayfalardır.

Yani bu klasör şunu söyler:
"Revolut gibi görünen bir tasarım dili kur."

Ama şunu söylemez:
"Canlı ana sayfayı birebir bu DOM yapısıyla kopyala."

## 2. DESIGN.md ne diyor

Ana mesajlar:

- Büyük, agresif, güven veren tipografi
- Near-black + white ağırlıklı yüzey
- Mavi sadece vurgu
- Pill buton sistemi
- Çok az gölge, neredeyse düz yüzey
- Geniş boşluk kullanımı
- Display font olarak `Aeonik Pro`
- Body/UI için `Inter`

Temel renkler:

- `#191c1f` ana koyu
- `#ffffff` beyaz
- `#f4f4f4` açık yüzey
- `#494fdf` mavi vurgu
- `#505a63` secondary text
- `#8d969e` muted text
- `#c9c9cd` border

Temel component kuralları:

- Bütün butonlar `9999px` radius
- Primary button koyu
- Secondary button açık gri
- Outline button koyu border
- Ghost button dark surface üzerinde açık sınırla
- Kart radius `20px`
- Küçük surface radius `12px`
- Gölge yok ya da yok denecek kadar az

Tipografi:

- Display hiyerarşisi çok büyük
- Heading'lerde weight `500`
- Negatif tracking
- Body text `Inter`
- Body textte daha sakin ve okunur spacing

## 3. preview.html ne gösteriyor

`preview.html` canlı Revolut ana sayfasını göstermiyor.

Gösterdiği şeyler:

- Sticky nav
- Basit hero
- Color swatch alanı
- Typography örnekleri
- Button varyantları
- Card örnekleri
- Form örnekleri
- Spacing scale
- Radius scale
- Elevation örnekleri

Yani:
- Bu bir **marketing homepage clone** değil
- Bu bir **design token showcase**

## 4. Canlı Revolut ana sayfası ne yapıyor

Canlı ana sayfada özellikle hero kısmında görülen yapı:

- Tam ekran mavi blur/gradyan arka plan
- Üstte çok sade beyaz nav
- Solda dev headline
- Altında kısa değer önerisi
- Solda koyu pill CTA
- Sağda büyük cutout insan görseli
- Görselin arkasında ince bir device/account frame
- Üstüne bindirilmiş finansal kart elementi

Yani canlı site:
- design system preview'den daha sinematik
- daha art-direct edilmiş
- daha fotoğraf odaklı
- daha az "katalog", daha çok "hero composition"

## 5. Şu anki hatam neydi

Ben ilk turda `preview` mantığını referans aldım.
Bu yüzden ortaya çıkan şey:

- Revolut tasarım dili taşıyan ama
- canlı homepage kompozisyonunu taşımayan
- daha katalog / demo mantıklı bir sayfa oldu

Bu yüzden sen haklı olarak:
"Bu canlı Revolut’a benzemiyor"
dedin.

## 6. Şu anki canlı sitede image küçülme hissi neden oluyor

Bu davranış template dokümanında yok.

Bu, benim landing implementasyonumdan geliyor.
Özellikle şu tip kararlar bu hissi doğurabiliyor:

- hero içinde görselin `absolute` yerleşmesi
- width’in yüzde ile verilmesi
- hero yüksekliğinin viewport’a göre çözülmesi
- alttaki section’a geçerken görselin kadrajının değişmesi

Yani bu davranış:
- `DESIGN.md` kararı değil
- `preview` kararı değil
- benim canlı hero’yu tahmin ederek kurmamdan gelen bir uygulama farkı

## 7. Referans bize tam olarak ne emrediyor

Eğer sadece `revolut/DESIGN.md` ve `preview`e sadık kalacaksak:

- beyaz arka plan
- koyu metin
- büyük ama kontrollü başlıklar
- DM Sans / Inter benzeri tipografi
- flat cards
- pill buttons
- spacing üzerinden lüks his
- section section ilerleyen bir marketing page

Eğer canlı ana sayfaya sadık kalacaksak:

- mavi immersive hero
- beyaz navigation
- fotoğraf merkezli composition
- büyük overlay heading
- görsel üstü ürün kartları / trust öğeleri
- daha dramatik art direction

## 8. Bundan sonra doğru yol

Bence doğru sıralama şu:

1. Önce karar ver:
   - `preview/design-system` mi kopyalanacak
   - yoksa canlı `revolut.com` hero ve homepage yapısı mı kopyalanacak

2. Eğer senin son mesajını baz alırsak doğru hedef:
   - **canlı Revolut homepage**

3. O zaman şunları yapmalıyız:
   - preview mantığını tamamen bırak
   - canlı hero composition'ı birebir kur
   - nav spacing’ini birebir yaklaştır
   - hero typography oranlarını yakınlaştır
   - visual stack’i birebir kur
   - scroll davranışını sabit ve kontrollü yap

## 9. Net sonuç

Şu an referansı iki farklı kaynaktan okuyoruz:

- `DESIGN.md` = stil kuralları
- canlı site = gerçek homepage kompozisyonu

Benim önceki sapmam şu oldu:
- stil kurallarını aldım
- homepage kompozisyonunu yeterince birebir taşımadım

Bu yüzden bundan sonraki net kural şu olmalı:

**Landing için referans artık `revolut.com` canlı homepage olsun.**

`DESIGN.md` sadece yardımcı kurallar seti olarak kalsın:
- renk
- font
- button radius
- spacing
- flatness

