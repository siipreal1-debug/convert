import os
from pathlib import Path
from dotenv import load_dotenv
import ollama
import json
from loguru import logger
from mineru.cli.common import convert_pdf_bytes_to_bytes_by_pypdfium2, prepare_env, read_fn
from mineru.data.data_reader_writer import FileBasedDataWriter
from mineru.utils.enum_class import MakeMode
from mineru.backend.pipeline.pipeline_analyze import doc_analyze as pipeline_doc_analyze
from mineru.backend.pipeline.pipeline_middle_json_mkcontent import union_make as pipeline_union_make
from mineru.backend.pipeline.model_json_to_middle_json import result_to_middle_json as pipeline_result_to_middle_json
import pypdfium2 as pypdfium
from langdetect import detect

def detect_pdf_language(pdf_bytes):
    """Определяет язык текста в PDF."""
    try:
        pdf = pypdfium.PdfDocument(pdf_bytes)
        text = ""
        for i in range(len(pdf)):
            page = pdf[i]
            textpage = page.get_textpage()
            text += textpage.get_text_range() or ""
            textpage.close()
            page.close()
        pdf.close()
        if text.strip():
            lang = detect(text)
            lang_map = {
                'en': 'en', 'zh-cn': 'ch', 'zh-tw': 'ch', 'fr': 'fr', 'de': 'de',
                'es': 'es', 'ru': 'ru', 'ja': 'ja', 'ko': 'ko', 'it': 'it'
            }
            return lang_map.get(lang, 'en')
        return 'en'
    except Exception as e:
        logger.warning(f"Ошибка при определении языка: {str(e)}. Используется английский по умолчанию.")
        return 'en'

def do_parse(
    output_dir,
    pdf_file_names: list[str],
    pdf_bytes_list: list[bytes],
    p_lang_list: list[str],
    backend="pipeline",
    parse_method="auto",
    formula_enable=True,
    table_enable=True,
    f_dump_md=True,
    f_make_md_mode=MakeMode.MM_MD,
    start_page_id=0,
    end_page_id=None,
):
    if backend == "pipeline":
        for idx, pdf_bytes in enumerate(pdf_bytes_list):
            new_pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, start_page_id, end_page_id)
            pdf_bytes_list[idx] = new_pdf_bytes

        try:
            logger.info("Начало анализа PDF с MinerU")
            infer_results, all_image_lists, all_pdf_docs, lang_list, ocr_enabled_list = pipeline_doc_analyze(
                pdf_bytes_list, p_lang_list, parse_method=parse_method, formula_enable=formula_enable, table_enable=table_enable
            )
        except Exception as e:
            logger.error(f"Ошибка при анализе PDF: {str(e)}")
            raise

        for idx, model_list in enumerate(infer_results):
            pdf_file_name = pdf_file_names[idx]
            local_image_dir, _ = prepare_env(output_dir, pdf_file_name, parse_method)  # Только для изображений
            local_md_dir = output_dir  # Markdown сохраняется в корне output
            image_writer, md_writer = FileBasedDataWriter(local_image_dir), FileBasedDataWriter(local_md_dir)

            images_list = all_image_lists[idx]
            pdf_doc = all_pdf_docs[idx]
            _lang = lang_list[idx]
            _ocr_enable = ocr_enabled_list[idx]
            try:
                middle_json = pipeline_result_to_middle_json(model_list, images_list, pdf_doc, image_writer, _lang, _ocr_enable, formula_enable)
                logger.info(f"Содержимое middle_json для {pdf_file_name}: {json.dumps(middle_json, indent=2, ensure_ascii=False)[:200]}...")
                pdf_info = middle_json["pdf_info"]
                pdf_bytes = pdf_bytes_list[idx]
                return _process_output(
                    pdf_info, pdf_bytes, pdf_file_name, local_md_dir, local_image_dir,
                    md_writer, f_dump_md, f_make_md_mode, middle_json
                )
            except Exception as e:
                logger.error(f"Ошибка при обработке результатов для {pdf_file_name}: {str(e)}")
                raise

def _process_output(
        pdf_info,
        pdf_bytes,
        pdf_file_name,
        local_md_dir,
        local_image_dir,
        md_writer,
        f_dump_md,
        f_make_md_mode,
        middle_json,
):
    if f_dump_md:
        try:
            md_content_str = pipeline_union_make(pdf_info, f_make_md_mode, str(os.path.basename(local_image_dir)))
            logger.info(f"Содержимое сырого Markdown для {pdf_file_name}: {md_content_str[:100]}...")
            if md_content_str.strip():
                raw_md_path = os.path.join(local_md_dir, f"{pdf_file_name}.raw.md")
                md_writer.write_string(f"{pdf_file_name}.raw.md", md_content_str)
                logger.info(f"Сырой Markdown сохранён в {raw_md_path}")
                return md_content_str
            else:
                logger.warning(f"Сырой Markdown для {pdf_file_name} пустой, файл не создан")
                return None
        except Exception as e:
            logger.error(f"Ошибка при создании сырого Markdown для {pdf_file_name}: {str(e)}")
            raise
    logger.info(f"Локальная выходная директория: {local_md_dir}")
    return None

print("Этап 1: Загрузка переменных окружения из .env")
load_dotenv()

pdf_path = os.getenv('PDF_PATH')
if not pdf_path:
    raise ValueError("PDF_PATH не указан в .env")
print(f"Этап 2: Путь к PDF-файлу: {pdf_path}")

base_name = os.path.splitext(os.path.basename(pdf_path))[0]
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)
print(f"Этап 3: Создание выходной директории: {output_dir}")

print("Этап 4: Чтение PDF-файла")
pdf_bytes = read_fn(Path(pdf_path))

print("Этап 5: Определение языка PDF")
lang = detect_pdf_language(pdf_bytes)
print(f"  - Определён язык: {lang}")

print("Этап 6: Конвертация PDF в сырой Markdown с помощью MinerU")
file_name_list = [base_name]
pdf_bytes_list = [pdf_bytes]
lang_list = [lang]
try:
    raw_md = do_parse(
        output_dir=output_dir,
        pdf_file_names=file_name_list,
        pdf_bytes_list=pdf_bytes_list,
        p_lang_list=lang_list,
        backend="pipeline",
        parse_method="auto",
        formula_enable=True,
        table_enable=True,
        f_dump_md=True,
        f_make_md_mode=MakeMode.MM_MD
    )
except Exception as e:
    logger.error(f"Ошибка при обработке PDF: {str(e)}")
    raise

raw_md_path = os.path.join(output_dir, f"{base_name}.raw.md")
print(f"Этап 7: Чтение сырого Markdown из {raw_md_path}")
if not raw_md:
    logger.error(f"Сырой Markdown пустой для {base_name}. Проверьте содержимое PDF.")
    raise ValueError(f"Сырой Markdown пустой для {base_name}")
if not os.path.exists(raw_md_path):
    logger.error(f"Файл {raw_md_path} не найден. Проверьте содержимое output/example/auto/ или output/example/md/")
    raise FileNotFoundError(f"Файл {raw_md_path} не найден")
with open(raw_md_path, 'r', encoding='utf-8') as f:
    raw_md = f.read()

print("Этап 8: Сохранение сырого Markdown во временный файл raw.md")
with open('raw.md', 'w', encoding='utf-8') as f:
    f.write(raw_md)

print("Этап 9: Загрузка промта для очистки из .env")
prompt = os.getenv('CLEAN_PROMPT')
if not prompt:
    print("  - Промт не найден, сохранение дефолтного промта в .env")
    prompt = """
    Очистите следующий текст Markdown, полученный из конвертации PDF:
    - Удалите номера страниц.
    - Исправьте разрывы строк и слов (например, слова с дефисами на разрывах).
    - Удалите дублирующиеся строки.
    - Удалите артефакты, такие как повторяющиеся заголовки/колонтитулы.
    - Заполните повреждённые слова или удалите их, если это мусор.
    - Сохраните оригинальный язык документа.
    - Выведите только очищенный Markdown.
    """
    with open('.env', 'a', encoding='utf-8') as env_file:
        env_file.write(f'\nCLEAN_PROMPT="{prompt}"')

print("Этап 10: Очистка Markdown с помощью Ollama")
response = ollama.chat(model='phi3.5:3.8b-mini-instruct-q4_K_M', messages=[
    {
        'role': 'system',
        'content': prompt,
    },
    {
        'role': 'user',
        'content': raw_md,
    },
])
cleaned_md = response['message']['content']

print(f"Этап 11: Сохранение очищенного Markdown в {os.path.join(output_dir, f'{base_name}.md')}")
md_writer = FileBasedDataWriter(output_dir)
md_writer.write_string(f"{base_name}.md", cleaned_md)

print("Этап 12: Удаление временного файла raw.md")
os.remove('raw.md')

print(f"Программа завершена. Очищенный Markdown сохранён в {os.path.join(output_dir, f'{base_name}.md')}. Сырой Markdown сохранён в {raw_md_path}")