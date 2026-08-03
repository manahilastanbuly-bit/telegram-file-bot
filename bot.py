# -*- coding: utf-8 -*-
import logging
import os
import tempfile

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
    convert_to_pdf, convert_images_to_pdf, convert_pdf_to_word,
    convert_pdf_to_ppt, convert_pdf_to_images, protect_pdf,
    unlock_pdf, compress_pdf, convert_pdf_to_searchable
)
from transcriber import transcribe_audio

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# حالات المحادثة
WAITING_FILE = 1
WAITING_IMAGES = 2
WAITING_PASSWORD_PROTECT = 3
WAITING_PASSWORD_UNLOCK = 4

TASK_KEY = "current_task"
IMAGES_KEY = "collected_images"
FILE_PATH_KEY = "temp_file_path"

# تعريف الأزرار الرئيسية
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
BTN_CANCEL = "❌ إلغاء"

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton(BTN_START)],
        [KeyboardButton(BTN_WORD_TO_PDF), KeyboardButton(BTN_PDF_TO_WORD)],
        [KeyboardButton(BTN_PPT_TO_PDF), KeyboardButton(BTN_PDF_TO_PPT)],
        [KeyboardButton(BTN_PDF_TO_JPG), KeyboardButton(BTN_PDF_TO_PNG)],
        [KeyboardButton(BTN_IMG_TO_PDF), KeyboardButton(BTN_COMPRESS_PDF)],
        [KeyboardButton(BTN_PROTECT_PDF), KeyboardButton(BTN_UNLOCK_PDF)],
        [KeyboardButton(BTN_OCR), KeyboardButton(BTN_VOICE)],
        [KeyboardButton(BTN_CANCEL)]
    ],
    resize_keyboard=True
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "أهلاً بك في بوت معالجة الملفات الشامل 🤖\nاختر المهمة المطلوبة من الأزرار التالية:",
        reply_markup=MAIN_KEYBOARD
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("تم إلغاء العملية. اختر خدمة من القائمة:", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END


# ---------- أزرار تشغيل المهام ----------

async def select_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == BTN_WORD_TO_PDF:
        context.user_data[TASK_KEY] = "word_to_pdf"
        await update.message.reply_text("أرسل ملف Word (.docx أو .doc)")

    elif text == BTN_PPT_TO_PDF:
        context.user_data[TASK_KEY] = "ppt_to_pdf"
        await update.message.reply_text("أرسل ملف PowerPoint (.pptx أو .ppt)")

    elif text == BTN_PDF_TO_WORD:
        context.user_data[TASK_KEY] = "pdf_to_word"
        await update.message.reply_text("أرسل ملف PDF لتحويله إلى Word")

    elif text == BTN_PDF_TO_PPT:
        context.user_data[TASK_KEY] = "pdf_to_ppt"
        await update.message.reply_text("أرسل ملف PDF لتحويله إلى PowerPoint")

    elif text == BTN_PDF_TO_JPG:
        context.user_data[TASK_KEY] = "pdf_to_jpg"
        await update.message.reply_text("أرسل ملف PDF لاستخراج جميع الصفحات كـ JPEG")

    elif text == BTN_PDF_TO_PNG:
        context.user_data[TASK_KEY] = "pdf_to_png"
        await update.message.reply_text("أرسل ملف PDF لاستخراج جميع الصفحات كـ PNG")

    elif text == BTN_IMG_TO_PDF:
        context.user_data[TASK_KEY] = "images_to_pdf"
        context.user_data[IMAGES_KEY] = []
        await update.message.reply_text("أرسل الصور واحدة تلو الأخرى أو دفعة واحدة، وعند الانتهاء أرسل كلمة: تم")
        return WAITING_IMAGES

    elif text == BTN_PROTECT_PDF:
        context.user_data[TASK_KEY] = "protect_pdf"
        await update.message.reply_text("أرسل ملف الـ PDF المراد حمايته")

    elif text == BTN_UNLOCK_PDF:
        context.user_data[TASK_KEY] = "unlock_pdf"
        await update.message.reply_text("أرسل ملف الـ PDF المحمي بكلمة مرور")

    elif text == BTN_COMPRESS_PDF:
        context.user_data[TASK_KEY] = "compress_pdf"
        await update.message.reply_text("أرسل ملف الـ PDF المراد ضغط حجمه")

    elif text == BTN_OCR:
        context.user_data[TASK_KEY] = "pdf_ocr"
        await update.message.reply_text("أرسل ملف الـ PDF لاستخراج النصوص منه وجعله قابلاً للبحث")

    elif text == BTN_VOICE:
        context.user_data[TASK_KEY] = "voice_to_text"
        await update.message.reply_text("أرسل التسجيل الصوتي أو الملف الصوتي")

    return WAITING_FILE


# ---------- معالجة الصور ومجموعاتها ----------

async def collect_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_obj = None
    if update.message.photo:
        file_obj = await update.message.photo[-1].get_file()
    elif update.message.document and update.message.document.mime_type.startswith("image/"):
        file_obj = await update.message.document.get_file()

    if file_obj:
        images = context.user_data.get(IMAGES_KEY, [])
        images.append(file_obj)
        context.user_data[IMAGES_KEY] = images
        await update.message.reply_text(f"تمت إضافة الصورة ({len(images)}). أرسل المزيد أو اكتب 'تم'.")
    return WAITING_IMAGES


async def process_images_to_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    images = context.user_data.get(IMAGES_KEY, [])
    if not images:
        await update.message.reply_text("لم ترسل أي صور! أرسل الصور أولاً ثم اكتب 'تم'.")
        return WAITING_IMAGES

    await update.message.reply_text("جاري تحويل الصور إلى PDF...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        image_paths = []
        for idx, img in enumerate(images):
            path = os.path.join(tmp_dir, f"img_{idx}.jpg")
            await img.download_to_drive(path)
            image_paths.append(path)

        out_pdf = os.path.join(tmp_dir, "صور_مجمعة.pdf")
        await convert_images_to_pdf(image_paths, out_pdf)
        await update.message.reply_document(document=open(out_pdf, "rb"), filename="صور_مجمعة.pdf")

    context.user_data.clear()
    return ConversationHandler.END


# ---------- معالجة الملفات ----------

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task = context.user_data.get(TASK_KEY)
    if not task:
        await update.message.reply_text("اختر خدمة أولاً من القائمة الأسفل 👇", reply_markup=MAIN_KEYBOARD)
        return ConversationHandler.END

    message = update.message
    tg_file = None
    orig_name = "file"

    if message.document:
        tg_file = await message.document.get_file(read_timeout=300)
        orig_name = message.document.file_name
    elif message.voice or message.audio:
        audio = message.voice or message.audio
        tg_file = await audio.get_file(read_timeout=300)
        orig_name = getattr(audio, "file_name", "voice.ogg")
    else:
        await update.message.reply_text("الرجاء إرسال الملف المطلوبة معالجته.")
        return WAITING_FILE

    # للعمليات التي تتطلب كلمة مرور (خطوات متعددة)، نحتاج مجلداً لا يُحذف فوراً
    if task in ("protect_pdf", "unlock_pdf"):
        tmp_dir = tempfile.mkdtemp()  # مجلد مؤقت يبقى موجوداً حتى يتم معالجته لاحقاً
        input_path = os.path.join(tmp_dir, orig_name)
        await tg_file.download_to_drive(input_path, read_timeout=300)
        
        context.user_data[FILE_PATH_KEY] = input_path
        context.user_data['tmp_dir'] = tmp_dir  # حفظ مسار المجلد لحذفه لاحقاً عند الانتهاء
        
        if task == "protect_pdf":
            await message.reply_text("أدخل كلمة المرور التي تريد قفل الملف بها:")
            return WAITING_PASSWORD_PROTECT
        elif task == "unlock_pdf":
            await message.reply_text("أدخل كلمة المرور الحالية للملف:")
            return WAITING_PASSWORD_UNLOCK

    # باقي المهام الفورية التي تتم في خطوة واحدة تستخدم with tempfile.TemporaryDirectory بشكل طبيعي
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_path = os.path.join(tmp_dir, orig_name)
        await tg_file.download_to_drive(input_path, read_timeout=300)

        await message.reply_text("جاري المعالجة، انتظر قليلاً...")
        try:
            if task in ("word_to_pdf", "ppt_to_pdf"):
                pdf_path = await convert_to_pdf(input_path, tmp_dir)
                await message.reply_document(document=open(pdf_path, "rb"), read_timeout=300)

            elif task == "pdf_to_word":
                out_doc = os.path.join(tmp_dir, f"{os.path.splitext(orig_name)[0]}.docx")
                await convert_pdf_to_word(input_path, out_doc)
                await message.reply_document(document=open(out_doc, "rb"), read_timeout=300)

            elif task == "pdf_to_ppt":
                out_ppt = await convert_pdf_to_ppt(input_path, tmp_dir)
                await message.reply_document(document=open(out_ppt, "rb"), read_timeout=300)

            elif task in ("pdf_to_jpg", "pdf_to_png"):
                fmt = "jpeg" if task == "pdf_to_jpg" else "png"
                img_paths = await convert_pdf_to_images(input_path, tmp_dir, fmt=fmt)
                for img_p in img_paths:
                    await message.reply_document(document=open(img_p, "rb"))

            elif task == "compress_pdf":
                out_comp = os.path.join(tmp_dir, f"compressed_{orig_name}")
                await compress_pdf(input_path, out_comp)
                await message.reply_document(document=open(out_comp, "rb"), filename=f"مضغوط_{orig_name}")

            elif task == "pdf_ocr":
                out_ocr = os.path.join(tmp_dir, f"searchable_{orig_name}")
                await convert_pdf_to_searchable(input_path, out_ocr)
                await message.reply_document(document=open(out_ocr, "rb"), filename=f"Searchable_{orig_name}")

            elif task == "voice_to_text":
                text = await transcribe_audio(input_path)
                for i in range(0, len(text), 4000):
                    await message.reply_text(text[i:i + 4000])

        except Exception as exc:
            logger.exception("فشل التنفيذ")
            await message.reply_text(f"حدث خطأ أثناء المعالجة: {exc}")

    context.user_data.clear()
    return ConversationHandler.END


    

        await message.reply_text("جاري المعالجة، انتظر قليلاً...")
        try:
            if task in ("word_to_pdf", "ppt_to_pdf"):
                pdf_path = await convert_to_pdf(input_path, tmp_dir)
                await message.reply_document(document=open(pdf_path, "rb"), read_timeout=300)

            elif task == "pdf_to_word":
                out_doc = os.path.join(tmp_dir, f"{os.path.splitext(orig_name)[0]}.docx")
                await convert_pdf_to_word(input_path, out_doc)
                await message.reply_document(document=open(out_doc, "rb"), read_timeout=300)

            elif task == "pdf_to_ppt":
                out_ppt = await convert_pdf_to_ppt(input_path, tmp_dir)
                await message.reply_document(document=open(out_ppt, "rb"), read_timeout=300)

            elif task in ("pdf_to_jpg", "pdf_to_png"):
                fmt = "jpeg" if task == "pdf_to_jpg" else "png"
                img_paths = await convert_pdf_to_images(input_path, tmp_dir, fmt=fmt)
                for img_p in img_paths:
                    await message.reply_document(document=open(img_p, "rb"))

            elif task == "compress_pdf":
                out_comp = os.path.join(tmp_dir, f"compressed_{orig_name}")
                await compress_pdf(input_path, out_comp)
                await message.reply_document(document=open(out_comp, "rb"), filename=f"مضغوط_{orig_name}")

            elif task == "pdf_ocr":
                out_ocr = os.path.join(tmp_dir, f"searchable_{orig_name}")
                await convert_pdf_to_searchable(input_path, out_ocr)
                await message.reply_document(document=open(out_ocr, "rb"), filename=f"Searchable_{orig_name}")

            elif task == "voice_to_text":
                text = await transcribe_audio(input_path)
                for i in range(0, len(text), 4000):
                    await message.reply_text(text[i:i + 4000])

        except Exception as exc:
            logger.exception("فشل التنفيذ")
            await message.reply_text(f"حدث خطأ أثناء المعالجة: {exc}")

    context.user_data.clear()
    return ConversationHandler.END


# ---------- التعامل مع كود المرور ----------

async def handle_password_protect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text
    input_path = context.user_data.get(FILE_PATH_KEY)
    await update.message.reply_text("جاري قفل وحماية الملف...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_pdf = os.path.join(tmp_dir, "Protected_Document.pdf")
        try:
            await protect_pdf(input_path, out_pdf, password)
            await update.message.reply_document(document=open(out_pdf, "rb"), filename="محمي_Protected.pdf")
        except Exception as e:
            await update.message.reply_text(f"حدث خطأ أثناء قفل الملف: {e}")
    context.user_data.clear()
    return ConversationHandler.END


async def handle_password_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text
    input_path = context.user_data.get(FILE_PATH_KEY)
    await update.message.reply_text("جاري فك كلمة المرور...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_pdf = os.path.join(tmp_dir, "Unlocked_Document.pdf")
        try:
            await unlock_pdf(input_path, out_pdf, password)
            await update.message.reply_document(document=open(out_pdf, "rb"), filename="مفكوك_Unlocked.pdf")
        except Exception as e:
            await update.message.reply_text(f"كلمة المرور خاطئة أو حدث خطأ: {e}")
    context.user_data.clear()
    return ConversationHandler.END


def build_application() -> Application:
    if not BOT_TOKEN:
        raise RuntimeError("لم يتم العثور على TELEGRAM_BOT_TOKEN.")

    from telegram.request import HTTPXRequest
    request = HTTPXRequest(connect_timeout=60.0, read_timeout=300.0, write_timeout=300.0)
    application = Application.builder().token(BOT_TOKEN).request(request).build()

    cancel_filter = filters.Regex(rf"(?i)^({BTN_CANCEL}|الغاء|إلغاء)$")

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex(rf"^{BTN_START}$"), start),
            MessageHandler(filters.TEXT & ~filters.COMMAND & ~cancel_filter, select_task),
        ],
        states={
            WAITING_FILE: [
                MessageHandler(cancel_filter, cancel),
                MessageHandler(filters.Regex(rf"^{BTN_START}$"), start),
                MessageHandler(filters.Document.ALL | filters.VOICE | filters.AUDIO, handle_file),
            ],
            WAITING_IMAGES: [
                MessageHandler(cancel_filter, cancel),
                MessageHandler(filters.Regex(rf"^{BTN_START}$"), start),
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
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex(rf"^{BTN_START}$"), start)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    return application


def main():
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
