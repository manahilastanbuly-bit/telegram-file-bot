import asyncio
import os
import uuid
from PIL import Image, ImageOps


async def convert_to_pdf(input_path: str, output_dir: str) -> str:
    """
    يحول ملفات Word (.docx/.doc) و PowerPoint (.pptx/.ppt) إلى PDF عبر LibreOffice.
    """
    os.makedirs(output_dir, exist_ok=True)

    # إنشاء مجلد ملف شخصي مؤقت لتفادي التعارض عند التحويل المتزامن
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


async def convert_images_to_pdf(image_paths: list[str], output_pdf_path: str) -> str:
    """
    تحويل قائمة من الصور إلى ملف PDF واحد منسق ومُعدّل الاتجاه.
    """
    processed_images = []

    for path in image_paths:
        img = Image.open(path)
        
        # تعديل اتجاه الصورة تلقائياً بناءً على وضعية التصوير (منع الصور المقلوبة)
        img = ImageOps.exif_transpose(img)
        
        # تحويل صيغ الألوان (مثل PNG الشفافة) إلى RGB المتوافقة مع PDF
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
            
        processed_images.append(img)

    if processed_images:
        # حفظ الصورة الأولى ودمج بقية الصور معها في ملف PDF واحد
        processed_images[0].save(
            output_pdf_path,
            "PDF",
            save_all=True,
            append_images=processed_images[1:]
        )

    return output_pdf_path
