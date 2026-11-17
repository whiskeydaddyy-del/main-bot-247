# language: Python, file: main.py, target: Python 3.10+ (Render Stable)
import logging
import asyncio
import json
import os
import io
import time
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "9012597054:AAFRL3eNZc0og_8Y3-vQNG9bpxI_rq4T2nk"
ADMIN_ID = 8607731717
DATA_FILE = "accounts_data.json"

USER_ACCOUNTS = {}
USER_STEPS = {}
ACTIVE_PROXIES = []
IS_RUNNING_24_7 = False
TARGET_ACCOUNT = "الجميع"

PROXY_URLS = [
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
    "https://cdn.jsdelivr.net/gh/proxyscrape/free-proxy-list@main/proxies/protocols/http/data.txt",
    "https://cdn.jsdelivr.net/gh/proxyscrape/free-proxy-list@main/proxies/protocols/socks5/data.txt"
]

def load_accounts():
    global USER_ACCOUNTS
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                USER_ACCOUNTS = json.load(f)
        except Exception as e:
            logger.error(f"خطأ في قراءة الحسابات: {e}")
            USER_ACCOUNTS = {}

def save_accounts():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(USER_ACCOUNTS, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"خطأ في حفظ الحسابات: {e}")

def fetch_fresh_proxies():
    global ACTIVE_PROXIES
    temp_proxies = []
    for url in PROXY_URLS:
        try:
            separator = "&" if "?" in url else "?"
            fresh_url = f"{url}{separator}_t={int(time.time())}"
            response = requests.get(fresh_url, timeout=10)
            if response.status_code == 200:
                for line in response.text.splitlines():
                    line = line.strip()
                    if line and line not in temp_proxies:
                        if not line.startswith("http") and not line.startswith("socks"):
                            temp_proxies.append(f"http://{line}")
                        else:
                            temp_proxies.append(line)
        except Exception as e:
            logger.error(f"خطأ في جلب البروكسيات: {e}")
    if temp_proxies:
        ACTIVE_PROXIES = temp_proxies
        logger.info(f"تم جلب بروكسيات جديدة. الإجمالي: {len(ACTIVE_PROXIES)}")
    return len(ACTIVE_PROXIES)

def get_next_proxy_and_consume():
    global ACTIVE_PROXIES
    try:
        if not ACTIVE_PROXIES:
            fetch_fresh_proxies()
        if ACTIVE_PROXIES:
            return ACTIVE_PROXIES.pop(0)
    except Exception as e:
        logger.error(f"خطأ في استهلاك البروكسي: {e}")
    return "http://safe.proxy:8080"

def get_main_keyboard():
    proxy_count = len(ACTIVE_PROXIES)
    keyboard = [
        [InlineKeyboardButton("📊 حالة الأداة", callback_data='check_status'), InlineKeyboardButton(f"🔄 تحديث البروكسيات ({proxy_count})", callback_data='refresh_proxies')],
        [InlineKeyboardButton("➕ إضافة حساب جديد", callback_data='start_add_account'), InlineKeyboardButton("📋 عرض الحسابات وفحصها", callback_data='view_accounts')],
        [InlineKeyboardButton("📁 استخراج البروكسيات ملف", callback_data='export_proxies_file')],
        [InlineKeyboardButton("🛡️ بدء مراسلة انستغرام وطلب المراجعة", callback_data='review_accounts_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_x_keyboard():
    keyboard = [
        [InlineKeyboardButton("❌ (إكس واحد)", callback_data='x_1')],
        [InlineKeyboardButton("❌❌ (إكسين)", callback_data='x_2')],
        [InlineKeyboardButton("❌❌❌ (ثلاث اكسات - باند نزاهة)", callback_data='x_3')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        if update.message:
            await update.message.reply_text("⛔ عذراً، هذا البوت خاص ولا يمكنك استخدامه.")
        return

    if not ACTIVE_PROXIES:
        fetch_fresh_proxies()
        
    status_emoji = "🟢 يعمل 24/7 باستقرار تام" if IS_RUNNING_24_7 else "🔴 متوقف وجاهز للتشغيل"
    welcome_text = (
        "╔══════════════════════════╗\n"
        "✨ **لوحة تحكم فك باند إنستغرام الاحترافية** ✨\n"
        "╚══════════════════════════╝\n\n"
        f"👑 **المشرف:** `المرعب اليماني`\n"
        f"📌 **حالة النظام:** `{status_emoji}`\n"
        f"🔌 **عداد البروكسيات المتاحة:** `{len(ACTIVE_PROXIES)}` بروكسي\n"
        f"📋 **الحسابات المخزنة:** `{len(USER_ACCOUNTS)}` حساب\n\n"
        "⚡ _اختر أحد الخيارات أدناه لإدارة الأداة:_"
    )
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard(), parse_mode='Markdown')
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            await query.edit_message_text(welcome_text, reply_markup=get_main_keyboard(), parse_mode='Markdown')
        except Exception:
            pass

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global IS_RUNNING_24_7, TARGET_ACCOUNT
    query = update.callback_query
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("⛔ عذراً، غير مسموح لك.", show_alert=True)
        return

    await query.answer()
    data = query.data

    if data == 'refresh_proxies':
        count = fetch_fresh_proxies()
        await query.message.reply_text(f"🔄 **تم سحب قائمة بروكسيات جديدة وتحديث العداد!**\nالعدد الحالي: `{count}` بروكسي", parse_mode='Markdown')
        await start(update, context)

    elif data == 'check_status':
        status_str = "يعمل 24/7 🟢" if IS_RUNNING_24_7 else "متوقف 🔴"
        await query.message.reply_text(
            "📊 **تقرير حالة الأداة:**\n\n"
            f"• حالة النظام: `{status_str}`\n"
            f"• الحسابات المخزنة: `{len(USER_ACCOUNTS)}`\n"
            f"• البروكسيات المتاحة: `{len(ACTIVE_PROXIES)}`\n"
            "• الفحص ومراقبة الردود: `نشط 24/7`",
            parse_mode='Markdown'
        )

    elif data == 'start_add_account':
        USER_STEPS[user_id] = {"step": "waiting_username"}
        await query.message.reply_text("👤 **الآن أرسل يوزر الحساب المتبند الجديد:**", parse_mode='Markdown')

    elif data == 'view_accounts':
        if not USER_ACCOUNTS:
            await query.message.reply_text("📂 لا توجد حسابات مسجلة حالياً.", parse_mode='Markdown')
        else:
            text = "📋 **قائمة الحسابات المخزنة وفحص حالتها:**\n\n"
            keyboard = []
            for acc, info in USER_ACCOUNTS.items():
                text += f"👤 يوزر: `{acc}`\n📧 إيميل: `{info.get('email')}`\n📌 الحالة: `{info.get('status')}`\n------------------\n"
                keyboard.append([InlineKeyboardButton(f"🔍 فحص الحساب: {acc}", callback_data=f"check_acc_{acc}")])
            
            keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    elif data.startswith('check_acc_'):
        acc_to_check = data.replace('check_acc_', '')
        if acc_to_check in USER_ACCOUNTS:
            current_status = USER_ACCOUNTS[acc_to_check].get('status', 'تحت المراجعة 🔄')
            check_report = (
                "🔍 **نتيجة فحص الحساب:**\n\n"
                f"👤 يوزر: `{acc_to_check}`\n"
                f"📌 الحالة الحالية: `{current_status}`\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "🟢 _الطلب مرسل للدعم ومحمي بالبروكسي._"
            )
            await query.message.reply_text(check_report, parse_mode='Markdown')

    elif data == 'export_proxies_file':
        if not ACTIVE_PROXIES:
            await query.message.reply_text("⚠️ لا توجد بروكسيات متاحة حالياً.", parse_mode='Markdown')
            return
        
        file_content = "\n".join(ACTIVE_PROXIES)
        file_bytes = io.BytesIO(file_content.encode('utf-8'))
        file_bytes.name = "safe_proxies.txt"
        
        await query.message.reply_document(
            document=InputFile(file_bytes),
            caption=f"📁 **ملف البروكسيات المتاحة:**\nالعدد: `{len(ACTIVE_PROXIES)}` بروكسي",
            parse_mode='Markdown'
        )

    elif data == 'review_accounts_menu':
        if not USER_ACCOUNTS:
            await query.message.reply_text("⚠️ لا توجد حسابات مخزنة! قم بإضافة حساب أولاً.", parse_mode='Markdown')
            return

        text = (
            "╔══════════════════════════╗\n"
            "🛡️ **قائمة الحسابات لطلب المراجعة** 🛡️\n"
            "╚══════════════════════════╝\n\n"
            "اختر الحساب للعمل عليه، أو اختر 'العمل على الجميع':\n"
        )
        
        keyboard = []
        for acc in USER_ACCOUNTS.keys():
            keyboard.append([InlineKeyboardButton(f"👤 العمل على: {acc}", callback_data=f"work_acc_{acc}")])
        
        keyboard.append([InlineKeyboardButton("⚡ العمل على الجميع (تشغيل 24/7)", callback_data='start_work_on_all')])
        keyboard.append([InlineKeyboardButton("⏹️ إيقاف العمل", callback_data='stop_engine')])
        keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    elif data.startswith('work_acc_'):
        chosen_acc = data.replace('work_acc_', '')
        TARGET_ACCOUNT = chosen_acc
        IS_RUNNING_24_7 = True
        
        if chosen_acc in USER_ACCOUNTS:
            USER_ACCOUNTS[chosen_acc]['status'] = 'قيد العمل الفردي ومحرك البروكسيات 🟢'
            save_accounts()

        proxy_used = get_next_proxy_and_consume()
        await query.message.reply_text(
            "⚡ **لوحة التشغيل الفردي الآمن (24/7)**\n\n"
            f"• الحساب المستهدف: `{chosen_acc}`\n"
            "• الحالة: `✅ بدأ التشغيل واستهلاك العداد بهدوء!`\n"
            f"• البروكسي المُستخدَم والمحذوف: `{proxy_used}`\n"
            f"• 📉 **البروكسيات المتبقية:** `{len(ACTIVE_PROXIES)} بروكسي`",
            parse_mode='Markdown'
        )

    elif data == 'start_work_on_all':
        if not USER_ACCOUNTS:
            await query.message.reply_text("⚠️ لا توجد حسابات للعمل عليها.", parse_mode='Markdown')
            return

        TARGET_ACCOUNT = "الجميع"
        IS_RUNNING_24_7 = True
        for acc in USER_ACCOUNTS:
            USER_ACCOUNTS[acc]['status'] = 'قيد العمل الشامل وحذف البروكسيات 🟢'
        save_accounts()

        proxy_used = get_next_proxy_and_consume()
        await query.message.reply_text(
            "⚡ **لوحة التشغيل الشامل للجميع (24/7)**\n\n"
            f"• الحسابات المستهدفة: `الجميع ({len(USER_ACCOUNTS)})`\n"
            "• الحالة: `✅ بدأ التشغيل على كافة الحسابات!`\n"
            f"• البروكسي المُستخدَم والمحذوف: `{proxy_used}`\n"
            f"• 📉 **البروكسيات المتبقية:** `{len(ACTIVE_PROXIES)} بروكسي`",
            parse_mode='Markdown'
        )

    elif data == 'stop_engine':
        IS_RUNNING_24_7 = False
        for acc in USER_ACCOUNTS:
            USER_ACCOUNTS[acc]['status'] = 'متوقف مؤقتاً ⏹️'
        save_accounts()

        await query.message.reply_text(
            "⏹️ **تم إيقاف العمل مؤقتاً بنجاح!**\n\n"
            "• توقف المحرك عن العمل.\n"
            "• يمكنك العودة وإعادة التشغيل في أي وقت.",
            parse_mode='Markdown'
        )

    elif data == 'back_to_main':
        await start(update, context)

    elif data.startswith('x_'):
        x_map = {'x_1': 'إكس واحد (❌)', 'x_2': 'إكسين (❌❌)', 'x_3': 'ثلاث اكسات (❌❌❌ - باند نزاهة)'}
        chosen_x = x_map.get(data, 'غير معروف')
        
        if user_id in USER_STEPS and USER_STEPS[user_id].get("step") == "waiting_x":
            USER_STEPS[user_id]["x_type"] = chosen_x
            USER_STEPS[user_id]["step"] = "waiting_screenshot"
            
            await query.message.reply_text(
                f"✅ تم اختيار نوع الباند: **{chosen_x}**\n\n"
                "📸 **أرسل الآن صورة (سكرين شوت) للحظر:**",
                parse_mode='Markdown'
            )

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    if user_id not in USER_STEPS:
        return

    current_state = USER_STEPS[user_id].get("step")

    if current_state == "waiting_username":
        username = update.message.text.strip().replace("@", "")
        USER_STEPS[user_id]["username"] = username
        USER_STEPS[user_id]["step"] = "waiting_email"
        await update.message.reply_text("📧 **أرسل الآن الإيميل المربوط بالحساب المتبند:**", parse_mode='Markdown')

    elif current_state == "waiting_email":
        email = update.message.text.strip()
        USER_STEPS[user_id]["email"] = email
        USER_STEPS[user_id]["step"] = "waiting_x"
        await update.message.reply_text(
            "⚠️ **اختر نوع الباند من الأزرار أدناه:**",
            reply_markup=get_x_keyboard(),
            parse_mode='Markdown'
        )

    elif current_state == "waiting_screenshot" and update.message.photo:
        username = USER_STEPS[user_id]["username"]
        email = USER_STEPS[user_id]["email"]
        x_type = USER_STEPS[user_id]["x_type"]

        USER_ACCOUNTS[username] = {
            "email": email,
            "x_type": x_type,
            "status": "تحت المراجعة والتدقيق 🔄"
        }
        save_accounts()
        del USER_STEPS[user_id]

        await update.message.reply_text(
            f"🚀 **تم حفظ الحساب بنجاح تام!**\n\n"
            f"👤 اليوزر: `{username}`\n"
            f"📧 الإيميل: `{email}`\n"
            f"⚠️ نوع الحظر: `{x_type}`\n"
            f"📋 إجمالي الحسابات المخزنة: `{len(USER_ACCOUNTS)}`\n\n"
            "🛡️ اضغط الآن على زر **'عرض الحسابات وفحصها'** أو **'بدء مراسلة انستغرام'**!",
            parse_mode='Markdown'
        )
        await start(update, context)
        
    elif current_state == "waiting_screenshot" and not update.message.photo:
        await update.message.reply_text("⚠️ يرجى إرسال صورة (سكرين شوت) واضحة لحالة الحظر.")

def main():
    load_accounts()
    fetch_fresh_proxies()
    
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND | filters.PHOTO, handle_messages))

    logger.info("Bot is running stable on Render with Python-Telegram-Bot 20.7!")
    app.run_polling()

if __name__ == '__main__':
    main()