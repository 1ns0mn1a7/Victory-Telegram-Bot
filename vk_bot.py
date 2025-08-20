import logging
import random
import redis
from enum import Enum, auto
from environs import Env
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from fetch_quiz import load_quiz, normalize_answer


class States(Enum):
    WAITING_ANSWER = auto()


def build_keyboard():
    keyboard = VkKeyboard(one_time=False, inline=False)
    keyboard.add_button("Новый вопрос", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("Сдаться", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button("Мой счёт", color=VkKeyboardColor.POSITIVE)
    return keyboard.get_keyboard()


def send_message(vk, user_id, text, keyboard=None):
    vk.messages.send(
        user_id=user_id,
        message=text,
        random_id=0,
        keyboard=keyboard
    )


def handle_new_question(vk, db, questions, user_id):
    if not questions:
        send_message(vk, user_id, "Вопросов нет 🙈")
        return

    question, answer = random.choice(questions)
    db.hset(f"vk:quiz:{user_id}", mapping={"q": question, "a": answer})

    send_message(vk, user_id, f"Вопрос:\n\n{question}", keyboard=build_keyboard())


def handle_give_up(vk, db, questions, user_id):
    answer = db.hget(f"vk:quiz:{user_id}", "a")
    if not answer:
        send_message(vk, user_id, "Сначала нажмите «Новый вопрос».", keyboard=build_keyboard())
        return

    send_message(vk, user_id, f"Правильный ответ:\n\n{answer}", keyboard=build_keyboard())

    question_next, answer_next = random.choice(questions)
    db.hset(f"vk:quiz:{user_id}", mapping={"q": question_next, "a": answer_next})
    send_message(vk, user_id, f"Следующий вопрос:\n\n{question_next}", keyboard=build_keyboard())


def handle_solution_attempt(vk, db, user_id, text):
    correct = db.hget(f"vk:quiz:{user_id}", "a")
    if not correct:
        send_message(vk, user_id, "Нажмите «Новый вопрос», чтобы начать.", keyboard=build_keyboard())
        return

    user_ans = normalize_answer(text or "")
    true_ans = normalize_answer(correct)

    if user_ans == true_ans:
        send_message(vk, user_id, "Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»",
                     keyboard=build_keyboard())
        db.delete(f"vk:quiz:{user_id}")
        db.incr(f"vk:score:{user_id}")
    else:
        send_message(vk, user_id, "Неправильно... Попробуешь ещё раз?", keyboard=build_keyboard())


def handle_score(vk, db, user_id):
    raw = db.get(f"vk:score:{user_id}")
    score = int(raw) if raw is not None else 0
    send_message(vk, user_id, f"Ваш счёт: {score}", keyboard=build_keyboard())


def main():
    logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")
    env = Env()
    env.read_env()

    vk_token = env("VK_GROUP_TOKEN")
    db = redis.Redis(
        host=env("REDIS_HOST"),
        port=env.int("REDIS_PORT"),
        password=env("REDIS_PASSWORD"),
        decode_responses=True,
    )

    qa = load_quiz("quiz-questions")
    questions = list(qa.items())

    vk_session = vk_api.VkApi(token=vk_token)
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)

    logging.info("VK Quiz Bot запущен!")

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_id = event.user_id
            text = event.text.strip()

            if text == "Новый вопрос":
                handle_new_question(vk, db, questions, user_id)
            elif text == "Сдаться":
                handle_give_up(vk, db, questions, user_id)
            elif text == "Мой счёт":
                handle_score(vk, db, user_id)
            elif text.lower() == "старт":
                send_message(vk, user_id, "Привет! Я бот для викторин 👋", keyboard=build_keyboard())
            else:
                handle_solution_attempt(vk, db, user_id, text)


if __name__ == "__main__":
    main()
