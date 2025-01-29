# model_test.py
import os
import json
import csv
import time
import requests
import openai
from dotenv import load_dotenv
from openai.error import Timeout as OpenAITimeout

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

openai.api_key = OPENAI_API_KEY

def load_prompts(prompts_file="prompts.json"):
    """Загружает сценарии (prompt'ы) из prompts.json."""
    with open(prompts_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["prompts"]

def generate_response_openai(prompt, model="gpt-3.5-turbo", max_retries=3, request_timeout=180):
    """
    Генерация ответа с помощью OpenAI ChatCompletion.
    Пытаемся запросить logprobs=True (может работать только на 0.27-0.28 openai).
    Делает несколько попыток при Timeout.
    """
    for attempt in range(1, max_retries+1):
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=500,
                n=1,
                logprobs=True,          # Пытаемся запросить логпробы
                request_timeout=request_timeout
            )
            # Парсим ответ
            text_output = response["choices"][0]["message"]["content"].strip()

            logprobs_data = response["choices"][0].get("logprobs", {})
            tokens = logprobs_data.get("tokens", [])
            token_logprobs = logprobs_data.get("token_logprobs", [])

            return text_output, tokens, token_logprobs
        except OpenAITimeout:
            print(f"[OpenAI] Timeout на попытке {attempt}. Ждём и повторяем...")
            if attempt < max_retries:
                time.sleep(5)
            else:
                # Последняя попытка провалилась, вернём пустые
                return "Error: OpenAI Timeout", [], []
        except Exception as e:
            print(f"[OpenAI] Ошибка: {e}")
            # Другие ошибки (например, RateLimitError) можно отдельно обрабатывать
            return f"Error: {str(e)}", [], []

def generate_response_huggingface_api(prompt, model_name, max_retries=3):
    """
    Генерация ответа через Hugging Face Inference API с retry.
    Возвращаем (ai_response, success_flag).
    """
    api_url = f"https://api-inference.huggingface.co/models/{model_name}"
    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"inputs": prompt}

    for attempt in range(1, max_retries+1):
        response = requests.post(api_url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0 and "generated_text" in data[0]:
                return data[0]["generated_text"], True
            else:
                return str(data), True
        else:
            print(f"[HF] Attempt {attempt} failed: {response.status_code} - {response.text}")
            if attempt < max_retries:
                time.sleep(5)
            else:
                return "", False

def generate_and_save_responses(service, model):
    """
    1) Загружает промпты из prompts.json.
    2) Для каждого промпта получает ответ модели (OpenAI / Hugging Face).
    3) Сохраняет (Prompt, AI_Response, Tokens, LogProbs) в responses.csv.
    4) Возвращает путь к CSV.
    """
    prompts = load_prompts()  # предполагаем, что prompts.json лежит рядом
    csv_file_path = "responses.csv"

    with open(csv_file_path, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Prompt", "AI_Response", "Tokens", "LogProbs"])

        for prompt in prompts:
            if service == "openai":
                ai_response, tokens, logprobs = generate_response_openai(prompt, model)
                writer.writerow([
                    prompt,
                    ai_response,
                    json.dumps(tokens, ensure_ascii=False),
                    json.dumps(logprobs, ensure_ascii=False)
                ])
            else:
                ai_response, success = generate_response_huggingface_api(prompt, model)
                if success and ai_response:
                    writer.writerow([
                        prompt,
                        ai_response,
                        json.dumps([], ensure_ascii=False),
                        json.dumps([], ensure_ascii=False)
                    ])
                else:
                    # Если даже после retries нет результата, пропускаем запись
                    print(f"[HF] No valid response for prompt:\n{prompt}")

    return csv_file_path


