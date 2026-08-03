# -*- coding: utf-8 -*-
import logging
import os
import shutil
import tempfile
from typing import Optional, Tuple

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from converters import (
    convert_to_pdf,
    convert_images_to_pdf,
    convert_pdf_to_word,
    convert_pdf_to_ppt,
    convert_pdf_to_images,
    protect_pdf,
    unlock_pdf,
    compress_pdf,
    convert_pdf_to_searchable,
)
from transcriber import transcribe_audio

# استيراد موديول الذكاء الاصطناعي (يجب أن يكون موجوداً)
import ai_services  # تأكد من وجود هذا الملف أو قم بتعريف دالة مؤقتة

# ---------- إعدادات التسجيل ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------- متغيرات البيئة ----------
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("لم يتم العثور على TELEGRAM_BOT_TOKEN في متغيرات البيئة.")

# ---------- حالات المحادثة ----------
(
    WAITING_FILE,
    WAITING_IMAGES,
    WAITING_PASSWORD_PROTECT,
    WAITING_PASSWORD_UNLOCK,
    WAITING_TEXT,          # حالة جديدة لاستقبال النص المراد تلخيصه
) = range(1, 6)

# ---------- مفاتيح التخزين المؤقت ----------
TASK_KEY = "task"
IMAGES_KEY = "images"
FILE_PATH_KEY = "file_path"
INPUT_TEMP_DIR_KEY = "input_temp_dir"
OUTPUT_TEMP_DIR_KEY = "output_temp_dir"

# ---------- تعريف الأزرار ----------
BTN_START = "🔄 البدء / القائمة الرئيسية"
BTN_WORD_TO_PDF = "📄 وورد ← PDF"
BTN_PPT_TO_PDF = "📊 بوربوينت ← PDF"
BTN_PDF_TO_WORD = "📝 PDF ← Word"
BTN_PDF_TO_PPT = "📈 PDF ← PowerPoint"
BTN_PDF_TO_JPG = "🖼️ PDF ← JPEG"
BTN_PDF_TO_PNG = "🖼️ PDF ← PNG"
BTN_IMG_TO_PDF = "📷 صور ← PDF"
BTN_PROTECT_PDF = "🔒 حماية PDF"
BTN_UNLOCK_PDF = "🔓 فك حماية PDF"
BTN_COMPRESS_PDF = "🗜️ ضغط PDF"
BTN_OCR = "🔍 PDF قابل للبحث (OCR)"
BTN_VOICE = "🎙️ صوت ← نص"
BTN_SUMMARY = "🧠 تلخيص نص"          # الزر الجديد
BTN_CANCEL = "❌ إلغاء"

# إعادة ترتيب الأزرار لإضافة زر التلخيص
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton(BTN_START)],
        [KeyboardButton(BTN_WORD_TO_PDF), KeyboardButton(BTN_PDF_TO_WORD)],
        [KeyboardButton(BTN_PPT_TO_PDF), KeyboardButton(BTN_PDF_TO_PPT)],
        [KeyboardButton(BTN_PDF_TO_JPG), KeyboardButton(BTN_PDF_TO_PNG)],
        [KeyboardButton(BTN_IMG_TO_PDF), KeyboardButton(BTN_COMPRESS_PDF)],
        [KeyboardButton(BTN_PROTECT_PDF), KeyboardButton(BTN_UNLOCK_PDF)],
        [KeyboardButton(BTN_OCR), KeyboardButton(BTN_VOICE)],
        [KeyboardButton(BTN_SUMMARY)],  # زر التلخيص في صف منفرد
        [KeyboardButton(BTN_CANCEL)],
    ],
    resize_keyboard=True,
)

# ---------- دوال مساعدة لإدارة المجلدات المؤقتة ----------

def create_input_temp_dir(context: ContextTypes.DEFAULT_TYPE) -> str:
    tmp_dir = tempfile.mkdtemp()
    context.user_data[INPUT_TEMP_DIR_KEY] = tmp_dir
    return tmp_dir

def create_output_temp_dir(context: ContextTypes.DEFAULT_TYPE) -> str:
    tmp_dir = tempfile.mkdtemp()
    context.user_data[OUTPUT_TEMP_DIR_KEY] = tmp_dir
    return tmp_dir

def cleanup_temp_dirs(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in (INPUT_TEMP_DIR_KEY, OUTPUT_TEMP_DIR_KEY):
        tmp_dir = context.user_data.pop(key, None)
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)

async def download_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Tuple[Optional[str], Optional[str]]:
    message = update.message
    file_obj = None
    original_name = None

    if message.document:
        file_obj = await message.document.get_file(read_timeout=300)
        original_name = message.document.file_name
    elif message.voice:
        file_obj = await message.voice.get_file(read_timeout=300)
        original_name = "voice.ogg"
    elif message.audio:
        file_obj = await message.audio.get_file(read_timeout=300)
        original_name = message.audio.file_name or "audio.mp3"
    else:
        return None, None

    tmp_dir = create_input_temp_dir(context)
    local_path = os.path.join(tmp_dir, original_name or "file")
    await file_obj.download_to_drive(local_path, read_timeout=300)
    return local_path, original_name

async def send_result(update: Update, file_path: str, filename: str = None) -> None:
    try:
        if filename is None:
            filename = os.path.basename(file_path)
        await update.message.reply_document(
            document=open(file_path, "rb"),
            filename=filename,
            read_timeout=300,
        )
    except Exception as e:
        logger.error(f"فشل إرسال الملف {file_path}: {e}")
        await update.message.reply_text("حدث خطأ أثناء إرسال الملف الناتج، حاول مرة أخرى.")

# ---------- دوال معالجة المحادثة ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cleanup_temp_dirs(context)
    context.user_data.clear()
    await update.message.reply_text(
        "أهلاً بك في بوت معالجة الملفات الشامل 🤖\nاختر المهمة المطلوبة من الأزرار التالية:",
        reply_markup=MAIN_KEYBOARD,
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cleanup_temp_dirs(context)
    context.user_data.clear()
    await update.message.reply_text("تم إلغاء العملية. اختر خدمة من القائمة:", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END

async def select_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    task_map = {
        BTN_WORD_TO_PDF: ("word_to_pdf", "أرسل ملف Word (.docx أو .doc)"),
        BTN_PPT_TO_PDF: ("ppt_to_pdf", "أرسل ملف PowerPoint (.pptx أو .ppt)"),
        BTN_PDF_TO_WORD: ("pdf_to_word", "أرسل ملف PDF لتحويله إلى Word"),
        BTN_PDF_TO_PPT: ("pdf_to_ppt", "أرسل ملف PDF لتحويله إلى PowerPoint"),
        BTN_PDF_TO_JPG: ("pdf_to_jpg", "أرسل ملف PDF لاستخراج جميع الصفحات كـ JPEG"),
        BTN_PDF_TO_PNG: ("pdf_to_png", "أرسل ملف PDF لاستخراج جميع الصفحات كـ PNG"),
        BTN_PROTECT_PDF: ("protect_pdf", "أرسل ملف الـ PDF المراد حمايته"),
        BTN_UNLOCK_PDF: ("unlock_pdf", "أرسل ملف الـ PDF المحمي بكلمة مرور"),
        BTN_COMPRESS_PDF: ("compress_pdf", "أرسل ملف الـ PDF المراد ضغط حجمه"),
        BTN_OCR: ("pdf_ocr", "أرسل ملف الـ PDF لاستخراج النصوص منه وجعله قابلاً للبحث"),
        BTN_VOICE: ("voice_to_text", "أرسل التسجيل الصوتي أو الملف الصوتي"),
        BTN_SUMMARY: ("summary", "أرسل النص الذي تريد تلخيصه (يمكن أن يكون طويلاً)"),
    }

    if text in task_map:
        task, prompt = task_map[text]
        context.user_data[TASK_KEY] = task
        await update.message.reply_text(prompt)
        if task == "summary":
            return WAITING_TEXT
        return WAITING_FILE

    if text == BTN_IMG_TO_PDF:
        context.user_data[TASK_KEY] = "images_to_pdf"
        context.user_data[IMAGES_KEY] = []
        await update.message.reply_text("أرسل الصور واحدة تلو الأخرى، وعند الانتهاء أرسل كلمة: تم")
        return WAITING_IMAGES

    await update.message.reply_text("الرجاء اختيار خدمة من القائمة.", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END

# ---------- معالجة الصور ----------

async def collect_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    file_obj = None
    if update.message.photo:
        file_obj = await update.message.photo[-1].get_file()
    elif update.message.document and update.message.document.mime_type.startswith("image/"):
        file_obj = await update.message.document.get_file()

    if file_obj:
        images = context.user_data.get(IMAGES_KEY, [])
        images.append(file_obj)
        context.user_data[IMAGES_KEY] = images
        await update.message.reply_text(f"✅ تمت إضافة الصورة ({len(images)}). أرسل المزيد أو اكتب 'تم'.")
    else:
        await update.message.reply_text("الرجاء إرسال صورة.")
    return WAITING_IMAGES

async def process_images_to_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    images = context.user_data.get(IMAGES_KEY, [])
    if not images:
        await update.message.reply_text("❌ لم ترسل أي صور!")
        return WAITING_IMAGES

    await update.message.reply_text("⏳ جاري تحويل الصور إلى PDF...")
    input_tmp = create_input_temp_dir(context)
    image_paths = []
    try:
        for idx, img in enumerate(images):
            path = os.path.join(input_tmp, f"img_{idx:03d}.jpg")
            await img.download_to_drive(path)
            image_paths.append(path)

        out_dir = create_output_temp_dir(context)
        out_pdf = os.path.join(out_dir, "صور_مجمعة.pdf")
        await convert_images_to_pdf(image_paths, out_pdf)
        await send_result(update, out_pdf, "صور_مجمعة.pdf")
    except Exception as e:
        logger.exception("فشل تحويل الصور إلى PDF")
        await update.message.reply_text(f"❌ حدث خطأ: {e}")
    finally:
        cleanup_temp_dirs(context)
        context.user_data.clear()

    return ConversationHandler.END

# ---------- معالجة التلخيص ----------

async def handle_summary_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استقبال النص المراد تلخيصه واستدعاء خدمة الذكاء الاصطناعي."""
    user_text = update.message.text
    if not user_text or len(user_text.strip()) == 0:
        await update.message.reply_text("❌ الرجاء إرسال نص صحيح للتلخيص.")
        return WAITING_TEXT

    # إرسال رسالة انتظار
    loading_msg = await update.message.reply_text("🤖 جاري تلخيص النص بواسطة الذكاء الاصطناعي...")

    try:
        # استدعاء دالة التلخيص من موديول ai_services
        summary_result = await ai_services.summarize_text(user_text)
        # إذا كانت النتيجة طويلة جداً، نقسمها
        if len(summary_result) > 4000:
            for i in range(0, len(summary_result), 4000):
                await update.message.reply_text(summary_result[i:i+4000])
        else:
            await update.message.reply_text(summary_result)
    except Exception as e:
        logger.exception("فشل تلخيص النص")
        await update.message.reply_text(f"❌ حدث خطأ أثناء التلخيص: {e}")
    finally:
        # حذف رسالة الانتظار
        await loading_msg.delete()
        cleanup_temp_dirs(context)
        context.user_data.clear()

    return ConversationHandler.END

# ---------- معالجة الملفات العامة ----------

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    task = context.user_data.get(TASK_KEY)
    if not task:
        await update.message.reply_text("❌ اختر خدمة أولاً.", reply_markup=MAIN_KEYBOARD)
        return ConversationHandler.END

    local_path, original_name = await download_file(update, context)
    if not local_path:
        await update.message.reply_text("❌ الرجاء إرسال ملف صالح.")
        return WAITING_FILE

    await update.message.reply_text("⏳ جاري المعالجة...")

    if task in ("protect_pdf", "unlock_pdf"):
        context.user_data[FILE_PATH_KEY] = local_path
        if task == "protect_pdf":
            await update.message.reply_text("🔑 أدخل كلمة المرور التي تريد قفل الملف بها:")
            return WAITING_PASSWORD_PROTECT
        else:
            await update.message.reply_text("🔑 أدخل كلمة المرور الحالية للملف:")
            return WAITING_PASSWORD_UNLOCK

    try:
        await process_general_task(update, context, task, local_path, original_name)
    except Exception as e:
        logger.exception("فشل تنفيذ المهمة العامة")
        await update.message.reply_text(f"❌ حدث خطأ: {e}")
    finally:
        cleanup_temp_dirs(context)
        context.user_data.clear()

    return ConversationHandler.END

async def process_general_task(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    task: str,
    input_path: str,
    original_name: str,
) -> None:
    out_dir = create_output_temp_dir(context)
    base, _ = os.path.splitext(original_name or "file")

    if task == "word_to_pdf" or task == "ppt_to_pdf":
        out_path = await convert_to_pdf(input_path, out_dir)
        await send_result(update, out_path)

    elif task == "pdf_to_word":
        out_path = os.path.join(out_dir, f"{base}.docx")
        await convert_pdf_to_word(input_path, out_path)
        await send_result(update, out_path)

    elif task == "pdf_to_ppt":
        out_path = await convert_pdf_to_ppt(input_path, out_dir)
        await send_result(update, out_path)

    elif task in ("pdf_to_jpg", "pdf_to_png"):
        fmt = "jpeg" if task == "pdf_to_jpg" else "png"
        img_paths = await convert_pdf_to_images(input_path, out_dir, fmt=fmt)
        for img_path in img_paths:
            await send_result(update, img_path)

    elif task == "compress_pdf":
        out_path = os.path.join(out_dir, f"compressed_{original_name}")
        await compress_pdf(input_path, out_path)
        await send_result(update, out_path, f"مضغوط_{original_name}")

    elif task == "pdf_ocr":
        out_path = os.path.join(out_dir, f"searchable_{original_name}")
        await convert_pdf_to_searchable(input_path, out_path)
        await send_result(update, out_path, f"Searchable_{original_name}")

    elif task == "voice_to_text":
        text = await transcribe_audio(input_path)
        if not text.strip():
            await update.message.reply_text("⚠️ لم يتم استخراج أي نص من الصوت.")
        else:
            for i in range(0, len(text), 4000):
                await update.message.reply_text(text[i:i+4000])

    else:
        await update.message.reply_text("❌ مهمة غير معروفة.")

# ---------- معالجة كلمة المرور ----------

async def handle_password_protect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    password = update.message.text
    input_path = context.user_data.get(FILE_PATH_KEY)
    input_dir = context.user_data.get(INPUT_TEMP_DIR_KEY)

    if not input_path or not os.path.exists(input_path):
        await update.message.reply_text("❌ ملف غير موجود، الرجاء إعادة المحاولة.")
        cleanup_temp_dirs(context)
        context.user_data.clear()
        return ConversationHandler.END

    await update.message.reply_text("⏳ جاري قفل وحماية الملف...")
    with tempfile.TemporaryDirectory() as out_tmp_dir:
        out_path = os.path.join(out_tmp_dir, "Protected_Document.pdf")
        try:
            await protect_pdf(input_path, out_path, password)
            await send_result(update, out_path, "محمي_Protected.pdf")
        except Exception as e:
            logger.exception("فشل حماية PDF")
            await update.message.reply_text(f"❌ حدث خطأ أثناء قفل الملف: {e}")
        finally:
            cleanup_temp_dirs(context)
            context.user_data.clear()

    return ConversationHandler.END

async def handle_password_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    password = update.message.text
    input_path = context.user_data.get(FILE_PATH_KEY)
    input_dir = context.user_data.get(INPUT_TEMP_DIR_KEY)

    if not input_path or not os.path.exists(input_path):
        await update.message.reply_text("❌ ملف غير موجود، الرجاء إعادة المحاولة.")
        cleanup_temp_dirs(context)
        context.user_data.clear()
        return ConversationHandler.END

    await update.message.reply_text("⏳ جاري فك كلمة المرور...")
    with tempfile.TemporaryDirectory() as out_tmp_dir:
        out_path = os.path.join(out_tmp_dir, "Unlocked_Document.pdf")
        try:
            await unlock_pdf(input_path, out_path, password)
            await send_result(update, out_path, "مفكوك_Unlocked.pdf")
        except Exception as e:
            logger.exception("فشل فك حماية PDF")
            await update.message.reply_text(f"❌ كلمة المرور خاطئة أو حدث خطأ: {e}")
        finally:
            cleanup_temp_dirs(context)
            context.user_data.clear()

    return ConversationHandler.END

# ---------- بناء التطبيق ----------

def build_application() -> Application:
    from telegram.request import HTTPXRequest

    request = HTTPXRequest(
        connect_timeout=60.0,
        read_timeout=300.0,
        write_timeout=300.0,
    )
    application = Application.builder().token(BOT_TOKEN).request(request).build()

    cancel_filter = filters.Regex(rf"(?i)^({BTN_CANCEL}|الغاء|إلغاء)$")
    start_filter = filters.Regex(rf"^{BTN_START}$")

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(start_filter, start),
            MessageHandler(filters.TEXT & ~filters.COMMAND & ~cancel_filter, select_task),
        ],
        states={
            WAITING_FILE: [
                MessageHandler(cancel_filter, cancel),
                MessageHandler(start_filter, start),
                MessageHandler(filters.Document.ALL | filters.VOICE | filters.AUDIO, handle_file),
            ],
            WAITING_IMAGES: [
                MessageHandler(cancel_filter, cancel),
                MessageHandler(start_filter, start),
                MessageHandler(filters.Regex(r"(?i)^تم$"), process_images_to_pdf),
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, collect_image),
            ],
            WAITING_PASSWORD_PROTECT: [
                MessageHandler(cancel_filter, cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password_protect),
            ],
            WAITING_PASSWORD_UNLOCK: [
                MessageHandler(cancel_filter, cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password_unlock),
            ],
            WAITING_TEXT: [
                MessageHandler(cancel_filter, cancel),
                MessageHandler(start_filter, start),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_summary_text),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(start_filter, start),
        ],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    return application

# ---------- نقطة الدخول ----------

def main() -> None:
    application = build_application()
    port = int(os.environ.get("PORT", "10000"))
    external_url = os.environ.get("RENDER_EXTERNAL_URL")

    if external_url:
        webhook_path = BOT_TOKEN
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=webhook_path,
            webhook_url=f"{external_url}/{webhook_path}",
        )
    else:
        application.run_polling()

if __name__ == "__main__":
    main()
