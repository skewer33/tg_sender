import pandas as pd
import asyncio
import time
import argparse
import logging
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import PeerFloodError, UserPrivacyRestrictedError, FloodWaitError, RPCError

from markdown import markdown as md_to_html
import re
import os
import configparser

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

# === LOAD ENV ===
load_dotenv(override=True)
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')


# === LOAD CONFIG ===
config = read_config()
session_name = config['session_name']
message_file = config['message_file']
contacts_file = config['contacts_file']
max_messages_per_day = config['max_messages_per_day']
delay_seconds = config['delay_seconds']
media_path = config['media_path']
media_type = config['media_type']

# === LOGGING ===
logging.basicConfig(
    filename='send_log.txt',
    encoding='utf-8',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Clean up old log file if it exists and is older than LOG_MAX_AGE_DAYS
LOG_FILE = 'send_log.txt'
LOG_MAX_AGE_DAYS = 14  # 2 weeks

def clean_old_log():
    if os.path.exists(LOG_FILE):
        file_age_days = (time.time() - os.path.getmtime(LOG_FILE)) / 86400
        if file_age_days > LOG_MAX_AGE_DAYS:
            os.remove(LOG_FILE)
            print(f"🧹 Старый лог {LOG_FILE} удалён (был старше {LOG_MAX_AGE_DAYS} дней).")

clean_old_log()


# === LOAD CONTACTS ===
def load_contacts(filename='contacts.xlsx'):
    try:
        df = pd.read_excel(filename, header=0)
        header_exists = True
    except Exception:
        df = pd.read_excel(filename, header=None)
        header_exists = False

    possible_cols = ['tg', 'tg_id', 'username', 'tg_username', 'telegram']
    if header_exists:
        found_col = None
        for col in df.columns:
            if str(col).strip().lower() in possible_cols:
                found_col = col
                break
        if found_col is None:
            raise ValueError("Не найдено колонок с username (tg/tg_id/username...)")
        df = df.rename(columns={found_col: 'tg_username'})
    else:
        df.columns = ['tg_username']
        
    # name stripping and cleaning: remove leading/trailing spaces, @, and t.me links
    df['tg_username'] = (
        df['tg_username']
        .astype(str)
        .str.strip()
        .str.replace(r'^https?://t\.me/', '', regex=True)
        .str.replace(r'^t\.me/', '', regex=True)
        .str.replace(r'^@', '', regex=True)
    )
    # remove duplicates based on 'tg_username'
    df['tg_username'] = df['tg_username'].str.lower()
    df.drop_duplicates(subset='tg_username', keep='first', inplace=True)
    
    # sent column handling
    if 'sent' not in df.columns:
        df['sent'] = 'no'
    else:
        df['sent'] = df['sent'].fillna('no')
    # error column handling
    if 'error' not in df.columns:
        df['error'] = ''
    else:
        df['error'] = df['error'].fillna('')

    return df

def _get_html_message(message_file):
    with open(message_file, 'r', encoding='utf-8') as f:
        html_message = f.read()
    return html_message

def _get_md_message(message_file):
    with open(message_file, 'r', encoding='utf-8') as f:
        md_message = f.read()

    html_message = md_to_html(md_message)

    def clean_html_for_telegram(html):
        html = re.sub(r'<h[1-6]>(.*?)</h[1-6]>', r'<b>\1</b>', html)
        html = re.sub(r'<p>(.*?)</p>', r'\1<br>', html)
        html = re.sub(r'<ul>', '', html)
        html = re.sub(r'</ul>', '', html)
        html = re.sub(r'<li>', '• ', html)
        html = re.sub(r'</li>', '<br>', html)
        html = re.sub(r'<blockquote>(.*?)</blockquote>', r'\n<blockquote>\1</blockquote>', html)
        return html

    html_message = clean_html_for_telegram(html_message)
    return html_message

# === GET MESSAGE ===
def get_message(message_file):
    '''
    Reads message file (markdown or html) and returns clean HTML for sending.
    '''
    if message_file.endswith('.html'):
        return _get_html_message(message_file)
    elif message_file.endswith('.md'):
        return _get_md_message(message_file)
    else:
        try:
            return _get_md_message(message_file)
        except:
            raise Exception('Wrong message file type. Try .html or .md file')

# === MAIN LOGIC ===
async def main(contacts_file, message_file, limit, delay):
    client = TelegramClient(session_name, API_ID, API_HASH)
    await client.start()

    message = get_message(message_file)
    df = load_contacts(contacts_file)
    unsent = df[df['sent'].str.lower() == 'no']

    sent = 0
    for idx, row in unsent.iterrows():
        if sent >= limit:
            logging.info(f"✅ Достигнут лимит {limit} сообщений.")
            break

        username = str(row['tg_username']).lstrip('@').strip()
        try:
            logging.info(f"📨 Отправка @{username}")
            entity = await client.get_entity(username)
            
            if media_path and os.path.exists(media_path):
                file = media_path
                if media_type == "photo":
                    await client.send_file(entity, file, caption=message, parse_mode='html')
                elif media_type == "document":
                    await client.send_file(entity, file, caption=message, parse_mode='html', force_document=True)
                else:
                    await client.send_message(entity, message, parse_mode='html')
            else:
                await client.send_message(entity, message, parse_mode='html')

            df.at[idx, 'sent'] = 'yes'
            sent += 1
            logging.info(f"✅ Успешно отправлено ({sent}): @{username}")
        except PeerFloodError:
            logging.warning("🚫 PeerFloodError: Telegram ограничил отправку. Завершение.")
            break
        except UserPrivacyRestrictedError:
            logging.warning(f"🔒 Пользователь @{username} ограничил входящие.")
            df.at[idx, 'error'] = 'privacy_restricted'
        except FloodWaitError as e:
            wait_seconds = e.seconds
            logging.warning(f'⏳ FloodWait: ждём {wait_seconds} секунд...')
            await asyncio.sleep(wait_seconds)
            continue  # пробуем снова после паузы
        except RPCError as e:
            if 'PRIVACY_PREMIUM_REQUIRED' in str(e):
                logging.warning(f"🚫 @{username} требует Telegram Premium для получения сообщений.")
                df.at[idx, 'error'] = 'premium_required'
            else:
                logging.error(f"❌ RPCError @{username}: {e}")
                df.at[idx, 'error'] = str(e)
        except Exception as e:
            err_msg = str(e)
            if 'USERNAME_NOT_OCCUPIED' in err_msg or 'UsernameNotOccupied' in err_msg:
                logging.warning(f"❌ Username @{username} не существует.")
                df.at[idx, 'error'] = 'not_found'
            else:
                logging.error(f"❌ Ошибка @{username}: {err_msg}")
                df.at[idx, 'error'] = err_msg

        time.sleep(delay)

    await client.disconnect()
    df.to_excel('output_' + contacts_file, index=False)
    logging.info(f"📁 Файл контактов сохранён в {'output_' + contacts_file}")

    with open("report_ready.flag", "w") as f:
        f.write("done")
        
# === ARGPARSE ===
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Telegram message sender")
    parser.add_argument('--contacts', type=str, default=contacts_file, help='Excel file with contacts')
    parser.add_argument('--message', type=str, default=message_file, help='Markdown message file')
    parser.add_argument('--limit', type=int, default=max_messages_per_day, help='Max messages per session')
    parser.add_argument('--delay', type=int, default=delay_seconds, help='Delay between messages (seconds)')

    args = parser.parse_args()
    asyncio.run(main(args.contacts, args.message, args.limit, args.delay))