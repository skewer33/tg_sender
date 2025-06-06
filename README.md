## About the project
A project to automate mailings from a telegram account using a tg bot as a UI

## Project capabilities

This project includes a Telegram bot on `aiogram` and a script for sending messages via Telethon. It allows you to:

- Accept a list of recipients (usernames or Excel file)

- Accept the text of the mailing in Markdown or HTML format

- Attach media (photos or documents)

- Send a mailing from a Telegram account

- Show a delivery report

## Operating principle

1) Send the bot a list of contacts for the mailing

2) Send the bot the text of the message (you can also attach 1 file or 1 picture)

3) The bot will launch the mailing script

4) Upon completion, you will receive a file with a list of who received the message

  
  

## Installation

1. Clone the repository:

```bash
git clone https://github.com/skewer33/tg_sender.git
cd tg_sender
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Create .env file
Put into ```.env``` file:
- [sender account API](https://core.telegram.org/api/obtaining_api_id) - this account will be used for sending out emails.
- [BOT_TOKEN](https://core.telegram.org/bots/tutorial) - needed to run your bot

```env
API_ID=your_telegram_api_id

API_HASH=your_telegram_api_hash

BOT_TOKEN=your_bot_token
```

4. Run the script 'telegram_sender.py' and confirm the login to telegram
```'telegram_sender.py'``` uses the ```telethon``` library. To enable it to send messages on behalf of your account, you need to enter a confirmation code in the console
```bash
python telegram_sender.py
```
INSERT THE CONFIRMATION CODE FROM TELEGRAM INTO THE CONSOLE

5. Add your Telegram ID to authorized_users.txt to have access to the bot
If you don't know your Telegram ID, write to the bot /start , it will tell you

6. Launch the bot
```bash
python bot_dispatcher.py
```
## Bot species
### Contacts format

You can send contacts both in text and in an xml file
-  Sending text
	Just write the bot a list of contacts at its request. Example:

```telegram
user1
@user2
t.me/user3
```

- Sending a '.xlsx' file

	The file must contain the columns:

|tg_usermane|sent|
| ------ | ------ |
|user1|yes|
|user2|no|
|user3|no|

In that case script will send only for users with "sent == no" status

### Message format

The messages support all Telegram styles: italics, bold, spoilers, quotes, etc.
An html file is used for interaction between the bot and the script.

### Config

The config is needed for interaction between the bot and the script
Contains the following parameters
  
```session_name``` - session name

```message_file```  - path to message file in markdown or html format

```contacts_file``` - contacts.xlsx # path to contacts file

```max_messages_per_day``` - how many users per day you can send messages. It doesn't work yet. But I don't recommend setting a large value (>150) to avoid a ban

```delay_seconds``` - delay between sending each message

```media_path``` - dont touch it. It's for bot-script communication

```media_type``` - dont touch it. It's for bot-script communication

```downloads_dir``` - directory for saving media files