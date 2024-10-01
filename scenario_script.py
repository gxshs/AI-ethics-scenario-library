import os
import openai
from openai.error import InvalidRequestError, RateLimitError, APIError
import csv
import json
import time
import sys

# Определение директории скрипта
script_dir = os.path.dirname(os.path.abspath(__file__))

# Установка API-ключа OpenAI из переменных окружения для безопасности
openai.api_key = os.getenv("OPENAI_API_KEY", "api key")

# Отладочные сообщения
print("DEBUG: Начало скрипта")
print(f"DEBUG: OPENAI_API_KEY = {openai.api_key}")

# Чтение детальных инструкций из файла
detailed_instruction_path = os.path.join(script_dir, 'detailed_instruction.txt')
if not os.path.exists(detailed_instruction_path):
    print(f"DEBUG: Файл {detailed_instruction_path} не найден.")
    sys.exit(1)

with open(detailed_instruction_path, 'r', encoding='utf-8') as f:
    detailed_instruction = f.read()

# Проверка аргументов командной строки
if len(sys.argv) < 2:
    print("DEBUG: Не указан путь к CSV-файлу.")
    sys.exit(1)

csv_file_path = sys.argv[1]

# Проверка существования файла
if not os.path.exists(csv_file_path):
    print(f"DEBUG: Файл {csv_file_path} не найден.")
    sys.exit(1)

# Чтение Prompts из CSV-файла
with open(csv_file_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    prompts = [row['Prompt'] for row in reader]

# Очищаем или создаём файл ai_responses.csv
ai_responses_path = os.path.join(script_dir, 'ai_responses.csv')
with open(ai_responses_path, 'w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(["Prompt", "Full Response"])  # Записываем заголовки

# Очищаем файл evaluated_responses.json
evaluated_responses_path = os.path.join(script_dir, 'evaluated_responses.json')
with open(evaluated_responses_path, 'w', encoding='utf-8') as outfile:
    outfile.write('')  # Просто создаём или очищаем файл

# Функция для получения AI-ответа
def get_ai_response(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": detailed_instruction},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0
        )
        ai_response = response['choices'][0]['message']['content'].strip()
        return ai_response
    except Exception as e:
        print(f"DEBUG: Ошибка при получении ответа от OpenAI: {e}")
        return "Не удалось получить ответ от ИИ."

# Функция для выполнения оценки
def make_evaluation_api_request(content, detailed_instruction, retries=3, initial_delay=10):
    for attempt in range(retries):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": detailed_instruction},
                    {"role": "user", "content": content}
                ],
                max_tokens=1500,
                temperature=0,
                n=1
            )
            evaluation_content = response['choices'][0]['message']['content'].strip()
            return evaluation_content
        except InvalidRequestError as e:
            print(f"DEBUG: Ошибка запроса: {e}")
            return None
        except RateLimitError:
            print(f"DEBUG: Превышен лимит запросов, повторная попытка... (Попытка {attempt + 1}/{retries})")
            time.sleep(initial_delay * (2 ** attempt))
        except APIError as e:
            print(f"DEBUG: API ошибка: {e}, повторная попытка... (Попытка {attempt + 1}/{retries})")
            time.sleep(initial_delay * (2 ** attempt))
    print("DEBUG: Постоянное превышение лимита запросов.")
    time.sleep(900)  # Пауза на 15 минут
    return None

evaluations = []

# Обработка каждой подсказки
for i, prompt in enumerate(prompts, start=1):
    print(f"DEBUG: Обработка подсказки {i}/{len(prompts)}")
    
    # Получение ai_response из OpenAI
    ai_response = get_ai_response(prompt)
    
    # Запись в ai_responses.csv
    with open(ai_responses_path, 'a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow([prompt, ai_response])

    # Подготовка контента для оценки
    content_for_evaluation = f"Scenario: {prompt}\nResponse: {ai_response}"

    # Выполнение оценки
    evaluation = make_evaluation_api_request(content_for_evaluation, detailed_instruction)

    if evaluation:
        evaluations.append({
            'Scenario': prompt,
            'AI Response': ai_response,
            'Evaluation': evaluation
        })
    else:
        evaluations.append({
            'Scenario': prompt,
            'AI Response': ai_response,
            'Evaluation': 'Не удалось получить оценку.'
        })
    time.sleep(1)  # Задержка для соблюдения лимитов

# Сохранение результатов в evaluated_responses.json
with open(evaluated_responses_path, 'w', encoding='utf-8') as json_file:
    json.dump(evaluations, json_file, ensure_ascii=False, indent=4)

print("DEBUG: Оценка завершена. Результаты сохранены в 'evaluated_responses.json'.")
