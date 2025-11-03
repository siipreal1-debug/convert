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
TIMEOUT_SEC = 3000
MAX_LEN = 32000

# === МОДЕЛИ ===
MODELS = {
    "qwen2.5:0.5b-instruct"         :  "qwen2.5:0.5b-instruct",
    "phi3.5"                        :  "phi3.5:3.8b-mini-instruct-q4_K_M",
    "deepseekr1:1.5b"               :  "deepseek-r1:1.5b",
    "qwen2.5:1.5b-instruct-q4_K_M"  :  "qwen2.5:1.5b-instruct-q4_K_M",
    "qwen2.5:0.5b-instruct-q4_K_M"  :  "qwen2.5:0.5b-instruct-q4_K_M",
    "qwen3:0.6b"                    :  "qwen3:0.6b",
    "qwen3"                         :  "qwen3:4b",
    "deepseek-7b"                   :  "deepseek-r1:7b-qwen-distill-q4_K_M"
}

# === ТЕМПЕРАТУРЫ ===
TEMPERATURES = [round(i * 0.5, 2) for i in range(5)]

# === ИНИЦИАЛИЗАЦИЯ ===
load_dotenv()
logger.remove()
logger.add(sys.stderr, level="INFO")

CLEAN_PROMPT = os.getenv('CLEAN_PROMPT')
if not CLEAN_PROMPT:
    logger.error("CLEAN_PROMPT не задан в .env!")
    sys.exit(1)

# === ОЧИСТКА ===
def clean_with_model(text: str, model: str, temp: float, result_path: Path) -> None:
    if result_path.exists():
        return

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
        logger.info(f"      t{int(temp*100):03d} → {elapsed:.1f}s")
        result_path.write_text(response['message']['content'], encoding='utf-8')
    except Exception as e:
        logger.error(f"      t{int(temp*100):03d} → Ошибка: {e}")

# === ГЛАВНЫЙ ЦИКЛ: МОДЕЛЬ → ФАЙЛ → ТЕМПЕРАТУРА ===
def main():
    raw_files = sorted(OUTPUT_DIR.glob("*.raw.md"))
    if not raw_files:
        print("Нет .raw.md файлов в output/")
        return

    print(f"Найдено {len(raw_files)} .raw.md файлов")
    print(f"Модели: {', '.join(MODELS.keys())}")
    print(f"Температуры: {[f'{t:.1f}' for t in TEMPERATURES]}")
    print("Оптимизация: [модель → файл → температура] → 1 загрузка модели\n")

    # === 1. ВНЕШНИЙ ЦИКЛ: МОДЕЛЬ (загружается 1 раз) ===
    for model_key, model_name in MODELS.items():
        print(f"\nЗагрузка модели: {model_key} ({model_name})")
        model_dir = OUTPUT_DIR / model_key
        model_dir.mkdir(exist_ok=True)

        # === 2. ФАЙЛЫ ===
        for raw_path in raw_files:
            print(f"  Обработка: {raw_path.name}")
            raw_text = raw_path.read_text(encoding='utf-8')
            base_name = raw_path.stem

            # === 3. ТЕМПЕРАТУРЫ ===
            for temp in TEMPERATURES:
                temp_str = f"t{int(temp * 100):03d}"
                result_path = model_dir / f"{base_name}.{temp_str}.md"

                if result_path.exists():
                    print(f"      → Пропуск: {result_path.name}")
                    continue

                print(f"      → {temp_str}")
                clean_with_model(raw_text, model_name, temp, result_path)

    print("\nГотово! Все модели обработаны с минимальной перезагрузкой.")

if __name__ == "__main__":
    main()
