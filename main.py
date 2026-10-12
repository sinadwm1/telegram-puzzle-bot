import os
import sqlite3
import logging
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ForceReply
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters
)

# Constants
DB_NAME = 'puzzle_bot.db'
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")

# Admin Panel States
ADMIN_MAIN, ADD_STAGE_NUMBER, ADD_STAGE_QUESTION, ADD_STAGE_SUCCESS, \
EDIT_STAGE_SELECT, EDIT_STAGE_CHOICE, EDIT_STAGE_SAVE, \
DELETE_STAGE_SELECT, DELETE_STAGE_CONFIRM, \
MANAGE_USER_SELECT, MANAGE_USER_ACTION = range(11)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Keyboard for users
USER_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🔍 پروفایل", "🆘 درخواست راهنمایی"]
    ],
    resize_keyboard=True
)

# Database setup
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Create tables
    c.execute('''CREATE TABLE IF NOT EXISTS puzzles (
                 id INTEGER PRIMARY KEY,
                 stage INTEGER NOT NULL UNIQUE,
                 question TEXT NOT NULL,
                 success_text TEXT NOT NULL)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                 chat_id INTEGER PRIMARY KEY,
                 current_stage INTEGER DEFAULT 1,
                 lives INTEGER DEFAULT 3)''')
    
    # Insert initial data - استفاده از REPLACE برای جلوگیری از خطای مراحل تکراری
    c.execute('''REPLACE INTO puzzles (stage, question, success_text) 
                 VALUES (1, 'به اولین مرحله خوش آمدید! پاسخ شما چیست؟', 'تبریک! مرحله اول را کامل کردید!')''')
    
    conn.commit()
    conn.close()

# Database helper functions
def get_db_connection():
    return sqlite3.connect(DB_NAME)

def get_user(chat_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_all_users():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users")
    users = c.fetchall()
    conn.close()
    return users

def update_user(chat_id, current_stage=None, lives=None):
    conn = get_db_connection()
    c = conn.cursor()
    if current_stage is not None:
        c.execute("UPDATE users SET current_stage = ? WHERE chat_id = ?", 
                 (current_stage, chat_id))
    if lives is not None:
        c.execute("UPDATE users SET lives = ? WHERE chat_id = ?", 
                 (lives, chat_id))
    conn.commit()
    conn.close()

def create_user(chat_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (chat_id) VALUES (?)", (chat_id,))
    conn.commit()
    conn.close()

def get_puzzle(stage):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM puzzles WHERE stage = ?", (stage,))
    puzzle = c.fetchone()
    conn.close()
    return puzzle

def get_all_puzzles():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT stage FROM puzzles ORDER BY stage")
    puzzles = c.fetchall()
    conn.close()
    return puzzles

def get_max_stage():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT MAX(stage) FROM puzzles")
    max_stage = c.fetchone()[0]
    conn.close()
    return max_stage or 0

def add_puzzle(stage, question, success_text):
    conn = get_db_connection()
    c = conn.cursor()
    
    # جایگزینی INSERT با REPLACE برای حل مشکل مراحل تکراری
    c.execute('''REPLACE INTO puzzles (stage, question, success_text)
                 VALUES (?, ?, ?)''',
             (stage, question, success_text))
    
    conn.commit()
    conn.close()

def update_puzzle(stage, question=None, success_text=None):
    conn = get_db_connection()
    c = conn.cursor()
    
    if question and success_text:
        c.execute('''UPDATE puzzles 
                     SET question = ?, success_text = ?
                     WHERE stage = ?''',
                 (question, success_text, stage))
    elif question:
        c.execute('''UPDATE puzzles 
                     SET question = ?
                     WHERE stage = ?''',
                 (question, stage))
    elif success_text:
        c.execute('''UPDATE puzzles 
                     SET success_text = ?
                     WHERE stage = ?''',
                 (success_text, stage))
    
    conn.commit()
    conn.close()

def delete_puzzle(stage):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM puzzles WHERE stage=?", (stage,))
    conn.commit()
    conn.close()

# =====================
# USER-FACING FUNCTIONS
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if chat_id == ADMIN_CHAT_ID:
        await context.bot.send_message(
            chat_id=chat_id,
            text="👑 به پنل مدیریت خوش آمدید. برای دسترسی به منوی ادمین از /admin استفاده کنید."
        )
        return
    
    create_user(chat_id)
    
    # متن خوش‌آمدگویی جدید
    welcome_text = (
        "🎉 سلام عزیزم، ماهگردمون مبارک!\n\n"
        "این بازی هدیه ویژه‌ای از طرف من به توست. قراره با هم مراحل و معماها رو حل کنیم "
        "تا به پایان برسیم. یادت نره که هدیه اصلی خود مسیر بازیه، پس از هر لحظه‌اش لذت ببر!\n\n"
        "🔸 تو این بازی ۳ جان داری\n"
        "🔸 هر بار که پاسخ اشتباه بدی، یک جون از دست میدی\n"
        "🔸 اگه جونت تموم بشه، بازی از اول شروع میشه\n\n"
        "حالا آماده‌ای که شروع کنیم؟"
    )
    
    # دکمه شروع
    keyboard = [[KeyboardButton("🚀 بزن بریم!")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=welcome_text,
        reply_markup=reply_markup
    )

async def send_puzzle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if chat_id == ADMIN_CHAT_ID:
        return
    
    user = get_user(chat_id)
    
    if not user:
        await start(update, context)
        return
    
    stage = user[1]
    puzzle = get_puzzle(stage)
    
    if not puzzle:
        await update.message.reply_text("⛔ پازلی برای این مرحله یافت نشد.")
        return
    
    question = puzzle[2]
    caption = f"مرحله {stage}"
    reply_markup = ForceReply(input_field_placeholder="✏️ پاسخ خود را وارد کنید...")
    
    if question.startswith(('http://', 'https://')):
        if any(ext in question.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            await context.bot.send_photo(chat_id, photo=question, caption=caption, reply_markup=reply_markup)
            await context.bot.send_message(chat_id, "از دکمه‌های زیر استفاده کن:", reply_markup=USER_KEYBOARD)
        elif any(ext in question.lower() for ext in ['.mp4', '.mov']):
            await context.bot.send_video(chat_id, video=question, caption=caption, reply_markup=reply_markup)
            await context.bot.send_message(chat_id, "از دکمه‌های زیر استفاده کن:", reply_markup=USER_KEYBOARD)
        else:
            await context.bot.send_message(chat_id, text=f"{caption}\n\n{question}", reply_markup=reply_markup)
            await context.bot.send_message(chat_id, "از دکمه‌های زیر استفاده کن:", reply_markup=USER_KEYBOARD)
    else:
        await context.bot.send_message(chat_id, text=f"{caption}\n\n{question}", reply_markup=reply_markup)
        await context.bot.send_message(chat_id, "از دکمه‌های زیر استفاده کن:", reply_markup=USER_KEYBOARD)

async def handle_text_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id == ADMIN_CHAT_ID:
        return
        
    user = get_user(update.effective_user.id)
    stage = user[1]
    answer = update.message.text
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تأیید", callback_data=f"rev_approve_{update.effective_user.id}_{stage}"),
            InlineKeyboardButton("❌ رد", callback_data=f"rev_reject_{update.effective_user.id}_{stage}")
        ],
        [
            InlineKeyboardButton("🔄 تلاش مجدد", callback_data=f"rev_retry_{update.effective_user.id}_{stage}")
        ]
    ])
    
    await context.bot.send_message(
        ADMIN_CHAT_ID,
        f"📩 پاسخ جدید از کاربر {update.effective_user.id} (مرحله {stage}):\n\n{answer}",
        reply_markup=keyboard
    )
    
    await update.message.reply_text("🔄 پاسخ شما برای بررسی به ادمین ارسال شد. منتظر نتیجه باشید...")

async def handle_admin_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split('_')
    action = parts[1]
    user_id = int(parts[2])
    stage = int(parts[3])
    
    puzzle = get_puzzle(stage)
    success_text = puzzle[3]
    
    if action == 'approve':
        max_stage = get_max_stage()
        new_stage = stage + 1
        
        if new_stage > max_stage:
            await context.bot.send_message(user_id, f"🎉 تبریک! شما بازی را به پایان رساندید!\n\n{success_text}")
        else:
            update_user(user_id, current_stage=new_stage)
            await context.bot.send_message(user_id, f"✅ پاسخ شما تأیید شد!\n\n{success_text}\n\nدر حال انتقال به مرحله بعد...")
            await send_puzzle_for_user(context, user_id, new_stage)
        
        await query.edit_message_text(f"✅ پاسخ کاربر {user_id} تایید شد. به مرحله {new_stage} منتقل شد.")
        
    elif action == 'reject':
        user = get_user(user_id)
        new_lives = user[2] - 1
        
        if new_lives <= 0:
            update_user(user_id, current_stage=1, lives=0)
            await context.bot.send_message(user_id, "💀 بازی تمام شد! تمام جان‌های شما تمام شده است.\nبرای شروع مجدد /start را بزنید.")
            await query.edit_message_text(f"❌ کاربر {user_id} بازی را باخت.")
        else:
            update_user(user_id, current_stage=1, lives=new_lives)
            await context.bot.send_message(user_id, f"❌ پاسخ نادرست بود! شما به مرحله اول بازگشتید.\nجان‌های باقی‌مانده: {new_lives}")
            await query.edit_message_text(f"❌ پاسخ کاربر {user_id} رد شد. جان‌های باقی‌مانده: {new_lives}")
            await send_puzzle_for_user(context, user_id, 1)
            
    elif action == 'retry':
        await context.bot.send_message(
            user_id,
            "⚠️ پاسخ شما تأیید نشد، اما می‌توانید دوباره تلاش کنید!\n\n"
            "لطفاً پاسخ خود را اصلاح کرده و دوباره ارسال کنید."
        )
        await send_puzzle_for_user(context, user_id, stage)
        await query.edit_message_text(f"🔄 کاربر {user_id} می‌تواند دوباره برای مرحله {stage} تلاش کند.")

async def send_puzzle_for_user(context, user_id, stage):
    puzzle = get_puzzle(stage)
    
    if not puzzle:
        await context.bot.send_message(user_id, "⛔ پازلی برای این مرحله یافت نشد. لطفاً با ادمین تماس بگیرید.")
        return
    
    question = puzzle[2]
    caption = f"مرحله {stage}"
    reply_markup = ForceReply(input_field_placeholder="✏️ پاسخ خود را وارد کنید...")
    
    if question.startswith(('http://', 'https://')):
        if any(ext in question.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            await context.bot.send_photo(user_id, photo=question, caption=caption, reply_markup=reply_markup)
            await context.bot.send_message(user_id, "از دکمه‌های زیر استفاده کن:", reply_markup=USER_KEYBOARD)
        elif any(ext in question.lower() for ext in ['.mp4', '.mov']):
            await context.bot.send_video(user_id, video=question, caption=caption, reply_markup=reply_markup)
            await context.bot.send_message(user_id, "از دکمه‌های زیر استفاده کن:", reply_markup=USER_KEYBOARD)
        else:
            await context.bot.send_message(user_id, text=f"{caption}\n\n{question}", reply_markup=reply_markup)
            await context.bot.send_message(user_id, "از دکمه‌های زیر استفاده کن:", reply_markup=USER_KEYBOARD)
    else:
        await context.bot.send_message(user_id, text=f"{caption}\n\n{question}", reply_markup=reply_markup)
        await context.bot.send_message(user_id, "از دکمه‌های زیر استفاده کن:", reply_markup=USER_KEYBOARD)

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id == ADMIN_CHAT_ID:
        return
        
    user = get_user(update.effective_chat.id)
    if user:
        stage = user[1]
        lives = user[2]
        max_stage = get_max_stage()
        
        progress = int((stage / max_stage) * 10) if max_stage > 0 else 0
        progress_bar = "🟩" * progress + "⬜" * (10 - progress)
        
        text = (
            f"👤 پروفایل کاربری\n\n"
            f"🔹 مرحله فعلی: {stage} از {max_stage}\n"
            f"🔹 جان‌های باقی‌مانده: {lives}\n\n"
            f"📊 پیشرفت: {progress_bar} {progress*10}%\n\n"
            "برای بازگشت به بازی از دکمه‌های زیر استفاده کنید:"
        )
        await update.message.reply_text(text, reply_markup=USER_KEYBOARD)

async def handle_help_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_user(chat_id)
    
    # ارسال لینک مستقیم به ادمین بدون انجام عملیات دیگر
    admin_link = f"https://t.me/{ADMIN_USERNAME}"
    text = (
        "🆘 برای دریافت راهنمایی مستقیم، لطفاً از طریق لینک زیر با ادمین تماس بگیرید:\n\n"
        f"👉 [تماس با ادمین]({admin_link})"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=USER_KEYBOARD,
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

# ===================
# ADMIN PANEL SYSTEM
# ===================
def admin_only(func):
    async def wrapper(update, context):
        if update.effective_chat.id == ADMIN_CHAT_ID:
            return await func(update, context)
        else:
            await update.message.reply_text("⛔ فقط ادمین مجاز به استفاده از این دستور است.")
    return wrapper

@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ افزودن مرحله", callback_data="admin_add_stage")],
        [InlineKeyboardButton("✏️ ویرایش مرحله", callback_data="admin_edit_stage")],
        [InlineKeyboardButton("🗑️ حذف مرحله", callback_data="admin_delete_stage")],
        [InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin_manage_users")],
        [InlineKeyboardButton("❌ بستن پنل", callback_data="admin_close")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text("👑 پنل مدیریت ادمین", reply_markup=reply_markup)
    else:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("👑 پنل مدیریت ادمین", reply_markup=reply_markup)
    
    return ADMIN_MAIN

@admin_only
async def admin_manage_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    users = get_all_users()
    if not users:
        await query.edit_message_text("ℹ️ هیچ کاربری وجود ندارد.")
        return ADMIN_MAIN
    
    buttons = []
    for user in users:
        buttons.append([
            InlineKeyboardButton(
                f"👤 کاربر {user[0]} (مرحله {user[1]}, جان‌ها: {user[2]})", 
                callback_data=f"manage_user_{user[0]}"
            )
        ])
    
    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")])
    
    await query.edit_message_text(
        "👥 انتخاب کاربر برای مدیریت:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return MANAGE_USER_SELECT

@admin_only
async def manage_user_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split('_')[2])
    context.user_data['managed_user'] = user_id
    
    user = get_user(user_id)
    
    buttons = [
        [InlineKeyboardButton("➕ افزودن جان", callback_data="user_add_life")],
        [InlineKeyboardButton("➖ کسر جان", callback_data="user_remove_life")],
        [InlineKeyboardButton("🔄 بازنشانی مرحله", callback_data="user_reset_stage")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]
    ]
    
    await query.edit_message_text(
        f"👤 مدیریت کاربر {user_id}\n"
        f"🔹 مرحله فعلی: {user[1]}\n"
        f"🔹 جان‌های باقی‌مانده: {user[2]}\n\n"
        "لطفاً عمل مورد نظر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return MANAGE_USER_ACTION

@admin_only
async def manage_user_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action = query.data
    user_id = context.user_data['managed_user']
    user = get_user(user_id)
    
    if action == 'user_add_life':
        new_lives = user[2] + 1
        update_user(user_id, lives=new_lives)
        text = f"✅ یک جان به کاربر {user_id} اضافه شد.\nجان‌های جدید: {new_lives}"
    
    elif action == 'user_remove_life':
        new_lives = max(0, user[2] - 1)
        update_user(user_id, lives=new_lives)
        text = f"⚠️ یک جان از کاربر {user_id} کسر شد.\nجان‌های جدید: {new_lives}"
    
    elif action == 'user_reset_stage':
        update_user(user_id, current_stage=1)
        text = f"🔄 مرحله کاربر {user_id} به 1 بازنشانی شد."
    
    await query.edit_message_text(text)
    await context.bot.send_message(
        user_id,
        "🔔 وضعیت حساب شما توسط ادمین به‌روزرسانی شد! لطفاً پروفایل خود را بررسی کنید."
    )
    return await admin_panel(update, context)

@admin_only
async def add_stage_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔢 لطفاً شماره مرحله جدید را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]])
    )
    return ADD_STAGE_NUMBER

@admin_only
async def add_stage_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        stage = int(update.message.text)
        
        # Validate stage number
        if stage <= 0:
            await update.message.reply_text("⚠️ شماره مرحله باید بزرگتر از صفر باشد. لطفاً دوباره وارد کنید:")
            return ADD_STAGE_NUMBER
            
        context.user_data['stage'] = stage
        
        # Check if stage exists
        puzzle = get_puzzle(stage)
        message = "❓ لطفاً سوال/معمای مرحله را وارد کنید (متن یا لینک عکس/فیلم):"
        
        if puzzle:
            message = f"⚠️ مرحله {stage} از قبل وجود دارد. محتوای آن جایگزین خواهد شد.\n\n" + message
            
        await update.message.reply_text(message)
        return ADD_STAGE_QUESTION
    except ValueError:
        await update.message.reply_text("⚠️ لطفاً یک عدد صحیح وارد کنید:")
        return ADD_STAGE_NUMBER

@admin_only
async def add_stage_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['question'] = update.message.text
    await update.message.reply_text("🎉 لطفاً متن تبریک پس از حل مرحله را وارد کنید:")
    return ADD_STAGE_SUCCESS

@admin_only
async def add_stage_success(update: Update, context: ContextTypes.DEFAULT_TYPE):
    success_text = update.message.text
    stage = context.user_data['stage']
    question = context.user_data['question']
    
    add_puzzle(stage, question, success_text)
    await update.message.reply_text(f"✅ مرحله {stage} با موفقیت اضافه شد!")
    return await admin_panel(update, context)

@admin_only
async def edit_stage_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    puzzles = get_all_puzzles()
    if not puzzles:
        await query.edit_message_text("ℹ️ هیچ مرحله‌ای برای ویرایش وجود ندارد.")
        return ADMIN_MAIN
    
    text = "✏️ انتخاب مرحله برای ویرایش:\n\n"
    for (stage,) in puzzles:
        text += f"🔹 مرحله {stage}\n"
    
    text += "\n🔢 لطفاً شماره مرحله را وارد کنید:"
    await query.edit_message_text(text)
    return EDIT_STAGE_SELECT

@admin_only
async def edit_stage_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        stage = int(update.message.text)
        puzzle = get_puzzle(stage)
        
        if not puzzle:
            await update.message.reply_text(f"⛔ مرحله {stage} یافت نشد! لطفاً شماره مرحله معتبر وارد کنید:")
            return EDIT_STAGE_SELECT
        
        context.user_data['stage'] = stage
        
        keyboard = [
            [InlineKeyboardButton("✏️ ویرایش سوال", callback_data="edit_question")],
            [InlineKeyboardButton("🎉 ویرایش متن تبریک", callback_data="edit_success")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]
        ]
        
        await update.message.reply_text(
            f"✏️ ویرایش مرحله {stage}:\n\n"
            f"1. سوال: {puzzle[2]}\n"
            f"2. متن تبریک: {puzzle[3]}\n\n"
            "لطفاً گزینه مورد نظر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return EDIT_STAGE_CHOICE
    except ValueError:
        await update.message.reply_text("⚠️ لطفاً یک عدد صحیح وارد کنید:")
        return EDIT_STAGE_SELECT

@admin_only
async def edit_stage_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    choice = query.data
    stage = context.user_data['stage']
    
    if choice == 'edit_question':
        await query.edit_message_text("❓ لطفاً سوال/معمای جدید را وارد کنید (متن یا لینک عكس/فيل):")
        context.user_data['edit_type'] = 'question'
    elif choice == 'edit_success':
        await query.edit_message_text("🎉 لطفاً متن تبریک جدید را وارد کنید:")
        context.user_data['edit_type'] = 'success'
    
    return EDIT_STAGE_SAVE

@admin_only
async def save_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stage = context.user_data['stage']
    edit_type = context.user_data['edit_type']
    new_value = update.message.text
    
    if edit_type == 'question':
        update_puzzle(stage, question=new_value)
    elif edit_type == 'success':
        update_puzzle(stage, success_text=new_value)
    
    await update.message.reply_text(f"✅ تغییرات مرحله {stage} با موفقیت ذخیره شد!")
    return await admin_panel(update, context)

@admin_only
async def delete_stage_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    puzzles = get_all_puzzles()
    if not puzzles:
        await query.edit_message_text("ℹ️ هیچ مرحله‌ای برای حذف وجود ندارد.")
        return ADMIN_MAIN
    
    text = "🗑️ انتخاب مرحله برای حذف:\n\n"
    for (stage,) in puzzles:
        text += f"🔹 مرحله {stage}\n"
    
    text += "\n🔢 لطفاً شماره مرحله را وارد کنید:"
    await query.edit_message_text(text)
    return DELETE_STAGE_SELECT

@admin_only
async def delete_stage_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        stage = int(update.message.text)
        puzzle = get_puzzle(stage)
        
        if not puzzle:
            await update.message.reply_text(f"⛔ مرحله {stage} یافت نشد! لطفاً دوباره وارد کنید:")
            return DELETE_STAGE_SELECT
        
        context.user_data['stage'] = stage
        
        keyboard = [
            [InlineKeyboardButton("✅ بله، حذف شود", callback_data=f"confirm_delete_{stage}")],
            [InlineKeyboardButton("❌ خیر، انصراف", callback_data="admin_back")]
        ]
        
        await update.message.reply_text(
            f"⚠️ آیا مطمئن هستید که می‌خواهید مرحله {stage} را حذف کنید؟",
            reply_markup=InlineKeyboardMarkup(keyboard))
        return DELETE_STAGE_CONFIRM
    except ValueError:
        await update.message.reply_text("⚠️ لطفاً یک عدد صحیح وارد کنید:")
        return DELETE_STAGE_SELECT

@admin_only
async def delete_stage_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    stage = int(query.data.split('_')[2])
    delete_puzzle(stage)
    await query.edit_message_text(f"✅ مرحله {stage} با موفقیت حذف شد!")
    return await admin_panel(update, context)

@admin_only
async def back_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await admin_panel(update, context)

@admin_only
async def close_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("👋 پنل ادمین بسته شد.")
    return ConversationHandler.END

# =====================
# MAIN BOT SETUP
# =====================
def main():
    if not BOT_TOKEN or ADMIN_CHAT_ID <= 0:
        raise RuntimeError("Set BOT_TOKEN and ADMIN_CHAT_ID before starting the bot.")
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()
    non_admin_filter = ~filters.Chat(ADMIN_CHAT_ID)
    
    # User commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("^🚀 بزن بریم!$") & non_admin_filter, send_puzzle))
    application.add_handler(MessageHandler(filters.Regex("^🔍 پروفایل$") & non_admin_filter, show_profile))
    application.add_handler(MessageHandler(filters.Regex("^🆘 درخواست راهنمایی$") & non_admin_filter, handle_help_request))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & non_admin_filter, handle_text_answer))
    application.add_handler(CallbackQueryHandler(handle_admin_review, pattern=r"^rev_\w+_\d+_\d+$"))
    
    # Admin conversation handler
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler('admin', admin_panel)],
        states={
            ADMIN_MAIN: [
                CallbackQueryHandler(admin_manage_users, pattern='^admin_manage_users$'),
                CallbackQueryHandler(add_stage_start, pattern='^admin_add_stage$'),
                CallbackQueryHandler(edit_stage_start, pattern='^admin_edit_stage$'),
                CallbackQueryHandler(delete_stage_start, pattern='^admin_delete_stage$'),
                CallbackQueryHandler(close_admin, pattern='^admin_close$'),
                CallbackQueryHandler(back_to_admin, pattern='^admin_back$')
            ],
            
            ADD_STAGE_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_stage_number),
                CallbackQueryHandler(back_to_admin, pattern='^admin_back$')
            ],
            
            ADD_STAGE_QUESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_stage_question),
                CallbackQueryHandler(back_to_admin, pattern='^admin_back$')
            ],
            
            ADD_STAGE_SUCCESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_stage_success),
                CallbackQueryHandler(back_to_admin, pattern='^admin_back$')
            ],
            
            EDIT_STAGE_SELECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_stage_select),
                CallbackQueryHandler(back_to_admin, pattern='^admin_back$')
            ],
            
            EDIT_STAGE_CHOICE: [
                CallbackQueryHandler(edit_stage_choice, pattern=r"^(edit_question|edit_success)$"),
                CallbackQueryHandler(back_to_admin, pattern='^admin_back$')
            ],
            
            EDIT_STAGE_SAVE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_edit),
                CallbackQueryHandler(back_to_admin, pattern='^admin_back$')
            ],
            
            DELETE_STAGE_SELECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, delete_stage_select),
                CallbackQueryHandler(back_to_admin, pattern='^admin_back$')
            ],
            
            DELETE_STAGE_CONFIRM: [
                CallbackQueryHandler(delete_stage_execute, pattern=r"^confirm_delete_\d+$"),
                CallbackQueryHandler(back_to_admin, pattern='^admin_back$')
            ],
            
            MANAGE_USER_SELECT: [
                CallbackQueryHandler(manage_user_selected, pattern=r"^manage_user_\d+$"),
                CallbackQueryHandler(back_to_admin, pattern='^admin_back$')
            ],
            
            MANAGE_USER_ACTION: [
                CallbackQueryHandler(manage_user_action, pattern=r"^(user_add_life|user_remove_life|user_reset_stage)$"),
                CallbackQueryHandler(back_to_admin, pattern='^admin_back$')
            ]
        },
        fallbacks=[CommandHandler('admin', admin_panel)],
        per_message=False
    )
    
    application.add_handler(admin_conv)
    application.run_polling()

if __name__ == '__main__':
    main()
    
    
    
    
# done ;)
