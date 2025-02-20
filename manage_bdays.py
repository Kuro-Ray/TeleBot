import os
from typing import List
import csv
from datetime import datetime
from random import choice
from dotenv import load_dotenv
import pytz
from cryptography.fernet import Fernet

load_dotenv()

BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
data_path: str = os.path.join(BASE_DIR, "DATA", "full_batch_data.csv.crypt")
TIME_ZONE: str = "Europe/Moscow"
fernet = Fernet(os.environ["SECRET_KEY"])

WISHES: List[str] = [
    "Пусть этот день рождения станет только началом года, наполненного чудесными моментами...",
    "Пусть годы будут добрыми к тебе...",
    "Пусть этот год станет лучшим в твоей жизни...",
    "Пусть каждый уходящий год приносит тебе мудрость, мир и радость...",
    "Желаю вам чудесного дня и сказочного года...",
    "Улыбайтесь! Сегодня твой день рождения...",
    "Желаю тебе счастливого дня, наполненного смехом и любовью...",
    "Желаю тебе огромного счастья и радости, которая никогда не закончится...",
    "Всего наилучшего в этот день...",
    "Желаю вам еще одного замечательного года счастья и радости...",
    "Пусть этот год станет для вас лучшим в жизни!",
    "Поздравляем вас!",
    "Пусть этот день принесет вам все, что заставит вас улыбаться...",
    "Жизнь - это путешествие, так что наслаждайтесь каждой милей...",
    "Считайте свою жизнь по улыбкам, а не по слезам; Считайте свой возраст по друзьям, а не по годам...",
]


def get_birthdays() -> List[str]:
    """Проверка на наличие дней рождения пользователей"""
    now = datetime.now().astimezone(pytz.timezone(TIME_ZONE))
    names: List[str] = []
    with open(file=data_path, mode="rb") as data_file:
        stream = data_file.read()
        decrypted_data = fernet.decrypt(stream).decode().strip().split("\n")
        reader = csv.reader(decrypted_data)
        for row in reader:
            try:
                current_bday = datetime.strptime(row[2], "%Y-%m-%d")
                if now.month == current_bday.month and now.day == current_bday.day:
                    names.append(row[9])
            except ValueError:
                continue
    return names


def generate_wish() -> List[str]:
    """Загадать случайное желание и создать текст сообщения"""
    bday_wishes: List[str] = []
    names: List[str] = get_birthdays()
    if not names:
        return []

    for name in names:
        bday_wishes.append(
            "🎉🎉🎉🎉🎊🎈🎂🎈🎊🎉🎉🎉🎉"
            "\n\n"
            f"<b>{choice(WISHES)}</b>"
            "\n"
            f"С Днем рождения {name}!"
            "\n\n"
            "🎉🎉🎉🎉🎊🎈🎂🎈🎊🎉🎉🎉🎉"
        )

    return bday_wishes
