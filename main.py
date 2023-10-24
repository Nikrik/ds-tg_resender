import json
import discord
import telebot
from threading import Thread
import asyncio
import os
from datetime import datetime


class MyDiscordClient(discord.Client):
    # Переопределяем класс что бы подружить асинхронные функции с синхронными
    async def on_ready(self):
        self.loop = asyncio.get_running_loop()

    def send_message(self, ds_channel_id, message, files=None):
        asyncio.run_coroutine_threadsafe(self.my_async_func(ds_channel_id, message, files), self.loop)

    async def my_async_func(self, ds_channel_id, message, files):
        ds_channel = await self.fetch_channel(ds_channel_id)
        if files:
            ds_files = [discord.File(item) for item in files]
            await ds_channel.send(message, files=ds_files)
            for item in files:
                item.close()
        else:
            await ds_channel.send(message)


with open('settings.json') as f:
    data = json.load(f)

ds_token = data['ds_token']
tg_token = data['tg_token']
ds_channel_id = data['ds_channel_id']
tg_chat_id = data['tg_chat_id']
ds_owner_chat_id = data['ds_owner_chat_id']


tg_content_types = ['text', 'audio', 'photo', 'voice', 'video', 'document', 'location', 'contact', 'sticker']
ds_content_type = "attachments"


intents = discord.Intents(messages=True, message_content=True)
ds_bot = MyDiscordClient(intents=intents)


tg_bot = telebot.TeleBot(tg_token)


@ds_bot.event
async def on_ready():
    pid = os.getpid()
    readytext = f"Бот запущен под PID: {pid}, что бы его остановить пропишите kill {pid} в терминал сервера"
    ds_bot.send_message(ds_owner_chat_id, readytext)


async def try_delete_file(filename):
    max_attempts = 100
    retry_interval = 3
    for attempt in range(max_attempts):
        try:
            print("Сплю")
            await asyncio.sleep(retry_interval)
            os.remove(filename)
            print("Файл удалён")
            break
        except PermissionError as e:
            if not (attempt < (max_attempts - 1)):
                raise e


# Пересылание сообщений из Discord в Telegram
@ds_bot.event
async def on_message(message):
    if message.channel.id == ds_channel_id:
        if message.author.id != ds_bot.user.id:
            try:
                text = f"*{message.author.display_name}*\n{message.content}"

                # Экранируем сообщения
                escaped_characters = "()=.->"
                for item in escaped_characters:
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
                ds_bot.send_message(ds_owner_chat_id, errortext)
                raise e


# Пересылание сообщений из Telegram в Discord
@tg_bot.message_handler(content_types=tg_content_types)
def get_message(message):
    # ds_bot.send_message(ds_owner_chat_id, "errortext")
    if message.chat.id == tg_chat_id:
        try:
            if message.content_type in ["text"]:
                text = f'**{message.from_user.username}**\n{message.text}'
                ds_bot.send_message(ds_channel_id, text)
            elif message.content_type in ["photo", "document", "sticker"]:
                text = f'**{message.from_user.username}**\n{message.caption if message.caption else ""}'
                if message.content_type == "photo":
                    fileID = message.photo[-1].file_id
                elif message.content_type == "document":
                    fileID = message.document.file_id
                elif message.content_type == "sticker":
                    fileID = message.sticker.file_id
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
                ds_bot.send_message(ds_channel_id, text, [localfile])
                asyncio.run(try_delete_file(file_info.file_path))
            else:
                errortext = f"Тип данных {message.content_type} не учтён"
                ds_bot.send_message(ds_owner_chat_id, errortext)
        except Exception as e:
            errortext = f"Произошла ошибка при пересыланиии сообщения из телеграма в дискорд на строке {e.__traceback__.tb_lineno}:"
            errortext += f"\n{str(e)}\n"
            errdate = datetime.fromtimestamp(message.date).astimezone().isoformat()
            errortext += f"ID Сообщения: {message.id} от {errdate}"
            ds_bot.send_message(ds_owner_chat_id, errortext)
            raise e


def run_ds():
    ds_bot.run(ds_token)


def run_tg():
    tg_bot.polling()


ds_thread = Thread(target=run_ds)
tg_thread = Thread(target=run_tg)
ds_thread.start()
tg_thread.start()
ds_thread.join()
tg_thread.join()
