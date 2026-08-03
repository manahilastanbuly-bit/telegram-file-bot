# -*- coding: utf-8 -*-
import os
import logging
import edge_tts
from google import genai
from google.genai import types

# إعداد التسجيل
logger = logging.getLogger(__name__)

# إعداد العميل لـ Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

if not client:
    logger.warning("⚠️ GEMINI_API_KEY غير موجود في متغيرات البيئة. بعض الخدمات لن تعمل.")


# ---------- دوال مساعدة داخلية ----------
def _truncate_text(text: str, max_chars: int = 30000) -> str:
    """تقطيع النص إلى الحد الأقصى المطلوب مع إضافة تنبيه إذا تم القطع."""
    if len(text) > max_chars:
        logger.info(f"تم تقطيع النص من {len(text)} إلى {max_chars} حرف.")
        return text[:max_chars] + "\n...[تم اقتطاع النص لطول كبير]"
    return text


async def _safe_generate_content(prompt: str, model: str = "gemini-1.5-flash") -> str:
    """تنفيذ طلب Gemini مع معالجة الأخطاء الموحدة."""
    if not client:
        return "❌ مفتاح GEMINI_API_KEY غير متاح في متغيرات البيئة."
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt
        )
        return response.text
    except Exception as e:
        logger.error(f"خطأ في استدعاء Gemini API: {e}")
        return f"❌ حدث خطأ أثناء الاتصال بالذكاء الاصطناعي: {e}"


# ---------- دوال الذكاء الاصطناعي المطلوبة في bot.py ----------

async def summarize_text(text: str, level: str = "medium") -> str:
    """توليد ملخص للنص بثلاثة مستويات."""
    text = _truncate_text(text)
    
    instructions = {
        "short": "لخص النص التالي في 3 جمل قصيرة جداً وواضحة فقط.",
        "medium": "لخص النص التالي في فقرة واحدة متوسطة الطول تغطي الأفكار الرئيسية.",
        "detailed": "لخص النص التالي بشكل مفصل في عدة فقرات، مع ذكر النقاط الفرعية المهمة."
    }
    
    prompt = f"{instructions.get(level, instructions['medium'])}\n\nالنص:\n{text}"
    return await _safe_generate_content(prompt)


async def translate_text(text: str, target_lang: str = "en") -> str:
    """ترجمة النص إلى اللغة المستهدفة."""
    text = _truncate_text(text)
    prompt = f"ترجم النص التالي بدقة واحترافية إلى اللغة {target_lang}، مع الحفاظ على المعنى والسياق:\n\n{text}"
    return await _safe_generate_content(prompt)


async def text_to_speech(text: str, output_file: str = "output.mp3", voice: str = "ar-SA-ZariyahNeural") -> str:
    """تحويل النص إلى صوت باستخدام edge-tts."""
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        return output_file
    except Exception as e:
        logger.error(f"فشل تحويل النص لصوت: {e}")
        raise e
