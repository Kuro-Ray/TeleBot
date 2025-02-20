"""
Зашифруйте данные с помощью ключа.
важно:
    - Ключ будет сохранен в текущей папке с именем "key.txt"
    - Не предоставляйте никому доступ к ключу!
    - Обязательно удалите исходные файлы данных после шифрования.
"""

from typing import List
from datetime import datetime
from cryptography.fernet import Fernet

FILES: List[str] = [
    "full_batch_data.csv",
    "results.csv",
    "resources.csv",
    "staff_info.txt",
]

key = Fernet.generate_key()
# Если у вас есть ключ, вы можете использовать его вместо создания нового
# Раскомментируйте следующую строку и вставьте свой ключ
# key = "paste_your_key_here"

filename: str = (
    "KEY_" + datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(":", "_") + ".txt"
)
# Сохраните ключ в текущей папке
with open(filename, "wb") as key_file:
    key_file.write(key)
print(f"Ключ, сохранен в {filename}")

for file in FILES:
    try:
        with open(file, "rb") as file_to_encrypt:
            data = file_to_encrypt.read()
            fernet = Fernet(key)
            encrypted_data = fernet.encrypt(data)
    except FileNotFoundError:
        print(f"Файл '{file}' не найден! -- возобновите...")
        continue

    try:
        with open(file + ".crypt", "wb") as encrypted_file:
            encrypted_file.write(encrypted_data)
    except Exception as e:
        print(f"Произошла ошибка при сохранении зашифрованного файла: '{file}' -- возобновите...")
        print(e)
        continue

    print(f"==== {file} Зашифрован. =====")

print("Шифрование завершено!")
