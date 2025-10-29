Вот готовый **`README.md`**, полностью соответств jums требованиям, с чёткой структурой, командами и пояснениями:

---

```markdown
# Конвертер документов → Markdown с OCR и пост-очисткой (Ollama + MinerU)

Автоматическая обработка PDF, DOCX, EPUB, изображений (JPG/PNG) и Markdown-файлов с извлечением текста, распознаванием структуры и очисткой через LLM (Ollama).

---

## Требования

- Ubuntu / Debian-подобная система
- Доступ к интернету (для загрузки моделей)
- GPU **не обязателен** (работает на CPU)

---

## Установка

```bash
# 1. Установка Python 3.11 и инструментов
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip curl git tesseract-ocr
sudo apt install -y libreoffice imagemagick ghostscript poppler-utils


# 2. Создание виртуального окружения
python3.11 -m venv venv_llm
source venv_llm/bin/activate

# 3. Обновление pip и установка uv
pip install -U pip uv Pillow reportlab ollama 

# 4. Установка зависимостей
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
uv pip install "mineru[core]" python-dotenv pytesseract loguru pypdfium2 langdetect python-magic docx2txt ebooklib beautifulsoup4

# 5. Установка Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 6. Запуск Ollama и загрузка модели
ollama serve &  # запуск в фоне
ollama pull qwen2.5:0.5b-instruct-q4_K_M   # основная модель (быстрая, ~300 МБ)
# Альтернативы (по желанию):
# ollama pull phi3.5:3.8b-mini-instruct-q4_K_M
# ollama pull deepseek-r1:1.5b
# ollama pull deepseek-r1:7b-qwen-distill-q4_K_M
# ollama pull qwen3:4b

# Проверить доступные модели
ollama list
```

> **Примечание**: `qwen2.5:0.5b-instruct-q4_K_M` — оптимальна по скорости и качеству для очистки Markdown.

---

## Загрузка моделей MinerU (OCR + Layout)

```bash
# Установка всех моделей для OCR и анализа структуры
mineru-models-download -m all
# или только для pipeline:
# mineru-models-download -m pipeline
```

> Это скачает модели для распознавания текста, таблиц, формул и макета.

---

## Клонирование и запуск

```bash
git clone https://github.com/yourusername/document-converter.git
cd document-converter

# Скопировать пример .env
cp .env.example .env
```

---

## Настройка `.env`

```properties
# Путь к папке с входными файлами
PATH_DIR="."

# Промт для пост-очистки через Ollama
CLEAN_PROMPT="[ROLE]: 
You are Expert in Multilingual Document Reconstruction (OCR Specialist). [CONSTRAINT]: Strictly forbidden: Do not output code, explanations, introductions, or conclusions. Output ONLY the reconstructed text.

[TASK PRIORITIES]:

Reconstruction: Restore original multilingual technical terms, brands, and unique names to their correct form (disregarding phonetics or transliteration).

Sanitization/Cleanup: Remove headers/footers, page numbers, duplicates, and any stray digits, symbols, or formatting artifacts that are not part of the restored content.

Preservation: Maintain the original language, case (capitalization), and structure (including Markdown).

[INPUT TEXT]:"
```

---

## Запуск

```bash
# Активировать окружение (если ещё не)
source venv_llm/bin/activate

# Запуск конвертации
python3.11 convert-1.py
```

---

## Что происходит?

1. Сканируется `PATH_DIR` (по умолчанию — текущая папка)
2. Поддерживаемые файлы: `.pdf`, `.docx`, `.epub`, `.jpg`, `.jpeg`, `.png`
3. Извлекается текст + структура (через **MinerU**)
4. Сохраняется **сырой** `.raw.md`
5. Очищается через **Ollama** → финальный `.md`
6. Пропускаются уже обработанные файлы

---

## Выходные данные

```
output/
├── document.pdf.raw.md     ← сырой вывод MinerU
└── document.pdf.md         ← очищенный через LLM
```

---

## Пример использования

```bash
# Положите файлы в текущую папку
cp ~/Documents/*.pdf .

# Запустите
python3.11 convert-1.py
```

---

## Рекомендации

- Используйте `qwen2.5:0.5b` — быстро и точно для очистки
- Для сложных PDF с формулами — `mineru-models-download -m all`
- Не забудьте `source venv_llm/bin/activate` при каждом запуске

---

## Устранение неисправностей


`ollama not found` Перезапустите `ollama serve &` 
`No module named 'mineru'`  Убедитесь, что `uv pip install "mineru[core]"` прошёл 
 Пустой вывод |Проверьте, что Tesseract установлен: `tesseract --version` 

---

**Готово!** Теперь вы можете массово конвертировать документы в чистый Markdown.
```

---

### Дополнительно: создайте `.env.example`

```properties
PATH_DIR="."
CLEAN_PROMPT="[ROLE]: 
You are Expert in Multilingual Document Reconstruction (OCR Specialist). [CONSTRAINT]: Strictly forbidden: Do not output code, explanations, introductions, or conclusions. Output ONLY the reconstructed text.

[TASK PRIORITIES]:

Reconstruction: Restore original multilingual technical terms, brands, and unique names to their correct form (disregarding phonetics or transliteration).

Sanitization/Cleanup: Remove headers/footers, page numbers, duplicates, and any stray digits, symbols, or formatting artifacts that are not part of the restored content.

Preservation: Maintain the original language, case (capitalization), and structure (including Markdown).

[INPUT TEXT]:"
```

---
