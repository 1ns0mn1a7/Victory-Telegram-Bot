import logging
import random
import redis
from enum import Enum, auto
from environs import Env
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
)

from fetch_quiz import load_quiz, normalize_answer


class States(Enum):
    WAITING_ANSWER = auto()


def build_keyboard():
    return ReplyKeyboardMarkup([["Новый вопрос", "Сдаться"], ["Мой счёт"]], resize_keyboard=True)


def start(update: Update, context: CallbackContext):
    update.message.reply_text("Привет! Я бот для викторин 👋", reply_markup=build_keyboard())


def help_command(update: Update, context: CallbackContext):
    update.message.reply_text("Доступные действия: «Новый вопрос», «Сдаться», «Мой счёт». /cancel — убрать клавиатуру.")


def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("Клавиатура скрыта. Введите /start, чтобы вернуть её.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def handle_new_question_request(update: Update, context: CallbackContext):
    db: redis.Redis = context.bot_data["db"]
    questions = context.bot_data["questions"]
    user_id = update.effective_user.id

    if not questions:
        update.message.reply_text("Вопросов нет 🙈")
        return ConversationHandler.END

    question, answer = random.choice(questions)
    db.set(f"quiz:{user_id}:q", question)
    db.set(f"quiz:{user_id}:a", answer)

    update.message.reply_text(f"Вопрос:\n\n{question}", reply_markup=build_keyboard())
    return States.WAITING_ANSWER


def handle_give_up(update: Update, context: CallbackContext):
    db: redis.Redis = context.bot_data["db"]
    questions = context.bot_data["questions"]
    user_id = update.effective_user.id
    
    answer = db.get(f"quiz:{user_id}:a")
    if not answer:
        update.message.reply_text("Сначала нажмите «Новый вопрос».", reply_markup=build_keyboard())
        return States.WAITING_ANSWER
    
    update.message.reply_text(f"Правильный ответ:\n\n{answer}", reply_markup=build_keyboard())
    question_next, answer_next = random.choice(questions)
    
    db.set(f"quiz:{user_id}:q", question_next)
    db.set(f"quiz:{user_id}:a", answer_next)
    
    update.message.reply_text(f"Следующий вопрос:\n\n{question_next}", reply_markup=build_keyboard())
    
    return States.WAITING_ANSWER


def handle_solution_attempt(update: Update, context: CallbackContext):
    db: redis.Redis = context.bot_data["db"]
    user_id = update.effective_user.id

    correct = db.get(f"quiz:{user_id}:a")
    if not correct:
        update.message.reply_text("Нажмите «Новый вопрос», чтобы начать.", reply_markup=build_keyboard())
        return States.WAITING_ANSWER

    user_answer = normalize_answer(update.message.text or "")
    true_answer = normalize_answer(correct)

    if user_answer == true_answer:
        db.incr(f"score:{user_id}")
        update.message.reply_text("Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»",
                                  reply_markup=build_keyboard())
        db.delete(f"quiz:{user_id}:q", f"quiz:{user_id}:a")
    else:
        update.message.reply_text("Неправильно... Попробуешь ещё раз?", reply_markup=build_keyboard())
    return States.WAITING_ANSWER


def handle_score(update: Update, context: CallbackContext):
    db: redis.Redis = context.bot_data["db"]
    user_id = update.effective_user.id
    score = db.get(f"score:{user_id}") or 0
    update.message.reply_text(f"Ваш счёт: {score}", reply_markup=build_keyboard())


def main():
    env = Env()
    env.read_env()

    token = env("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Не найден TELEGRAM_BОT_TOKEN в переменных окружения")
    
    db = redis.Redis(
        host=env("REDIS_HOST"),
        port=env.int("REDIS_PORT"),
        password=env("REDIS_PASSWORD"),
        decode_responses=True,
    )
    
    qa = load_quiz("quiz-questions")
    questions = list(qa.items())

    updater = Updater(token, use_context=True)
    dp = updater.dispatcher
    dp.bot_data["db"] = db
    dp.bot_data["questions"] = questions

    conversation_handler = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex(r"^Новый вопрос$"), handle_new_question_request),
            CommandHandler("start", start),
        ],
        states={
            States.WAITING_ANSWER: [
                MessageHandler(Filters.regex(r"^Сдаться$"), handle_give_up),
                MessageHandler(Filters.regex(r"^Мой счёт$"), handle_score),
                MessageHandler(Filters.text & ~Filters.command, handle_solution_attempt),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("help", help_command),
        ],
        allow_reentry=True,
    )
    
    dp.add_handler(conversation_handler)
    dp.add_handler(CommandHandler("help", help_command))
    
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.ERROR
    )
    logger = logging.getLogger(__name__)
    main()
