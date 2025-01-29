# bot.py
import os
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from dotenv import load_dotenv

from model_test import generate_and_save_responses
from evaluator import evaluate_responses, create_summary

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Пример списков моделей:
OPENAI_MODELS = ["gpt-4o-mini", "gpt-3.5-turbo"]
HUGGINGFACE_MODELS = ["tiiuae/falcon-7b-instruct"]

user_selection = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    keyboard = [["OpenAI", "HuggingFace"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text(
        "Привет! Выберите сервис ИИ для тестирования:",
        reply_markup=reply_markup
    )

async def choose_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    service = update.message.text.strip().lower()

    if service == "openai":
        user_selection[user_id] = {"service": "openai"}
        keyboard = [[m] for m in OPENAI_MODELS]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        await update.message.reply_text("Выберите модель OpenAI:", reply_markup=reply_markup)
    elif service == "huggingface":
        user_selection[user_id] = {"service": "huggingface"}
        keyboard = [[m] for m in HUGGINGFACE_MODELS]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        await update.message.reply_text("Выберите модель HuggingFace:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Пожалуйста, выберите корректный сервис (OpenAI или HuggingFace).")

async def choose_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chosen_model = update.message.text.strip()

    if user_id not in user_selection:
        await update.message.reply_text("Сначала введите /start и выберите сервис.")
        return

    service = user_selection[user_id]["service"]
    valid_models = OPENAI_MODELS if service == "openai" else HUGGINGFACE_MODELS

    if chosen_model not in valid_models:
        await update.message.reply_text("Выбрана некорректная модель. Попробуйте ещё раз.")
        return

    user_selection[user_id]["model"] = chosen_model
    await update.message.reply_text(f"Вы выбрали {service} и модель {chosen_model}. Начинаем тестирование...")

    # Генерируем ответы (CSV)
    csv_file_path = generate_and_save_responses(service, chosen_model)

    # Оцениваем ответы (JSON)
    evaluation_file = evaluate_responses(csv_file_path)

    # Формируем краткий вывод
    summary_text = create_summary(evaluation_file)

    # Отправляем результат
    with open(evaluation_file, "rb") as f:
        await update.message.reply_text("Вот JSON-файл с результатами оценки:")
        await update.message.reply_document(document=f)

    await update.message.reply_text(f"Краткий обзор:\n{summary_text}")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("(?i)^(OpenAI|HuggingFace)$"), choose_service))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Regex("(?i)^(OpenAI|HuggingFace)$"),
        choose_model
    ))

    app.run_polling()

if __name__ == "__main__":
    main()

