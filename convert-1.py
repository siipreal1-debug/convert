import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import ollama
from loguru import logger
from mineru.data.data_reader_writer import FileBasedDataWriter
from mineru.utils.enum_class import MakeMode
from mineru.cli.common import read_fn, prepare_env
from mineru.backend.pipeline.pipeline_analyze import doc_analyze
from mineru.backend.pipeline.pipeline_middle_json_mkcontent import union_make
from mineru.backend.pipeline.model_json_to_middle_json import result_to_middle_json
from mineru.cli.common import convert_pdf_bytes_to_bytes_by_pypdfium2 
import pypdfium2 as pypdfium
from langdetect import detect
import magic
import subprocess
import tempfile
import time
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io
from reportlab.lib.utils import ImageReader

# === НОВЫЕ ИМПОРТЫ ДЛЯ EPUB/HTML → PDF ===
try:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    logger.warning("weasyprint не установлен. EPUB/HTML → PDF отключены.")

# === КОНФИГУРАЦИЯ ===
INPUT_DIR = Path(".")
OUTPUT_DIR = Path("output")
SUPPORTED_EXT = {'.pdf', '.jpg', '.jpeg', '.png', '.docx', '.epub', '.html', '.htm'}
SKIP_EXT = {'.py', '.md', '.txt', '.MD'}
OLLAMA_MODEL = 'qwen2.5:0.5b-instruct-q4_K_M'
TIMEOUT_SEC = 680
MAX_LEN = 8000
TEMPERATUR = 0.2

# === ИНИЦИАЛИЗАЦИЯ ===
load_dotenv()
os.makedirs(OUTPUT_DIR, exist_ok=True)
logger.remove()

env_path = os.getenv('PATH_DIR')
if not env_path:
    logger.error("PATH_DIR не задан в .env! Используется текущая папка.")
    INPUT_DIR = Path(".")
else:
    INPUT_DIR = Path(env_path)

if not INPUT_DIR.exists() or not INPUT_DIR.is_dir():
    logger.error(f"Папка не существует: {INPUT_DIR}")
    sys.exit(1)

logger.add(sys.stderr, level="INFO")

CLEAN_PROMPT = os.getenv('CLEAN_PROMPT')
if not CLEAN_PROMPT:
    logger.warning("CLEAN_PROMPT не задан в .env! Очистка отключена.")
    CLEAN_PROMPT = "Очисти текст, сохрани структуру."

LLM_clean = os.getenv('LLM_CLEAN')
if not LLM_clean:
    LLM_clean = 'qwen2.5:0.5b-instruct-q4_K_M'
OLLAMA_MODEL = LLM_clean

# === КОНВЕРТАЦИЯ В PDF ===
# === КОНВЕРТАЦИЯ В PDF ===
def convert_to_pdf(file_path: Path, output_dir: Path) -> Path | None:
    ext = file_path.suffix.lower()
    pdf_path = output_dir / f"{file_path.stem}.pdf"

    if pdf_path.exists():
        print(f"  → PDF уже существует: {pdf_path.name}")
        return pdf_path

    try:
        # === DOCX → PDF (LibreOffice) ===
        if ext == '.docx':
            result = subprocess.run([
                "libreoffice", "--headless", "--convert-to", "pdf",
                "--outdir", str(output_dir), str(file_path)
            ], capture_output=True, text=True, timeout=90)

            if result.returncode == 0 and pdf_path.exists():
                print(f"  → LibreOffice: {file_path.name} → {pdf_path.name}")
                return pdf_path
            else:
                logger.warning(f"LibreOffice ошибка: {result.stderr.strip()}")
                return None

# === EPUB / HTML → PDF (weasyprint) ===
        elif ext in {'.epub', '.html', '.htm'} and WEASYPRINT_AVAILABLE:
            html_content = ""

            if ext == '.epub':
                try:
                    book = epub.read_epub(str(file_path))
                    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                        soup = BeautifulSoup(item.get_content(), 'html.parser')
                        html_content += str(soup) + "\n"
                except Exception as e:
                    logger.error(f"Ошибка чтения EPUB {file_path.name}: {e}")
                    return None
            else:
                # Для .html и .htm
                try:
                    html_content = file_path.read_text(encoding='utf-8', errors='replace')
                except Exception as e:
                    logger.error(f"Ошибка чтения HTML {file_path.name}: {e}")
                    return None

            # === КРИТИЧЕСКАЯ ПРОВЕРКА ===
            if html_content is None:
                logger.error(f"html_content is None для {file_path.name}")
                return None
            if not html_content.strip():
                logger.warning(f"Пустой HTML-контент после парсинга: {file_path.name}")
                return None

            full_html = f"<html><head><meta charset='utf-8'/></head><body>{html_content}</body></html>"

            # Временный HTML файл
            tmp_html_fd, tmp_html_path = tempfile.mkstemp(suffix='.html', text=True)
            try:
                with os.fdopen(tmp_html_fd, 'w', encoding='utf-8') as f:
                    f.write(full_html)

                HTML(tmp_html_path).write_pdf(str(pdf_path))
                print(f"  → {'EPUB' if ext == '.epub' else 'HTML'} → PDF: {file_path.name} → {pdf_path.name}")
                return pdf_path
            except Exception as e:
                logger.error(f"Ошибка WeasyPrint при конвертации {file_path.name}: {e}")
                return None
            finally:
                try:
                    os.unlink(tmp_html_path)
                except OSError:
                    pass  # Игнорируем, если файл уже удалён

        # === JPG/PNG → PDF ===
        elif ext in {'.jpg', '.jpeg', '.png'}:
            img = Image.open(file_path).convert("RGB")
            c = canvas.Canvas(str(pdf_path), pagesize=A4)
            width, height = A4

            img_width, img_height = img.size
            scale = min(width / img_width, height / img_height) * 0.9
            new_width = img_width * scale
            new_height = img_height * scale
            x = (width - new_width) / 2
            y = (height - new_height) / 2

            img_buffer = io.BytesIO()
            img.save(img_buffer, format="JPEG")
            img_buffer.seek(0)
            c.drawImage(ImageReader(img_buffer), x, y, new_width, new_height)
            c.showPage()
            c.save()

            print(f"  → Изображение → PDF: {file_path.name} → {pdf_path.name}")
            return pdf_path

    except FileNotFoundError as e:
        if 'libreoffice' in str(e):
            logger.error("libreoffice не установлен! Установите: sudo apt install libreoffice")
        else:
            logger.error(f"Файл не найден: {e}")
    except Exception as e:
        logger.error(f"Ошибка конвертации {file_path.name}: {e}")

    return None

# === ФУНКЦИИ ИЗВЛЕЧЕНИЯ ===
def detect_language(text):
    try:
        return detect(text) if text.strip() else 'en'
    except:
        return 'en'

def extract_text_pdf(pdf_path):
    pdf_bytes = read_fn(pdf_path)


    base_name = pdf_path.stem
    local_image_dir, _ = prepare_env(str(OUTPUT_DIR), base_name, "auto")

    pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes)
    infer_results, all_image_lists, all_pdf_docs, lang_list, ocr_list = doc_analyze(
        [pdf_bytes], [detect_language("")], parse_method="auto"
    )
    middle_json = result_to_middle_json(
        infer_results[0], all_image_lists[0], all_pdf_docs[0],
        FileBasedDataWriter(local_image_dir), lang_list[0], ocr_list[0], True
    )
    md_content = union_make(middle_json["pdf_info"], MakeMode.MM_MD, "images")
    return md_content.strip()

def extract_text_image(img_path):
    with tempfile.NamedTemporaryFile(suffix=img_path.suffix, delete=False) as tmp:
        tmp.write(img_path.read_bytes())
        tmp_path = tmp.name
    result = subprocess.run(
        ["tesseract", tmp_path, "stdout", "-l", "eng+rus"],
        capture_output=True, text=True
    )
    os.unlink(tmp_path)
    return result.stdout.strip()

def extract_text_docx(docx_path):
    import docx2txt
    return docx2txt.process(docx_path)

def extract_text_epub(epub_path):
    import ebooklib
    from bs4 import BeautifulSoup
    from ebooklib import epub
    book = epub.read_epub(str(epub_path))
    text = ""
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        text += soup.get_text() + "\n"
    return text

def extract_text_md(md_path):
    return md_path.read_text(encoding='utf-8')

def clean_with_ollama(raw_md):
    if not raw_md.strip():
        return raw_md
    try:
        start = time.time()
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {'role': 'system', 'content': CLEAN_PROMPT},
                {'role': 'user', 'content': raw_md[:MAX_LEN]}
            ],
            options={'timeout': TIMEOUT_SEC, 'temperature': TEMPERATUR}
        )
        logger.info(f"Ollama ответила за {time.time()-start:.1f}с")
        return response['message']['content']
    except Exception as e:
        logger.warning(f"Ollama не ответила: {e}. Используем сырой текст.")
        return raw_md


# === ОСНОВНОЙ ЦИКЛ ===
# === ОСНОВНОЙ ЦИКЛ (только изменённая часть) ===
def main():
    files = [
        f for f in INPUT_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXT and f.suffix.lower() not in SKIP_EXT
    ]
    if not files:
        print("Нет файлов для обработки.")
        return

    print(f"Найдено {len(files)} файлов для обработки:")
    for f in files:
        print(f"  • {f.name}")

    for file_path in files:
        base_name = file_path.stem
        raw_md_path = OUTPUT_DIR / f"{base_name}.raw.md"
        final_md_path = OUTPUT_DIR / f"{base_name}.md"

        if final_md_path.exists():
            print(f"Пропуск: {final_md_path} уже существует")
            continue

        print(f"\nОбработка: {file_path.name}")

        # === КОНВЕРТАЦИЯ В PDF ===
        ext = file_path.suffix.lower()
        pdf_path = None
        if ext != '.pdf':
            pdf_path = convert_to_pdf(file_path, INPUT_DIR)

        try:
            if pdf_path and pdf_path.exists():
                print(f"  → Используем PDF: {pdf_path.name}")
                raw_md = extract_text_pdf(pdf_path)
            elif ext == '.pdf':
                raw_md = extract_text_pdf(file_path)
            elif ext in {'.jpg', '.jpeg', '.png'}:
                raw_md = extract_text_image(file_path)
            elif ext == '.docx':
                raw_md = extract_text_docx(file_path)
            elif ext in {'.epub', '.html', '.htm'}:
                raw_md = extract_text_epub(file_path) if ext == '.epub' else file_path.read_text(encoding='utf-8')
            else:
                continue

            if not raw_md.strip():
                print("  → Пустой текст, пропуск")
                continue

            raw_md_path.write_text(raw_md, encoding='utf-8')
            print(f"  → Сырой MD: {raw_md_path}")

            cleaned_md = clean_with_ollama(raw_md)
            final_md_path.write_text(cleaned_md, encoding='utf-8')
            print(f"  → Очищенный MD: {final_md_path}")

        except Exception as e:
            logger.error(f"Ошибка при обработке {file_path.name}: {e}")

    print("\nГотово! Все файлы обработаны.")

if __name__ == "__main__":
    main()