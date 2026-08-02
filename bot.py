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

from converters import convert_to_pdf, convert_images_to_pdf, convert_pdf_to_searchable
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

TASK_KEY = "current_task"
IMAGES_KEY = "collected_images"

TASK_WORD = "word_to_pdf"
TASK_PPT = "ppt_to_pdf"
TASK_VOICE = "voice_to_text"
TASK_IMAGES = "images_to_pdf"
TASK_OCR = "pdf_ocr"

# الأزرار الرئيسية في الكيبورد
BTN_WORD = "📄 وورد إلى PDF"
BTN_PPT = "📊 بوربوينت إلى PDF"
BTN_IMAGES = "🖼️ صور إلى PDF"
BTN_VOICE = "🎙️ صوت إلى نص"
BTN_OCR = "🔍 جعل PDF قابل للبحث (OCR)"
BTN_CANCEL = "❌ إلغاء"

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton(BTN_WORD), KeyboardButton(BTN_PPT)],
        [KeyboardButton(BTN_IMAGES), KeyboardButton(BTN_VOICE)],
        [KeyboardButton(BTN_OCR)],
        [KeyboardButton(BTN_CANCEL)]
    ],
    resize_keyboard=True
)

WELCOME_MESSAGE = (
    "أهلاً بك! أنا بوت تحويل الملفات الشامل 🤖\n\n"
    "اختر الخدمة المطلوبة من الأزرار بالأسفل 👇"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=MAIN_KEYBOARD)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop(TASK_KEY, None)
    context.user_data.pop(IMAGES_KEY, None)
    await update.message.reply_text(
        "تم إلغاء العملية. اختر خدمة أخرى من الأزرار بالأسفل:",
        reply_markup=MAIN_KEYBOARD
    )
    return ConversationHandler.END


# ---------- نقاط الدخول (الأزرار) ----------

async def ask_for_word_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[TASK_KEY] = TASK_WORD
    await update.message.reply_text("الرجاء إرسال ملف Word (.doc أو .docx)")
    return WAITING_FILE


async def ask_for_ppt_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[TASK_KEY] = TASK_PPT
    await update.message.reply_text("الرجاء إرسال ملف PowerPoint (.ppt أو .pptx)")
    return WAITING_FILE


async def ask_for_voice_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[TASK_KEY] = TASK_VOICE
    await update.message.reply_text("الرجاء إرسال الملف الصوتي (يدعم العربية والإنجليزية)")
    return WAITING_FILE


async def ask_for_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[TASK_KEY] = TASK_IMAGES
    context.user_data[IMAGES_KEY] = []
    await update.message.reply_text(
        "أرسل الصور المطلوبة الآن (واحدة تلو الأخرى أو دفعة واحدة).\n"
        "عند الانتهاء من إرسال كل الصور، أرسل كلمة: تم"
    )
    return WAITING_IMAGES


async def ask_for_ocr_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[TASK_KEY] = TASK_OCR
    await update.message.reply_text(
        "الرجاء إرسال ملف الـ PDF المطلوب استخراج النصوص منه ليكون قابلاً للبحث (عربي/إنجليزي)."
    )
    return WAITING_FILE


# ---------- استقبال الصور وتجميعها ----------

async def collect_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    file_obj = None

    if message.photo:
        file_obj = await message.photo[-1].get_file()
    elif message.document and message.document.mime_type.startswith("image/"):
        file_obj = await message.document.get_file()

    if file_obj:
        images_list = context.user_data.get(IMAGES_KEY, [])
        images_list.append(file_obj)
        context.user_data[IMAGES_KEY] = images_list
        await message.reply_text(
            f"تمت إضافة الصورة ({len(images_list)}). أرسل المزيد أو أرسل كلمة 'تم' للتحويل."
        )

    return WAITING_IMAGES


async def process_images_to_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    images_list = context.user_data.get(IMAGES_KEY, [])

    if not images_list:
        await update.message.reply_text("لم تقم بإرسال أي صور! أرسل الصور أولاً ثم أرسل 'تم'.")
        return WAITING_IMAGES

    await update.message.reply_text("جاري دمج وتنسيق الصور وتحويلها إلى PDF...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        image_paths = []
        for index, file_obj in enumerate(images_list):
            img_path = os.path.join(tmp_dir, f"img_{index}.jpg")
            await file_obj.download_to_drive(img_path)
            image_paths.append(img_path)

        try:
            pdf_path = os.path.join(tmp_dir, "converted_images.pdf")
            await convert_images_to_pdf(image_paths, pdf_path)
            await update.message.reply_document(
                document=open(pdf_path, "rb"),
                filename="صور_مجمعة.pdf"
            )
        except Exception as exc:
            logger.exception("فشل تحويل الصور إلى PDF")
            await update.message.reply_text(f"حدث خطأ أثناء معالجة الصور: {exc}")

    context.user_data.pop(TASK_KEY, None)
    context.user_data.pop(IMAGES_KEY, None)
    return ConversationHandler.END


# ---------- استقبال الملفات وتنفيذ المهام ----------

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task = context.user_data.get(TASK_KEY)
    if not task:
        await update.message.reply_text(
            "اختر إحدى الخدمات من الأزرار أدناه أولاً 👇",
            reply_markup=MAIN_KEYBOARD
        )
        return ConversationHandler.END

    message = update.message
    tg_file = None
    original_name = None

    if task in (TASK_WORD, TASK_PPT, TASK_OCR):
        if not message.document:
            await message.reply_text("الرجاء إرسال الملف كملف (document).")
            return WAITING_FILE
        tg_file = await message.document.get_file()
        original_name = message.document.file_name

    elif task == TASK_VOICE:
        if message.voice:
            tg_file = await message.voice.get_file()
            original_name = "voice.ogg"
        elif message.audio:
            tg_file = await message.audio.get_file()
            original_name = message.audio.file_name or "audio.mp3"
        elif message.document:
            tg_file = await message.document.get_file()
            original_name = message.document.file_name
        else:
            await message.reply_text("الرجاء إرسال ملف صوتي أو رسالة صوتية.")
            return WAITING_FILE

    await message.reply_text("جاري المعالجة، انتظر قليلاً...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        input_path = os.path.join(tmp_dir, original_name)
        await tg_file.download_to_drive(input_path)

        try:
            if task in (TASK_WORD, TASK_PPT):
                pdf_path = await convert_to_pdf(input_path, tmp_dir)
                await message.reply_document(document=open(pdf_path, "rb"))

            elif task == TASK_OCR:
                output_pdf = os.path.join(tmp_dir, f"searchable_{original_name}")
                await convert_pdf_to_searchable(input_path, output_pdf)
                await message.reply_document(
                    document=open(output_pdf, "rb"),
                    filename=f"Searchable_{original_name}"
                )

            elif task == TASK_VOICE:
                text = await transcribe_audio(input_path)
                for i in range(0, len(text), 4000):
                    await message.reply_text(text[i:i + 4000])

        except Exception as exc:
            logger.exception("فشل تنفيذ المهمة")
            await message.reply_text(f"صار خطأ أثناء المعالجة: {exc}")

    context.user_data.pop(TASK_KEY, None)
    return ConversationHandler.END


def build_application() -> Application:
    if not BOT_TOKEN:
        raise RuntimeError("لم يتم العثور على التوكن TELEGRAM_BOT_TOKEN.")

    application = Application.builder().token(BOT_TOKEN).build()

    # مطابقة الأزرار أو النصوص المشابهة
    word_pattern = filters.Regex(rf"(?i)({BTN_WORD}|وورد|word)")
    ppt_pattern = filters.Regex(rf"(?i)({BTN_PPT}|بوربوينت|power ?point)")
    voice_pattern = filters.Regex(rf"(?i)({BTN_VOICE}|صوت|voice|audio)")
    images_pattern = filters.Regex(rf"(?i)({BTN_IMAGES}|صور|صورة|images?)")
    ocr_pattern = filters.Regex(rf"(?i)({BTN_OCR}|ocr|بحث|قابل للبحث)")

    cancel_filter = filters.Regex(rf"(?i)^({BTN_CANCEL}|الغاء|إلغاء)$")

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(word_pattern, ask_for_word_file),
            MessageHandler(ppt_pattern, ask_for_ppt_file),
            MessageHandler(voice_pattern, ask_for_voice_file),
            MessageHandler(images_pattern, ask_for_images),
            MessageHandler(ocr_pattern, ask_for_ocr_pdf),
        ],
        states={
            WAITING_FILE: [
                MessageHandler(cancel_filter, cancel),
                MessageHandler(filters.Document.ALL | filters.VOICE | filters.AUDIO, handle_file),
            ],
            WAITING_IMAGES: [
                MessageHandler(cancel_filter, cancel),
                MessageHandler(filters.Regex(r"(?i)^تم$"), process_images_to_pdf),
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, collect_image),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
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
        logger.info("البوت شغال بوضع Webhook على Render...")
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=webhook_path,
            webhook_url=f"{external_url}/{webhook_path}",
        )
    else:
        logger.info("البوت شغال بوضع Polling...")
        application.run_polling()


if __name__ == "__main__":
    main()
