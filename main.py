import json
import discord
import telebot
from threading import Thread
import asyncio
import os
from datetime import datetime
import time
from telebot.types import Message
from telebot import ExceptionHandler
from telebot.handler_backends import HandlerBackend
from telebot.storage import StateStorageBase
import http.client


async def try_delete_file(filename):
    max_attempts = 100
    retry_interval = 3
    for attempt in range(max_attempts):
        try:
            await asyncio.sleep(retry_interval)
            os.remove(filename)
            break
        except PermissionError as e:
            if not (attempt < (max_attempts - 1)):
                raise e


class MyTelegramClient(telebot.TeleBot):
    # Переопределяем класс, что бы починить его отрубание
    def __init__(self, token: str, welcome_event_handler=None, message_event_handler=None, parse_mode: str | None = None, threaded: bool | None = True, skip_pending: bool | None = False, num_threads: int | None = 2, next_step_backend: HandlerBackend | None = None, reply_backend: HandlerBackend | None = None, exception_handler: ExceptionHandler | None = None, last_update_id: int | None = 0, suppress_middleware_excepions: bool | None = False, state_storage: StateStorageBase | None = ..., use_class_middlewares: bool | None = False, disable_web_page_preview: bool | None = None, disable_notification: bool | None = None, protect_content: bool | None = None, allow_sending_without_reply: bool | None = None, colorful_logs: bool | None = False):
        self.__is_polling = False
        # self.set_messa
        super().__init__(token, parse_mode, threaded, skip_pending, num_threads, next_step_backend, reply_backend, exception_handler, last_update_id, suppress_middleware_excepions,
                         state_storage, use_class_middlewares, disable_web_page_preview, disable_notification, protect_content, allow_sending_without_reply, colorful_logs)
        self.message_event_handler = message_event_handler
        self.welcome_event_handler = welcome_event_handler

    def set_message_event_handler(self, function):
        self.message_event_handler = function

    def set_welcome_event_handler(self, function):
        self.welcome_event_handler = function

    def __poll(self):
        connection = http.client.HTTPSConnection("api.telegram.org")
        offset = None
        # Пропустить сообщения, которые бот получит, когда был неактивным
        if False:
            url = f"/bot{self.token}/getUpdates"
            connection.request("GET", url)
            response = json.loads(connection.getresponse().read().decode("utf-8"))

        while self.__is_polling:
            url = f"/bot{self.token}/getUpdates?timeout=5{f'&offset={offset}' if offset else ''}"
            connection.request("GET", url)
            response = json.loads(connection.getresponse().read().decode("utf-8"))
            if response['ok'] == True:
                result = response['result']
                if result:
                    offset = result[-1]['update_id']+1
                    for item in result:
                        if 'message' in item.keys():
                            message_object = Message.de_json(item['message'])
                            if message_object:
                                if self.message_event_handler != None:
                                    if message_object.content_type == "new_chat_members":
                                        self.welcome_event_handler(message_object)
                                    else:
                                        self.message_event_handler(message_object)
                        else:
                            text = f"Тип {item.keys()} не учтён"
                            print(text)
                            report_bug(text)
                else:
                    offset = None
                time.sleep(1)
            else:
                report_bug(f"not ok {response}")

    def start(self):
        if self.__is_polling == False:
            self.__is_polling = True
            self.__poll()
            print("im running")
        else:
            raise RuntimeError("MyTelegramClient is already running")

    def stop(self):
        self.__is_polling = False
        print("im stop polling")


class MyDiscordClient(discord.Client):
    # Переопределяем класс что бы подружить асинхронные функции с синхронными
    async def on_ready(self):
        self.loop = asyncio.get_running_loop()

    def send_message(self, ds_channel_id, message):
        asyncio.run_coroutine_threadsafe(self.my_async_func(ds_channel_id, message), self.loop)

    def send_document(self, ds_channel_id, message, file):
        print("ha")
        asyncio.run_coroutine_threadsafe(self.my_async_func(ds_channel_id, message, [file]), self.loop)

    async def my_async_func(self, ds_channel_id, message, files=None):
        ds_channel = await self.fetch_channel(ds_channel_id)
        if files:
            ds_files = [discord.File(item) for item in files]
            await ds_channel.send(message, files=ds_files)
            for item in files:
                item.close()
                await try_delete_file(item.name)
        else:
            await ds_channel.send(message)


with open('settings.json') as f:
    data = json.load(f)
    ds_token = data['ds_token']
    tg_token = data['tg_token']
    ds_channel_id = data['ds_channel_id']
    tg_chat_id = data['tg_chat_id']
    ds_admin_chat_id = data['ds_admin_chat_id']
    ds_owner_chat_id = data['ds_owner_chat_id']


def report_bug(message):
    ds_bot.send_message(ds_admin_chat_id, message)


def main():
    print("Запуск главного потока")
    ds_content_type = "attachments"

    intents = discord.Intents(messages=True, message_content=True)
    # global ds_bot
    # ds_bot = MyDiscordClient(intents=intents)
    # global tg_bot
    # tg_bot = telebot.TeleBot(tg_token)

    # Пересылание сообщений из Telegram в Discord
    def run_ds():
        global ds_bot
        global tg_bot
        while not is_killed and not is_restarted:
            print("Дискорд запускается")
            ds_bot = MyDiscordClient(intents=intents)

            @ds_bot.event
            async def on_ready():
                global pid
                pid = os.getpid()
                readytext = f"Бот запущен под PID: {pid}"
                ds_bot.send_message(ds_admin_chat_id, readytext)

            # Пересылание сообщений из Discord в Telegram

            @ds_bot.event
            async def on_message(message):
                if message.author.id != ds_bot.user.id:
                    if message.channel.id == ds_channel_id:
                        try:
                            text = f"*{message.author.display_name}*\n{message.content}"

                            # Экранируем сообщения
                            escape_characters = "#!()=.>-+[]_"
                            for item in escape_characters:
                                text = text.replace(f"{item}", f"\{item}")

                            if message.attachments:
                                if not os.path.exists(ds_content_type):
                                    os.makedirs(ds_content_type)
                                file_paths = [os.path.join(ds_content_type, item.filename) for item in message.attachments]
                                for i in range(len(message.attachments)):
                                    await message.attachments[i].save(file_paths[i])
                                    file = open(file_paths[i], 'rb')
                                    tg_bot.send_document(tg_chat_id, file, caption=text, parse_mode="MarkdownV2")
                                    file.close()
                                    await try_delete_file(file_paths[i])
                            else:
                                tg_bot.send_message(tg_chat_id, text, parse_mode="MarkdownV2")
                        except Exception as e:
                            errortext = f"Произошла ошибка при пересыланиии сообщения из дискорд в телеграм на строке {e.__traceback__.tb_lineno}:"
                            errortext += f"\n{str(e)}\n"
                            errdate = message.created_at.astimezone().isoformat()
                            errortext += f"ID Сообщения: {message.id} от {errdate}"
                            report_bug(errortext)
                            raise e
                    # Обработка входящих команд владельца и админа
                    elif message.channel.id in [ds_admin_chat_id, ds_owner_chat_id]:
                        if message.content == "kill":
                            global is_killed
                            is_killed = True
                            tg_bot.stop()
                            await ds_bot.close()
                        elif message.content == "restart":
                            global is_restarted
                            is_restarted = True
                            tg_bot.stop()
                            await ds_bot.close()
                        elif message.content == "restart DS":
                            await ds_bot.close()
                        else:
                            text = "Неизвестная команда\nДоступные команды: kill, restart, restart DS"
                            report_bug(text)
            ds_bot.run(ds_token)
            ds_bot.clear()
            print("Дискорд завершает свою работу")

    def run_tg():
        global tg_bot
        global ds_bot

        # Решение бага с переставанием получения сообщений
        def restart_tg():
            print("Таймер запущен")
            time.sleep(60*60)
            tg_bot.stop()
            print("Бот остановлен по таймеру")

        while not is_killed and not is_restarted:
            print("Телеграм запускается")
            tg_bot = MyTelegramClient(tg_token)

            # @tg_bot.message_handler(content_types=["new_chat_members"])
            def welcome(message):
                if message.chat.id == tg_chat_id:
                    try:
                        for new_chat_member in message.new_chat_members:
                            username = new_chat_member.username
                            username = username if username else new_chat_member.full_name
                            username = f'<a href="tg://user?id={new_chat_member.id}">{username}</a>'
                            text = open("tg_welcome_text.html", "r", encoding="UTF-8").read().replace("{@nickname}", username)
                            tg_bot.reply_to(message, text, parse_mode="HTML")
                    except Exception as e:
                        errortext = f"Произошла ошибка при приветствии на строке {e.__traceback__.tb_lineno}:"
                        errortext += f"\n{str(e)}\n"
                        errdate = errdate = datetime.fromtimestamp(message.date).astimezone().isoformat()
                        errortext += f"ID Сообщения: {message.id} от {errdate}"
                        report_bug(errortext)
                        raise e

            # Баг, через некоторое время перестаёт получать сообщения
            # @tg_bot.message_handler(content_types=tg_content_types)
            def get_message(message):
                fileID = None
                # ds_bot.send_message(ds_admin_chat_id, f"Сообщение из ID чата {message.chat.id},\n содержание\n{message.text}")
                if message.chat.id == tg_chat_id:
                    try:
                        if message.content_type in ["text"]:
                            username = message.from_user.username
                            username = username if username else message.from_user.full_name
                            text = f'**{username}**\n{message.text}'
                            ds_bot.send_message(ds_channel_id, text)
                        elif message.content_type in ["photo", "document", "sticker"]:
                            text = f'**{message.from_user.username}**\n{message.caption if message.caption else ""}'
                            if message.content_type == "photo":
                                fileID = message.photo[-1].file_id
                            elif message.content_type == "document":
                                fileID = message.document.file_id
                            elif message.content_type == "sticker":
                                fileID = message.sticker.thumbnail.file_id
                            else:
                                raise Exception(f"В программу не добавился тип документов: {message.content_type}")
                            file_info = tg_bot.get_file(fileID)
                            downloaded_bytes = tg_bot.download_file(file_info.file_path)
                            directory = os.path.dirname(file_info.file_path)
                            if not os.path.exists(directory):
                                os.makedirs(directory)
                            localfile = open(file_info.file_path, "wb")
                            localfile.write(downloaded_bytes)
                            localfile.close()
                            localfile = open(file_info.file_path, "rb")
                            # Баг, поток не блокируется, он начинает загружать вложение и сразу пытается удалить файл
                            ds_bot.send_document(ds_channel_id, text, localfile)
                            # asyncio.run(try_delete_file(file_info.file_path))
                        else:
                            errortext = f"Тип данных {message.content_type} не учтён"
                            report_bug(errortext)
                    except Exception as e:
                        errortext = f"Произошла ошибка при пересыланиии сообщения из телеграма в дискорд на строке {e.__traceback__.tb_lineno}:"
                        errortext += f"\n{str(e)}\n"
                        errdate = datetime.fromtimestamp(message.date).astimezone().isoformat()
                        errortext += f"ID Сообщения: {message.id} от {errdate}\n fileID={fileID}"
                        report_bug(errortext)
                        raise e
            # tg_restart_thread = Thread(target=restart_tg)
            # tg_restart_thread.start()
            tg_bot.set_message_event_handler(get_message)
            tg_bot.set_welcome_event_handler(welcome)
            tg_bot.start()
            # tg_restart_thread.join()
            print("Телеграм завершает свою работу")

    ds_thread = Thread(target=run_ds)
    tg_thread = Thread(target=run_tg)
    ds_thread.start()
    tg_thread.start()
    ds_thread.join()
    tg_thread.join()
    print("Остановка главного потока")


is_restarted = True
is_killed = False
if __name__ == "__main__":
    while is_restarted and not is_killed:
        is_restarted = False
        main()
    print("Завершение программы")
