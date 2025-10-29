#!/usr/bin/env python3.11

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import ollama
from loguru import logger
import time

# === КОНФИГУРАЦИЯ ===
OUTPUT_DIR = Path("output")
CLEAN_PROMPT = None
TIMEOUT_SEC = 600
MAX_LEN = 32000
TEMPERATUR = 0.05

# === СЛОВАРЬ МОДЕЛЕЙ (измени под себя) ===
MODELS = {
    "qwen2.5:0.5b-instruct"         :  "qwen2.5:0.5b-instruct",
    "phi3.5"                        :  "phi3.5:3.8b-mini-instruct-q4_K_M",
    "deepseekr1:1.5b"               :  "deepseek-r1:1.5b",
    "qwen2.5:1.5b-instruct-q4_K_M"  :  "qwen2.5:1.5b-instruct-q4_K_M",
    "deepseek-7b"                   :  "deepseek-r1:7b-qwen-distill-q4_K_M",
    "qwen2.5:0.5b-instruct-q4_K_M"  :  "qwen2.5:0.5b-instruct-q4_K_M",
    "qwen3:0.6b"                    :  "qwen3:0.6b",
    "qwen3"                         :  "qwen3:4b"
}



# === СПИСОК ТЕМПЕРАТУР (от 0.0 до 2.0 с шагом 0.2) ===
TEMPERATURES = [round(i * 0.2, 2) for i in range(11)]  # [0.0, 0.2, ..., 2.0]

# === ИНИЦИАЛИЗАЦИЯ ===
load_dotenv()
logger.remove()
logger.add(sys.stderr, level="INFO")

CLEAN_PROMPT = os.getenv('CLEAN_PROMPT')
if not CLEAN_PROMPT:
    logger.error("CLEAN_PROMPT не задан в .env!")
    sys.exit(1)

# === ФУНКЦИЯ ОЧИСТКИ ===
def clean_with_model(text: str, model: str, temp: float) -> str:
    if not text.strip():
        return text
    try:
        start = time.time()
        response = ollama.chat(
            model=model,
            messages=[
                {'role': 'system', 'content': CLEAN_PROMPT},
                {'role': 'user', 'content': text[:MAX_LEN]}
            ],
            options={'timeout': TIMEOUT_SEC, 'temperature': temp}
        )
        elapsed = time.time() - start
        logger.info(f"[{model} | t{int(temp*100):03d}] Ответ за {elapsed:.1f}с")
        return response['message']['content']
    except Exception as e:
        logger.error(f"[{model} | t{int(temp*100):03d}] Ошибка: {e}")
        return text  # fallback

# === ОСНОВНОЙ ЦИКЛ ===
def main():
    raw_files = list(OUTPUT_DIR.glob("*.raw.md"))
    if not raw_files:
        print("Нет .raw.md файлов в output/")
        return

    print(f"Найдено {len(raw_files)} .raw.md файлов")
    print(f"Модели: {', '.join(MODELS.keys())}")
    print(f"Температуры: {[f'{t:.1f}' for t in TEMPERATURES]}")

    for raw_path in raw_files:
        print(f"\nОбработка: {raw_path.name}")
        raw_text = raw_path.read_text(encoding='utf-8')

        # Базовое имя без .raw.md
        base_name = raw_path.stem  # например: document

        for model_key, model_name in MODELS.items():
            model_dir = OUTPUT_DIR / model_key
            model_dir.mkdir(exist_ok=True)

            for temp in TEMPERATURES:
                temp_str = f"t{int(temp * 100):03d}"  # t000, t020, t100, t200
                result_filename = f"{base_name}.{temp_str}.md"
                result_path = model_dir / result_filename

                if result_path.exists():
                    print(f"  → Пропуск: {model_key}/{result_filename}")
                    continue

                print(f"  → {model_key} | {temp_str} → {result_filename}")
                cleaned = clean_with_model(raw_text, model_name, temp)
                result_path.write_text(cleaned, encoding='utf-8')

    print("\nГотово! Результаты в output/<модель>/<файл>.tXXX.md")

if __name__ == "__main__":
    main()