import logging
import traceback
import json
import os
from typing import Optional, Tuple, Union, List
from html import escape
from datetime import time
from dotenv import load_dotenv
import pytz

from telegram import KeyboardButton, ReplyKeyboardMarkup
from telegram import __version__ as TG_VER

try:
    from telegram import __version_info__
except ImportError:
    __version_info__ = (0, 0, 0, 0, 0)  # type: ignore[assignment]

if __version_info__ < (20, 0, 0, "alpha", 1):
    raise RuntimeError(
        "Этот бот совместим только с python-telegram-bot v20.0a2 или выше."
    )


from telegram import (
    Chat,
    ChatMember,
    ChatMemberUpdated,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ChatMemberHandler,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)

from staff_info import employee_info
from schedule import  employee_infos
from manage_bdays import generate_wish
from resource_data import get_resources

# Включить ведение журнала
# Вы также можете включить запись в файл — просто раскомментируйте строки ниже
logging.basicConfig(
    # filename="app.log",
    # filemode="w",
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

load_dotenv()

# Среда
ENV: str = os.environ.get("ENV", "dev")

# ИНФОРМАЦИЯ О БОТЕ
BOT_VERSION: str = "актуальная"
BOT_NAME: str = "Бот"
BOT_DESCRIPTION: str = """Создан не для продажи.\n
Привет, я бот написанный на Python. 
Так что вы можете буквально заглянуть внутрь меня! - Как я обрабатываю все ваши просьбы...\n
Кроме того, приветствуется сообщение об ошибках и всегда приветствуются запросы на включение! 🤗\n"""

# Настройки рендеринга
PORT: str = os.environ.get("PORT", "8443")
RENDER_APP_URL: str = os.environ.get("RENDER_APP_URL", "")

# ИНФОРМАЦИЯ В ЧАТЕ/ТЕЛЕГРАММЕ
TELEGRAM_TOKEN: str = os.environ["TELEGRAM_TOKEN"]
DEV_CHAT_ID: str = os.environ["DEV_CHAT_ID"]
GROUP_CHAT_ID: str = os.environ["GROUP_CHAT_ID"]


# ДАННЫЕ ЧАСОВОГО ПОЯСА
TIME_ZONE: str = "Europe/Moscow"

# ИНФОРМАЦИЯ ОБ УНИВЕРСИТЕТЕ
UNI_NAME_LONG: str = "Калмыцкий государственный университет"
UNI_NAME_SHORT: str = "KGU"
UNI_DESCRIPTION: str = (
    "КалмГУ — опорный университет Калмыкии.\n"
    "приглашает вас стать свидетелями поистине уникального опыта!\n"
    "Читать далее <a href='https://vk.com/kalmgu08?ysclid=m69a0fna7j498202126'>здесь.</a>\n\n"
    "<b>📞 Общие номера:</b> +7(84722)4-10-05\n +7(84722)5-08-10\n\n"
    "<b>📠 Приемная:</b> 88472241005\n 88472250810\n\n"
    "<b>📨 Почта:</b> uni@kalmsu.ru\n\n"
    "<b>🏬 Адрес:</b> 358000, Республика Калмыкия, г. Элиста, ул. Пушкина, 11\n"
)

# ВЫБОР ДАННЫХ
USER_ID, USER_NIC = range(2)
QUERY_STAFF = range(1)
QUERY_SCHED = range(1)
QUERY_USER = range(1)
ANNOUNCEMENT_QUERY = range(1)
RESOURCE_QUERY = range(1)


def is_authenticated_origin(update: Update) -> bool:
    """
    Проверяет, исходило ли обновление из группового чата или чата разработчиков.
    """
    logger.info("Authentication request originated from ID: %s", update.message.chat.id)
    return (
        str(update.message.chat.id) == GROUP_CHAT_ID
        or str(update.message.chat.id) == DEV_CHAT_ID
    )


def extract_status_change(
    chat_member_update: ChatMemberUpdated,
) -> Optional[Tuple[bool, bool]]:
    """
    Берет экземпляр ChatMemberUpdated и извлекает информацию о том, был ли «old_chat_member» участником
    чата и является ли «new_chat_member» участником чата. Возвращает Нет, если
    статус не изменился.
    """
    status_change = chat_member_update.difference().get("status")
    old_is_member, new_is_member = chat_member_update.difference().get(
        "is_member", (None, None)
    )

    if status_change is None:
        return None

    old_status, new_status = status_change
    was_member = old_status in [
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
    ] or (old_status == ChatMember.RESTRICTED and old_is_member is True)
    is_member = new_status in [
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
    ] or (new_status == ChatMember.RESTRICTED and new_is_member is True)

    return was_member, is_member


async def alert_dev(message: str, alert_type: int, context: ContextTypes) -> None:
    """
    Отправляйте обновления, ошибки разработчику.
    Типы оповещений:
        0 -> Ошибка
        1 -> Обновить
        2 -> Предупреждение
        3 -> Несанкционированное использование
    """
    logger.info("Sending new update to developer - Type: %s", alert_type)
    if alert_type == 0:
        await context.bot.send_message(
            chat_id=DEV_CHAT_ID,
            text=(f"🔴 <b><u>{BOT_NAME} - Отчет об ошибках</u></b>\n\n" f"{message}"),
            parse_mode=ParseMode.HTML,
        )
        return
    elif alert_type == 1:
        await context.bot.send_message(
            chat_id=DEV_CHAT_ID,
            text=(f"🔵 <b><u>{BOT_NAME} -  Новое обновление</u></b>\n\n" f"{message}"),
            parse_mode=ParseMode.HTML,
        )
        return
    elif alert_type == 2:
        await context.bot.send_message(
            chat_id=DEV_CHAT_ID,
            text=(f"⏺ <b><u>{BOT_NAME} -  Предупреждение</u></b>\n\n" f"{message}"),
            parse_mode=ParseMode.HTML,
        )
        return
    else:
        logger.error("Invalid alert type provided. [Accepted: 0, 1, 2, 3]")
        return


async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отслеживает чаты, в которых находится бот."""
    result = extract_status_change(update.my_chat_member)
    if result is None:
        return
    was_member, is_member = result

    # Проверьте, кто несет ответственность за изменение
    cause_name = update.effective_user.full_name

    # Обрабатывает типы чатов по-разному:
    chat = update.effective_chat
    if chat.type == Chat.PRIVATE:
        if not was_member and is_member:
            logger.info("%s started the bot", cause_name)
            context.bot_data.setdefault("user_ids", set()).add(chat.id)
            await alert_dev(f"{cause_name} has started {BOT_NAME}", 1, context)
        elif was_member and not is_member:
            logger.info("%s blocked the bot", cause_name)
            context.bot_data.setdefault("user_ids", set()).discard(chat.id)
            await alert_dev(f"{cause_name} has blocked {BOT_NAME}", 1, context)
    elif chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
        if not was_member and is_member:
            logger.info("%s added the bot to the group %s", cause_name, chat.title)
            context.bot_data.setdefault("group_ids", set()).add(chat.id)
            await alert_dev(
                f"{cause_name} has added {BOT_NAME} to group - {chat.title}", 1, context
            )
        elif was_member and not is_member:
            logger.info("%s removed the bot from the group %s", cause_name, chat.title)
            context.bot_data.setdefault("group_ids", set()).discard(chat.id)
            await alert_dev(
                f"{cause_name} has removed {BOT_NAME} from group - {chat.title}",
                1,
                context,
            )
    else:
        if not was_member and is_member:
            logger.info("%s added the bot to the channel %s", cause_name, chat.title)
            context.bot_data.setdefault("channel_ids", set()).add(chat.id)
            await alert_dev(
                f"{cause_name} has added {BOT_NAME} to channel - {chat.title}",
                1,
                context,
            )
        elif was_member and not is_member:
            logger.info(
                "%s removed the bot from the channel %s", cause_name, chat.title
            )
            context.bot_data.setdefault("channel_ids", set()).discard(chat.id)
            await alert_dev(
                f"{cause_name} has removed {BOT_NAME} from channel - {chat.title}",
                1,
                context,
            )


async def greet_chat_members(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Приветствует новых пользователей в чатах и объявляет, когда кто-то уходит."""
    result = extract_status_change(update.chat_member)
    if result is None:
        return

    was_member, is_member = result
    cause_name = update.chat_member.from_user.mention_html()
    member_name = update.chat_member.new_chat_member.user.mention_html()

    if not was_member and is_member:
        if member_name == cause_name:
            await update.effective_chat.send_message(
                f"Добро пожаловать {member_name}! 🤗 🎉\nРад видеть вас здесь!"
                f"Я {BOT_NAME} кстати. Если вам интересно узнать, что я могу сделать, просто введите /help.",
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.effective_chat.send_message(
                f"{member_name} был добавлен пользователем {cause_name}.\nДобро пожаловать {member_name}! 🤗 🎉\n\n"
                f"Я {BOT_NAME} кстати. Если вам интересно узнать, что я могу сделать, просто введите /help.",
                parse_mode=ParseMode.HTML,
            )
    elif was_member and not is_member:
        await update.effective_chat.send_message(
            f"{member_name} его больше нет с нами... До скорой встречи {member_name}! 🙌",
            parse_mode=ParseMode.HTML,
        )


async def check_bdays(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверяет дни рождения и отправляет пожелания пользователям"""
    logger.info("Checking for birthdays")
    bday_wishes: List[str] = generate_wish()

    for wish in bday_wishes:
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID, text=wish, parse_mode=ParseMode.HTML
        )


def remove_task_if_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Удалить задачу с заданным именем. Возвращает, была ли задача удалена."""
    current_tasks = context.job_queue.get_jobs_by_name(name)

    if not current_tasks:
        return False
    for task in current_tasks:
        task.schedule_removal()

    return True



async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывать раздел «Помощь» для бота при вводе команды /help."""
    logger.info("/help command issued by %s", update.effective_user.full_name)

    # Создайте клавиатуру ответа с кнопками
    reply_keyboard = ReplyKeyboardMarkup(
        [
            [
                KeyboardButton("/help"),
                KeyboardButton("/about"),
            ],
            [
                KeyboardButton("/resources"),
                KeyboardButton("/staff"),
            ],
            [
                KeyboardButton("/kgu"),
                KeyboardButton("/sched"),
            ],
        ],
        resize_keyboard=True,
    )

    await update.message.reply_text(
        f"<b>Привет! 👋 Я {BOT_NAME} для направления бизнес-информатика, работаю <i>24x7</i> несмотря ни на что 😊</b>"
        "\n\n"
        "<b><u>Основные команды</u></b>"
        "\n\n"
        "/help - 👀 Показать это сообщение"
        "\n"
        "/about - ⭐ Прочитай обо мне"
        "\n"
        "/cancel - 🚫 Отменить любую запущенную операцию"
        "\n\n"
        "<b><u>Университет</u></b>"
        "\n\n"
        "/resources - 📚 Изучить ресурсы"
        "\n"
        "/staff - 👥 Получить информацию о преподавателях"
        "\n"
        "/sched - 📝 расписание"
        "\n"
        f"/{UNI_NAME_SHORT.lower()} - 🎓 Об университете",
        reply_markup=reply_keyboard,
        parse_mode=ParseMode.HTML,
    )


async def about_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывать BOT_VERSION и информацию при вводе команды /about."""
    logger.info("/about command issued by %s", update.effective_user.full_name)
    await update.message.reply_text(
        f"Я {BOT_NAME} - Версия {BOT_VERSION}"
        "\n"
        f"{BOT_DESCRIPTION}"
        "\n\n"
        "Создатель @Kuromaros"
        "\n\n"
        "Просмотрите мой исходный код <a href='https://github.com/Kuro-Ray/TeleBot'>@GitHub</a>",
        parse_mode=ParseMode.HTML,
    )


async def about_university(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывать информацию об университете при вводе команды /{UNI_NAME_SHORT}."""
    logger.info(
        "/%s command issued by %s",
        UNI_NAME_SHORT.lower(),
        update.effective_user.full_name,
    )
    await update.message.reply_text(
        UNI_DESCRIPTION,
        parse_mode=ParseMode.HTML,
    )

    return ConversationHandler.END


async def resources(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Получить запрос ресурсов пользователя"""
    logger.info("/resources command issued by %s", update.effective_user.full_name)
    logger.info("/resources - Getting user's search query")
    await update.message.reply_text(
        "Хорошо... Давайте посмотрим, что вы ищете! 🧐\n"
        "Пожалуйста, введите поисковый запрос:\n\n"
        "Если вы хотите отменить этот разговор, просто введите /cancel."
    )
    return RESOURCE_QUERY


async def send_resources(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Возвращать ресурсы на основе запроса пользователя."""
    logger.info("Received query from user: %s", update.message.text)
    await update.message.reply_text(
        get_resources(update.message.text), parse_mode=ParseMode.HTML
    )

    return ConversationHandler.END


async def staff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Получить поисковый запрос пользователя"""
    logger.info("/staff command issued by %s", update.effective_user.full_name)
    logger.info("/staff - Getting user's search query")
    await update.message.reply_text(
        "Хорошо... Давайте посмотрим, кого вы ищете! 🧐\n"
        "Пожалуйста, введите поисковый запрос (Часть имени, Должность, Телефон...):\n\n"
        "Если вы хотите отменить этот разговор, просто введите /cancel."
    )
    return QUERY_STAFF


async def get_staff_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Возвращает информацию о сотруднике по запросу пользователя."""
    logger.info("Received query from user: %s", update.message.text)
    await update.message.reply_text(
        employee_info(update.message.text), parse_mode=ParseMode.HTML
    )

    return ConversationHandler.END


async def sched(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Получить поисковый запрос пользователя"""
    logger.info("/sched command issued by %s", update.effective_user.full_name)
    logger.info("/sched - Getting user's search query")
    await update.message.reply_text(
        "Хорошо... Давайте посмотрим, что вы ищете! 🧐\n"
        "Пожалуйста, введите запрос (номер и курс):\n\n"
        "Если вы хотите отменить этот разговор, просто введите /cancel."
    )
    return QUERY_SCHED


async def get_sched(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Возвращает информацию о сотруднике по запросу пользователя."""
    logger.info("Received query from user: %s", update.message.text)
    await update.message.reply_text(
        employee_infos(update.message.text), parse_mode=ParseMode.HTML
    )

    return ConversationHandler.END


async def cancel_conversation(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Отменяет и завершает активный разговор."""
    logger.info("/cancel command issued by %s", update.effective_user.full_name)
    await update.message.reply_text("✅ ОК, ваш запрос отменен. Нажмите /help чтобы вернуться")
    logger.info(
        "Conversation with %s has been cancelled", update.effective_user.full_name
    )

    return ConversationHandler.END


async def unknown_commands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ответ на неизвестные команды."""
    logger.warning(
        "Unknown command issued by %s | Command: %s",
        update.effective_user.full_name,
        update.message.text,
    )
    await update.message.reply_text(
        "Извините, я не понял эту команду 🤖\nОтправьте /help, чтобы узнать, что я могу сделать."
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Зарегистрируйте ошибку и отправьте телеграмму, чтобы уведомить разработчика."""
    logger.error(
        "Exception while handling an update - Sending error message to developer"
    )

    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__, 5
    )
    tb_string = "".join(tb_list)

    update_str = update.to_dict() if isinstance(update, Update) else str(update)

    message = (
        "Исключение возникло при обработке обновления\n\n"
        f"<pre>update = {escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {escape(str(context.user_data))}</pre>\n\n"
        f"⏩ <pre>{escape(tb_string)}</pre>"
    )

    await alert_dev(message, 0, context)

    await update.message.reply_text(
        "Упс! Что-то не так 🤖\n"
        "При обработке вашего запроса произошла ошибка.\n"
        "Об ошибке сообщено разработчику, в ближайшее время она будет исправлена.\n"
    )


def main() -> None:
    """Запуск бота."""
    # Создайте приложение и передайте ему токен вашего бота.
    # Используйте переменные среды, чтобы избежать жесткого кодирования токена вашего бота.
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Обработка участников, присоединяющихся к чатам или покидающих их.
    application.add_handler(
        ChatMemberHandler(greet_chat_members, ChatMemberHandler.CHAT_MEMBER)
    )
    logger.info("Greeting handler added")

    # Обработка команды «/help».
    application.add_handler(CommandHandler(["help", "start"], help_command))
    logger.info("Help handler added")

    # Обработка команды «/about».
    application.add_handler(CommandHandler("about", about_bot))
    logger.info("About Bot handler added")

    # Обработка команды '/{UNI_NAME_SHORT}'.
    application.add_handler(CommandHandler(UNI_NAME_SHORT.lower(), about_university))
    logger.info("About University handler added")

    # Ведение разговора – Информация о персонале
    staff_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("staff", staff)],
        states={
            QUERY_STAFF: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_staff_info)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    application.add_handler(staff_conv_handler)
    logger.info("Staff Info conversation handler added")

    # Ведение разговора – Расписание
    sched_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("sched", sched)],
        states={
            QUERY_SCHED: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_sched)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    application.add_handler(sched_conv_handler)
    logger.info("Sched Info conversation handler added")


    # Ведение разговора — Ресурсы
    resources_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("resources", resources)],
        states={
            RESOURCE_QUERY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, send_resources)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    application.add_handler(resources_conv_handler)
    logger.info("Resources conversation handler added")

    # Обработка неизвестных команд.
    application.add_handler(MessageHandler(filters.COMMAND, unknown_commands))
    logger.info("Unknown Command handler added")

    # Обработка ошибок.
    application.add_error_handler(error_handler)
    logger.info("Error handler added")

    if ENV == "dev":
        # О местной среде
        # Запуск бота, пока пользователь не нажмет Ctrl-C.
        # Pass 'allowed_updates' handle *all* updates including `chat_member` updates
        # Чтобы сбросить это, просто передайте `allowed_updates=[]`
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    else:
        # При рендеринге — производственная среда
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TELEGRAM_TOKEN,
            webhook_url=RENDER_APP_URL + TELEGRAM_TOKEN,
        )


if __name__ == "__main__":
    main()
