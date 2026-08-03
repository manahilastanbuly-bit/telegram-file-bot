# استخدام صورة بايثون خفيفة الوزن وحديثة
FROM python:3.12-slim

# ---------- تحسينات البيئة (ضرورية لـ Render) ----------
# يمنع تخزين مخرجات الطباعة مؤقتاً (لرؤية السجلات فوراً)
ENV PYTHONUNBUFFERED=1
# يمنع إنشاء ملفات .pyc غير الضرورية
ENV PYTHONDONTWRITEBYTECODE=1

# ---------- تثبيت برامج النظام والخطوط ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
    # برامج التحويل والضغط الأساسية
    libreoffice \
    ghostscript \
    ffmpeg \
    # برنامج OCR ومعالجة الصور
    ocrmypdf \
    tesseract-ocr \
    tesseract-ocr-ara \
    tesseract-ocr-eng \
    # حزم الخطوط الأساسية (مهم جداً لتحويل المستندات العربية/الإنجليزية بشكل صحيح)
    fonts-liberation \
    fonts-dejavu-core \
    fonts-noto \
    # أداة مساعدة (اختياري)
    curl \
    # تنظيف قائمة الحزم لتقليل حجم الصورة النهائية
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ---------- إعداد بيئة التشغيل ----------
WORKDIR /app

# نسخ ملف المتطلبات أولاً لاستفادة من خاصية Cache في Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ بقية ملفات المشروع
COPY . .

# ---------- تحسين الأمان (مستحسن بشدة) ----------
# إنشاء مستخدم غير جذر (root) لتشغيل البوت، لحماية النظام داخل الحاوية
RUN addgroup --system appgroup && adduser --system --no-create-home --group appgroup
# منح المستخدم الجديد صلاحيات الوصول لمجلد التطبيق
RUN chown -R appgroup:appgroup /app
# التبديل إلى المستخدم الجديد
USER appgroup

# ---------- أمر التشغيل ----------
# استخدام "-u" لضمان عدم تخزين السجلات مؤقتاً حتى مع بايثون 3.12
CMD ["python", "-u", "bot.py"]
