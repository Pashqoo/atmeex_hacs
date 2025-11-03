# ⚠️ ВНИМАНИЕ: Добавьте файл brand.png

## Что нужно сделать

Для отображения логотипа в HACS и Home Assistant нужно добавить файл `brand.png` в корень репозитория.

### Шаги:

1. **Получите логотип ATMEEX:**
   - Скачайте с официального сайта
   - Или экспортируйте из мобильного приложения
   - Или создайте на основе описания логотипа

2. **Подготовьте изображение:**
   - Формат: PNG
   - Размер: 512x512 или 256x256 пикселей
   - Прозрачный фон (рекомендуется)
   - Размер файла: до 200 KB

3. **Сохраните как `brand.png`** в корне репозитория:
   ```
   /Users/pavelbakulin/bot/HA/atmeex_hacs_fixed/brand.png
   ```

4. **Загрузите на GitHub:**
   ```bash
   git add brand.png
   git commit -m "Add brand image"
   git push origin main
   ```

## После загрузки

Логотип будет отображаться:
- ✅ В каталоге HACS интеграций
- ✅ На странице интеграции в HACS
- ✅ В интерфейсе Home Assistant

**URL логотипа:** `https://raw.githubusercontent.com/Pashqoo/atmeex_hacs/main/brand.png`

