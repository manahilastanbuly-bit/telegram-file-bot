"""
تحويل الصوت إلى نص باستخدام faster-whisper (نسخة محسّنة من Whisper).
يدعم العربية والإنجليزية وأي لغة أخرى بدقة عالية، ويشتغل محليًا بدون تكلفة API.
"""

import asyncio
import os

from faster_whisper import WhisperModel

# نموذج الدقة العالية. الخيارات المتاحة (من الأصغر للأكبر/الأدق):
# tiny, base, small, medium, large-v3
#
# "base" هو الافتراضي هنا لأنه يشتغل بأمان ضمن الرام المحدودة (~512 ميجا)
# على خطة Render المجانية. لو تنقل لسيرفر بموارد أكبر (VPS/Pi)،
# غيّر متغير البيئة WHISPER_MODEL إلى "small" أو "medium" أو "large-v3"
# لدقة أعلى.
MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")

_model = None


def _load_model():
    global _model
    if _model is None:
        # compute_type="int8" يخلي النموذج يشتغل بكفاءة على CPU بدون GPU
        _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


def _transcribe_sync(audio_path: str) -> str:
    model = _load_model()
    # language=None يخلي النموذج يكتشف اللغة تلقائيًا (عربي/إنجليزي/غيره)
    segments, info = model.transcribe(
        audio_path,
        language=None,
        beam_size=5,
        vad_filter=True,  # يشيل فترات الصمت لتحسين الدقة والسرعة
    )
    text = " ".join(segment.text.strip() for segment in segments)
    return text.strip()


async def transcribe_audio(audio_path: str) -> str:
    """يحول ملف صوتي إلى نص (يعمل بشكل غير متزامن حتى لا يوقف البوت)."""
    loop = asyncio.get_running_loop()
    text = await loop.run_in_executor(None, _transcribe_sync, audio_path)
    if not text:
        raise RuntimeError("لم أتمكن من استخراج أي نص من هذا الملف الصوتي.")
    return text
