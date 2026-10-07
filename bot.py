import logging
import os
from typing import Dict

from openai import OpenAI
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable.")

if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY environment variable.")

client = OpenAI(api_key=OPENAI_API_KEY)
previous_response_ids: Dict[int, str] = {}

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("optavik-ai")

SYSTEM_INSTRUCTIONS = """
You are Optavik AI, the customer assistant for OPTAVIKCHINA.

Your job:
- Help customers understand that OPTAVIKCHINA sources products from China.
- Answer clearly and professionally in the customer's language.
- Be friendly, concise, and business-focused.
- Ask for missing details when a product request is incomplete.
- Never invent a product price, stock quantity, delivery time, supplier, or specification.
- If you do not have verified information, say that the information needs to be checked.
- Do not claim that an order, payment, purchase, or shipment has been completed unless the system explicitly confirms it.
- For a product request, try to collect: product/model, quantity, preferred version/specification, destination city/country, and any important requirements.
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user:
        previous_response_ids.pop(user.id, None)

    if update.message:
        await update.message.reply_text(
            "👋 Здравствуйте! Я Optavik AI — помощник OPTAVIKCHINA 🇨🇳\n\n"
            "Помогу разобраться с товарами из Китая, оптовыми запросами и заявками.\n\n"
            "Напишите, что вам нужно. Например:\n"
            "📱 POCO C85, 20 шт\n"
            "👕 Мужские свитшоты, 50 шт\n"
            "📦 Нужно найти товар с доставкой в Душанбе"
        )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user:
        previous_response_ids.pop(user.id, None)

    if update.message:
        await update.message.reply_text("♻️ Диалог сброшен. Напишите ваш новый запрос.")


async def handle_private_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    if not user:
        return

    user_text = update.message.text.strip()
    if not user_text:
        return

    try:
        await update.message.chat.send_action("typing")

        request_kwargs = {
            "model": OPENAI_MODEL,
            "instructions": SYSTEM_INSTRUCTIONS,
            "input": user_text,
        }

        previous_id = previous_response_ids.get(user.id)
        if previous_id:
            request_kwargs["previous_response_id"] = previous_id

        response = client.responses.create(**request_kwargs)
        answer = (response.output_text or "").strip()

        if not answer:
            answer = "Извините, я не смог сформировать ответ. Попробуйте ещё раз."

        previous_response_ids[user.id] = response.id
        await update.message.reply_text(answer)

    except Exception:
        logger.exception("OpenAI request failed")
        await update.message.reply_text(
            "⚠️ Произошла техническая ошибка. Попробуйте ещё раз через несколько секунд."
        )


async def handle_channel_post(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    message = update.channel_post
    if not message:
        return

    post_text = message.text or message.caption or "[non-text post]"
    logger.info(
        "CHANNEL POST received | chat_id=%s | message_id=%s | text=%s",
        message.chat.id,
        message.message_id,
        post_text[:1000],
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled Telegram error", exc_info=context.error)


def main() -> None:
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset))

    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
            handle_private_message,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.UpdateType.CHANNEL_POSTS,
            handle_channel_post,
        )
    )

    application.add_error_handler(error_handler)

    logger.info("Optavik AI is starting...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
