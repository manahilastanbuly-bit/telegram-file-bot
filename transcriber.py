import os
from groq import Groq

# يتم قراءة المفتاح تلقائياً من متغيرات البيئة في Render
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

async def transcribe_audio(audio_path: str) -> str:
    """
    تحويل الصوت إلى نص باستخدام نموذج whisper-large-v3 الخارق عبر Groq API
    """
    with open(audio_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(audio_path, file.read()),
            model="whisper-large-v3",
            response_format="text"
        )
    return transcription
