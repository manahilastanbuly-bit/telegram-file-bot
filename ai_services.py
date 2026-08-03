# -*- coding: utf-8 -*-
import os
import edge_tts
from google import genai
from google.genai import types

# إعداد العميل لـ Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# 1. دالة تلخيص المستندات (مع دعم المستويات)
async def summarize_text(text: str, level: str = "medium") -> str:
    if not client:
        return "❌ مفتاح GEMINI_API_KEY غير متاح في متغيرات البيئة."
    
    # تخصيص أسلوب التلخيص بناءً على اختيار المستخدم
    level_instructions = {
        "short": "قم بتلخيص النص التالي في جملة واحدة موجزة وقوية باللغة العربية.",
        "medium": "قم بتلخيص النص التالي في فقرة قصيرة ومنظمة باللغة العربية.",
        "detailed": "قم بتلخيص النص التالي بشكل مفصل ومنظم في عدة فقرات ونقاط رئيسية واضحة باللغة العربية."
    }
    
    instruction = level_instructions.get(level, level_instructions["medium"])
    prompt = f"{instruction}\n\nالنص:\n{text[:30000]}"
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    return response.text

# 2. دالة ترجمة النصوص (مطلوبة لأزرار الترجمة)
async def translate_text(text: str, target_lang: str = "en") -> str:
    if not client:
        return "❌ مفتاح GEMINI_API_KEY غير متاح في متغيرات البيئة."
    
    prompt = f"قم بترجمة النص التالي إلى اللغة الإنجليزية بدقة واحترافية عالية:\n\n{text}"
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    return response.text

# 3. دالة المحادثة والأسئلة حول المستند (Chat with Doc)
async def ask_document_question(doc_text: str, question: str) -> str:
    if not client:
        return "❌ مفتاح GEMINI_API_KEY غير متاح في متغيرات البيئة."
    
    prompt = f"""
    أنت مساعد ذكي. اعتماداً حصرياً على النص التالي للمستند، أجب على سؤال المستخدم بدقة باللغة العربية:
    
    --- المستند ---
    {doc_text[:50000]}
    --------------
    
    السؤال: {question}
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    return response.text

# 4. دالة تحليل الصور
async def analyze_image_ai(image_path: str) -> str:
    if not client:
        return "❌ مفتاح GEMINI_API_KEY غير متاح في متغيرات البيئة."
    
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    prompt = "اكتب وصفاً تفصيلياً لهذه الصورة باللغة العربية، واستخرج أي نصوص مكتوبة فيها بوضوح."
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            prompt
        ]
    )
    return response.text

# 5. دالة تحويل النص إلى صوت (TTS)
async def text_to_speech_file(text: str, output_audio_path: str, voice: str = "ar-SA-HamedNeural") -> str:
    """
    تحويل النص إلى ملف صوتي بصوت عربي طبيعي
    """
    short_text = text[:1000]  # أخذ أول 1000 حرف لتجنب الملفات الضخمة
    communicate = edge_tts.Communicate(short_text, voice)
    await communicate.save(output_audio_path)
    return output_audio_path
