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


async def _safe_generate_content(prompt: str, model: str = "gemini-2.5-flash") -> str:
    """تنفيذ طلب Gemini مع معالجة الأخطاء الموحدة."""
    if not client:
        return "❌ مفتاح GEMINI_API_KEY غير متاح في متغيرات البيئة."
    try:
        response = client
