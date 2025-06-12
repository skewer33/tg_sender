import sys
import subprocess
import asyncio
import os
import pandas as pd
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, FSInputFile
from aiogram.enums import ParseMode
from aiogram.utils.markdown import hbold
from dotenv import load_dotenv
import configparser
        
        
# === CONFIG ===
load_dotenv(override=True)
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Чтение конфигурации
def read_config(config_path='config.cfg'):
    config = configparser.ConfigParser()
    config.read(config_path)
    cfg = config['DEFAULT']
    return {
        'session_name': cfg.get('session_name', 'anon'),
        'message_file': cfg.get('message_file', 'message.md'),
        'contacts_file': cfg.get('contacts_file', 'contacts.xlsx'),
        'max_messages_per_day': cfg.getint('max_messages_per_day', 50),
        'delay_seconds': cfg.getint('delay_seconds', 60),
        'media_path': cfg.get('media_path', ''),
        'media_type': cfg.get('media_type', ''),
        'downloads_dir': cfg.get('downloads_dir', '')
    }
    
config = read_config()
message_file = config['message_file']
contacts_file = config['contacts_file']
max_messages_per_day = config['max_messages_per_day']
delay_seconds = config['delay_seconds']
media_path = config['media_path']
media_type = config['media_type']
downloads_dir = config['downloads_dir']

python_path = sys.executable  # путь к текущему Python-интерпретатору
script_path = os.path.join(os.path.dirname(__file__), 'telegram_sender.py')

def update_config(**kwargs):
    """
    Updates config.cfg file with given key=value pairs.

    Parameters
    ----------
    kwargs : dict
        Any parameters to update in the [DEFAULT] section of config.cfg
    """
    config_path = 'config.cfg'
    config = configparser.ConfigParser()
    config.read(config_path)

    if 'DEFAULT' not in config:
        config['DEFAULT'] = {}

    for key, value in kwargs.items():
        config['DEFAULT'][key] = str(value)

    with open(config_path, 'w') as configfile:
        config.write(configfile)


# === STATES ===
class Form(StatesGroup):
    wait4sending = State()
    get_recipients = State()
    get_message = State()
    check_correctness = State()
    sending = State()
    report = State()

# === AUTHORIZED USERS ===
def is_authorized(user_id):
    try:
        with open("authorized_users.txt", "r") as f:
            ids = [line.strip() for line in f.readlines()]
        return str(user_id) in ids
    except Exception:
        return False

# === START ===
@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    print(f"\U0001F511 USER ID: {user_id}")
    await message.answer(f"Ваш Telegram ID: {user_id}")
    if not is_authorized(user_id):
        await message.answer("❌ У вас нет доступа к этому боту.")
        return

    if os.path.exists("report_ready.flag"):
        os.remove("report_ready.flag")
        
    await state.set_state(Form.wait4sending)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚀 Начать рассылку")]],
        resize_keyboard=True
    )
    await message.answer("Привет! Готов начать рассылку?", reply_markup=keyboard)

# === ПОЛУЧАТЕЛИ ===
@dp.message(Form.wait4sending)
async def ask_recipients(message: types.Message, state: FSMContext):
    if message.text != "🚀 Начать рассылку":
        return
    await state.set_state(Form.get_recipients)
    await message.answer("📋 Пришлите список пользователей (username) в столбик или прикрепите Excel-файл.",
                         reply_markup=ReplyKeyboardMarkup(
                             keyboard=[[KeyboardButton(text="🔙 Назад")]], resize_keyboard=True))
    
# === Get recipients ===
# xlsx or message of userids separated by '\n'
@dp.message(Form.get_recipients)
async def handle_recipients(message: types.Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await state.set_state(Form.wait4sending)
        await message.answer("Привет! Готов начать рассылку?", reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🚀 Начать рассылку")]], resize_keyboard=True))
        return
    
    if message.document:
        file = await bot.download(message.document)
        with open(contacts_file, "wb") as f:
            f.write(file.read())
        update_config(contacts_file=contacts_file)
        await state.update_data(contacts_file=contacts_file)
    elif message.text:
        usernames = [line.strip().lstrip("@") for line in message.text.strip().splitlines() if line.strip()]
        df = pd.DataFrame({"tg_username": usernames})
        df["sent"] = "no"
        df.to_excel(contacts_file, index=False)
        update_config(contacts_file=contacts_file)
        await state.update_data(contacts_file=contacts_file)
    else:
        await message.answer(f"⚠️ Пожалуйста, отправьте список текстом или прикрепите .xlsx файл.\nВажно! Во избежание бана, не отправляйте более {max_messages_per_day} контактов в сутки")
        return
    
    await state.set_state(Form.get_message)
    await message.answer("✉️ Введите сообщение для рассылки.", reply_markup=ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Назад")]], resize_keyboard=True))

# === Get Message ===
# get message from user
# he also could send 1 photo or 1 document
@dp.message(Form.get_message)
async def handle_message_text(message: types.Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await state.set_state(Form.get_recipients)
        await message.answer("📋 Пришлите список пользователей (username) в столбик или прикрепите Excel-файл.",
                         reply_markup=ReplyKeyboardMarkup(
                             keyboard=[[KeyboardButton(text="🔙 Назад")]], resize_keyboard=True))
        return

    html_text = message.html_text or ""
    media_path = None

    # Save photo or document
    if message.document:
        async def handle_document(message):
            media_path = os.path.join(downloads_dir, message.document.file_name)
            
            file = await bot.get_file(message.document.file_id)
            await bot.download_file(file.file_path, media_path)
            return media_path
        
        media_path = await handle_document(message)
        update_config(media_path=media_path, media_type='document')
    elif message.photo:
        async def handle_photo(message):
            media_path = os.path.join(downloads_dir, 'photo.jpg')
            photo = message.photo[-1]  # самое большое фото
            file = await bot.get_file(photo.file_id)
            
            await bot.download_file(file.file_path, media_path)
            return media_path
        
        media_path = await handle_photo(message)
        update_config(media_path=media_path, media_type='photo')
    else:
        update_config(media_path='', media_type='')


    with open("message.md", "w", encoding="utf-8") as f:
        f.write(message.text or "")
    with open("message.html", "w", encoding="utf-8") as f:
        f.write(html_text)

    await state.update_data(
        message_file=message_file,
        html_text=html_text,
        media_path=media_path,
        media_type="document" if message.document else "photo" if message.photo else None
    )

    await state.set_state(Form.check_correctness)
    await message.answer("📨 Подтвердите рассылку сообщения:", reply_markup=ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Разослать")],
            [KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    ))

    # repeat user message and show number of recipients
    df = pd.read_excel(contacts_file)
    await message.answer(f"Ваше сообщение будет разослано по {len(df[df.sent == 'no'])} контактам:")

    if media_path:
        await message.answer_document(FSInputFile(media_path)) if message.document else await message.answer_photo(FSInputFile(media_path))

    await message.answer(html_text, parse_mode=ParseMode.HTML)

# === Check correctness ===
# user checks correctnes of message and number of users
@dp.message(Form.check_correctness)
async def confirm_sending(message: types.Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await state.set_state(Form.get_message)
        await message.answer("↩️ Введите новое сообщение:", reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Назад")]], resize_keyboard=True))
        return

    if message.text != "✅ Разослать":
        return

    await state.set_state(Form.sending)
    await handle_sending(message, state)

# === Information message of start sending ===
@dp.message(Form.sending)
async def handle_sending(message: types.Message, state: FSMContext):
    await message.answer("🚀 Запускаю рассылку...", reply_markup=ReplyKeyboardRemove())
    subprocess.Popen([python_path, script_path])
    await message.answer("✅ Рассылка запущена. Ожидайте отчёт.")
    await state.set_state(Form.report)
    await handle_report(message, state)

# === Waiting for end of sending ===
# bot waited when telegram_sender.py creates report_ready.flag
@dp.message(Form.report)
async def handle_report(message: types.Message, state: FSMContext):
    await message.answer("⏳ Ожидаю завершения рассылки...")
    while not os.path.exists("report_ready.flag"):
        await asyncio.sleep(5)

    os.remove("report_ready.flag")
    output_file = [f for f in os.listdir() if f.startswith('output_' + contacts_file.rstrip('.xlsx')) and f.endswith(".xlsx")]
    if output_file:
        path = output_file[0]
        df = pd.read_excel(path)
        count = df[df['sent'].str.lower() == 'yes'].shape[0]
        await message.answer(f"✅ Рассылка завершена. Сообщения успешно отправлены {count} контактам.")
        await message.answer_document(FSInputFile(path))

def get_all_authorized():
    with open("authorized_users.txt") as f:
        return [int(x.strip()) for x in f if x.strip().isdigit()]

# === RUN ===
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
