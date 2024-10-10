import asyncio
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import subprocess
import os
import json

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Отправь CSV-файл для оценки ответов на сценарии.")

# Обработчик текстовых сообщений от пользователя
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    # Запускаем сценарий для обработки текста
    scenario_result = run_scenario(user_text)

    # Отправляем результат обратно пользователю
    await update.message.reply_text(scenario_result)
# Function to parse JSON and generate a formatted text report
def generate_text_report(json_file_path):
    try:
        with open(json_file_path, 'r') as json_file:
            data = json.load(json_file)
        
        # Initialize an empty list to store each test's report
        report_lines = []
        
        # Loop through each scenario and generate a summary
        for idx, scenario in enumerate(data, start=1):
            report_lines.append(f"Test {idx}:")
            for key, value in scenario.get('Evaluation', {}).items():
                report_lines.append(f"    {key}: {value}")
            report_lines.append(f"Overall score: {scenario.get('Overall score')}")
            report_lines.append(f"Feedback: {scenario.get('Feedback', '')}")
            report_lines.append("")  # Blank line for separation between tests
        
        # Join the report into a single string
        return "\n".join(report_lines)

    except Exception as e:
        return f"Error generating report: {e}"
# Обработчик для получения файла (например, CSV)
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    file = await context.bot.get_file(document.file_id)

    # Скачиваем файл во временную директорию
    temp_file_path = f'/tmp/{document.file_id}.csv'
    await file.download_to_drive(temp_file_path)

    # Запускаем сценарий для обработки файла
    scenario_result = run_scenario_with_file(temp_file_path)

    if os.path.exists(scenario_result):
        # Send JSON file to the user
        with open(scenario_result, 'rb') as output_file:
            await update.message.reply_document(
                document=InputFile(output_file),
                caption="Вот результаты после обработки файла."
            )

        # Generate and send formatted text report
        text_report = generate_text_report(scenario_result)
        await update.message.reply_text(text_report)

        # Удаляем временные файлы
        os.remove(temp_file_path)
        os.remove(scenario_result)

        # Удаляем ai_responses.csv из директории сценария
        ai_responses_path = os.path.join(os.path.dirname(scenario_result), 'ai_responses.csv')
        if os.path.exists(ai_responses_path):
            os.remove(ai_responses_path)
    else:
        await update.message.reply_text(f"Произошла ошибка при обработке файла: {scenario_result}")

# Функция для запуска сценария с текстом
def run_scenario(user_input):
    try:
        # Используем Python из виртуального окружения
        result = subprocess.run(
            ['/root/telegram_bot/venv/bin/python3', '/root/telegram_bot/scenarios/scenario_script.py', user_input],
            capture_output=True,
            text=True
        )
        return result.stdout.strip()
    except Exception as e:
        return f"Произошла ошибка при выполнении сценария: {e}"

# Функция для запуска сценария с файлом
def run_scenario_with_file(file_path):
    try:
        # Используем Python из виртуального окружения
        result = subprocess.run(
            ['/root/telegram_bot/venv/bin/python3', '/root/telegram_bot/scenarios/scenario_script.py', file_path],
            capture_output=True,
            text=True
        )
        # Предполагаем, что сценарий создаёт 'evaluated_responses.json' в директории скрипта
        script_dir = os.path.dirname('/root/telegram_bot/scenarios/scenario_script.py')
        output_file_path = os.path.join(script_dir, 'evaluated_responses.json')
        if os.path.exists(output_file_path):
            return output_file_path
        else:
            return result.stderr.strip()
    except Exception as e:
        return f"Произошла ошибка при выполнении сценария: {e}"

# Основная функция для запуска бота (асинхронная)
def main():
    # Создаем экземпляр приложения с токеном Telegram бота
    app = Application.builder().token('token').build()

    # Добавляем обработчики для команды /start и текстовых сообщений
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.FileExtension('csv'), handle_file))

    # Запускаем бота
    app.run_polling()

# Запуск бота
if __name__ == '__main__':
    main()
