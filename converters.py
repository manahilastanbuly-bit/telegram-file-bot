"""
تحويل ملفات Word (.docx/.doc) و PowerPoint (.pptx/.ppt) إلى PDF
باستخدام LibreOffice في وضع headless (بدون واجهة رسومية).
"""

import asyncio
import os
import uuid


async def convert_to_pdf(input_path: str, output_dir: str) -> str:
    """
    يحول أي ملف (docx, doc, pptx, ppt, xlsx ...) إلى PDF عبر LibreOffice.
    يرجع مسار ملف الـ PDF الناتج.
    """
    os.makedirs(output_dir, exist_ok=True)

    # كل عملية تحويل تحتاج مجلد إعدادات مستخدم (profile) خاص بها
    # عشان نتفادى تعارض إذا صارت أكثر من عملية تحويل بنفس الوقت
    profile_dir = os.path.join(output_dir, f"profile_{uuid.uuid4().hex}")
    os.makedirs(profile_dir, exist_ok=True)

    cmd = [
        "soffice",
        "--headless",
        "--norestore",
        f"-env:UserInstallation=file://{profile_dir}",
        "--convert-to", "pdf",
        "--outdir", output_dir,
        input_path,
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)

    if process.returncode != 0:
        raise RuntimeError(
            f"فشل تحويل الملف إلى PDF: {stderr.decode(errors='ignore')}"
        )

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.pdf")

    if not os.path.exists(output_path):
        raise RuntimeError("لم يتم إنشاء ملف PDF، تأكد أن الملف صحيح وغير تالف.")

    return output_path
