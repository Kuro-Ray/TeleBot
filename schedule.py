import os
from functools import lru_cache
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from thefuzz import fuzz

load_dotenv()

BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
data_path: str = os.path.join(BASE_DIR, "DATA", "schedule.txt.crypt")
fernet = Fernet(os.environ["SECRET_KEY"])

@lru_cache(maxsize=16)
def employee_infos(query: str) -> str:
    """Создать информацию и вернуть текст сообщения"""
    found_info: list = []
    message_body: str = "<b>🔎 Вот что я нашел:</b>\n\n"

    with open(file=data_path, mode="rb") as data_file:
        stream = data_file.read()
        decrypted_data = fernet.decrypt(stream).decode().strip()
        employees: list = decrypted_data.split("\n\n")
        for employee in employees:
            if fuzz.partial_ratio(query.lower(), employee.lower()) > 90:
                found_info.append(employee)

    if not found_info:
        return "😕 Соответствующих данных не найдено!\nМожете ли вы попробовать еще раз с другим запросом?\nВведите /sched"
    if len(found_info) > 4:
        return (
            f"😕 <b>'{query}' найден в {len(found_info)} месте!"
            "</b>\nМожете ли вы сузить поисковый запрос?\nВведите /sched"
        )
    for info in found_info:
        message_body += f"{info}\n\n"

    return message_body + "\n\n<b>Хотите найти расписание другого курса? Введите /sched</b>\n<b>Введите /help, чтобы открыть меню.</b>"