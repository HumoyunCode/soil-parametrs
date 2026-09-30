# O'zbekiston Tuproq Qatlamlari Tahlili Tizimi (SoilGrids GIS Portal)

PhD ilmiy tadqiqot loyihasi uchun ishlab chiqilgan interaktiv geoinformatsion (GIS) platforma.

## 📌 Loyiha haqida
Ushbu platforma ISRIC SoilGrids v2.0 global tuproq ma'lumotlar bazasi va O'zbekiston agro-ekologik tuproq xaritalari asosida yaratilgan. Xarita orqali O'zbekistonning istalgan nuqtasi (dala, tuman, viloyat) tanlanganda, ushbu nuqtadagi tuproqning turli chuqurlik qatlamlari bo'yicha fizik-kimyoviy va agronomik parametrlari avtomatik hisoblanadi va tahlil qilinadi.

### Asosiy Imkoniyatlar:
- **Interaktiv Xarita (Leaflet.js)**:
  - O'zbekiston davlat chegarasi va hududlari bo'yicha markazlashtirilgan.
  - 4 xil qatlam: Sun'iy yo'ldosh (Esri Satellite), Qorong'u rejim (Dark GIS), Relyef (OpenTopoMap) va Standart ko'cha (OSM).
  - Istalgan joyga bosish (click) yoki pinni surish (drag & drop) orqali koordinatani tanlash.
  - O'zbekistonning barcha 14 ta ma'muriy hududlari bo'yicha tezkor o'tish (presets).
- **Qatlamlar Kesimidagi Parametrlar**:
  - Chuqurliklar: `0-5 sm`, `5-15 sm`, `15-30 sm`, `30-60 sm`, `60-100 sm`.
  - Tuproq muhiti ($\text{pH}_{\text{H}_2\text{O}}$).
  - Organik uglerod ($\text{SOC}$, g/kg).
  - Gumus / Chirindi ($\text{SOM} = \text{SOC} \times 1.724 / 10$, %).
  - Gektariga hisoblangan gumus zaxirasi ($t/\text{ga}$).
  - Umumiy Azot ($\text{N}$, g/kg).
  - Kation almashinuv sig'imi ($\text{CEC}$, $\text{cmol}(+)/\text{kg}$).
  - Tuproq zichligi / Hajm massasi ($\text{Bulk Density}$, $\text{g}/\text{sm}^3$).
  - Granulometrik tarkib: Loy ($\text{Clay}$), Qum ($\text{Sand}$), Chang ($\text{Silt}$) foizlari.
  - USDA va milliy tasnif bo'yicha mexanik tarkib (Masalan: *O'rta qumoq*, *Qumloq*, *Gilli*).
- **Vizual Grafika va Tahlil (Chart.js)**:
  - Chuqurlik oshishi bilan parametrlar dinamikasi chiziqli grafigi.
  - Donadorlik (mexanik tarkib) nisbati diagrammasi.
  - Agronomik baholash va ekinlar tavsiyasi (paxta, g'alla, meva-sabzavot).
- **Eksport va Hisobot**:
  - Natijalarni to'liq jadval ko'rinishida Excel / CSV formatida yuklab olish.
  - Ilmiy hisobotlar uchun JSON formatida nusxalash.
  - Chop etish yoki PDF sifatida saqlash.

## 🚀 Ishga Tushirish

1. Kutubxonalarni o'rnatish:
```bash
pip install -r requirements.txt
```

2. Serverni ishga tushirish:
```bash
python main.py
```
yoki:
```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

3. Brauzerda ochish:
```
http://127.0.0.1:8000
```
