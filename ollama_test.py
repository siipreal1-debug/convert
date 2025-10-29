#!/usr/bin/env python3.11

import ollama
import time
import sys

# === НАСТРОЙКИ ===
MODEL = "phi3.5:3.8b-mini-instruct-q4_K_M"  # или qwen2.5:0.5b-instruct-q4_K_M
TIMEOUT = 60  # секунд
TEST_TEXT = "# Dummy PDF file"

# === ТЕСТ ===
def test_ollama():
    print(f"Тестирую Ollama: модель '{MODEL}'")
    print(f"Вход: {TEST_TEXT}")
    print(f"Таймаут: {TIMEOUT} сек")
    print("-" * 50)

    start = time.time()
    try:
        response = ollama.chat(
            model=MODEL,
            messages=[
                {'role': 'system', 'content': 'Ответь кратко. Только очищенный текст.'},
                {'role': 'user', 'content': TEST_TEXT}
            ],
            options={'timeout': TIMEOUT}
        )
        result = response['message']['content']
        duration = time.time() - start
        print(f"УСПЕХ! Ответ за {duration:.1f} сек:")
        print("-" * 50)
        print(result.strip())
        print("-" * 50)
        return True

    except Exception as e:
        duration = time.time() - start
        print(f"ОШИБКА за {duration:.1f} сек: {e}")
        if "timeout" in str(e).lower():
            print("Совет: Ollama думает слишком долго. Попробуй меньшую модель:")
            print("  ollama run qwen2.5:0.5b-instruct-q4_K_M")
        return False

# === ЗАПУСК ===
if __name__ == "__main__":
    if not test_ollama():
        sys.exit(1)