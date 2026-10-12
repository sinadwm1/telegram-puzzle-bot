# Telegram Puzzle Bot

[راهنمای فارسی](README_FA.md)

A configurable Telegram puzzle bot with staged questions, player progress, lives, help requests, and an admin flow for editing stages and reviewing answers. The application stores its data in local SQLite.

## Stack

Python, `python-telegram-bot`, SQLite.

## Setup

1. Create a **new** Telegram bot token. Tokens embedded in the original local source must be revoked before this code is used.
2. Set `BOT_TOKEN`, `ADMIN_CHAT_ID`, and `ADMIN_USERNAME` as environment variables. `.env.example` lists the required names; the script reads process environment variables and does not load `.env` automatically.
3. Run:

```bash
pip install -r requirements.txt
python main.py
```

Send `/start` as a player. The configured administrator can use `/admin` to manage stages and users. The SQLite file is created locally and is intentionally not included in this draft.

## Privacy and limitations

The original bot database, log, and personal photo are not part of this draft. The bot has not been tested with a live Telegram token during preparation. Use a dedicated bot and inspect its administrator permissions before deployment. Released under the MIT License.
