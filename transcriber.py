import os
from groq import Groq


async def transcribe_audio(audio_path: str) -> str:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "خطأ: مفتاح GROQ_API_KEY غير معرف في بيئة العمل (Environment Variables)."

    client = Groq(api_key=api_key)

    with open(audio_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), file.read()),
            model="whisper-large-v3",
            response_format="text",
        )
    return transcription
