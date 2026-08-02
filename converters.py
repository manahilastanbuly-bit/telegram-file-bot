import asyncio
import os
import uuid
import fitz  # PyMuPDF
from PIL import Image, ImageOps
from pdf2docx import Converter
from pypdf import PdfReader, PdfWriter


# --- 1. تحويل Word/PPT إلى PDF ---
async def convert_to_pdf(input_path: str, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    profile_dir = os.path.join(output_dir, f"profile_{uuid.uuid4().hex}")
    os.makedirs(profile_dir, exist_ok=True)

    cmd = [
        "soffice", "--headless", "--norestore",
        f"-env:UserInstallation=file://{profile_dir}",
        "--convert-to", "pdf", "--outdir", output_dir, input_path
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await asyncio.wait_for(process.communicate(), timeout=180)

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.pdf")
    if not os.path.exists(output_path):
        raise RuntimeError("فشل تحويل الملف إلى PDF.")
    return output_path


# --- 2. تحويل الصور إلى PDF ---
async def convert_images_to_pdf(image_paths: list[str], output_pdf_path: str) -> str:
    processed_images = []
    for path in image_paths:
        img = Image.open(path)
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        processed_images.append(img)

    if processed_images:
        processed_images[0].save(
            output_pdf_path, "PDF", save_all=True, append_images=processed_images[1:]
        )
    return output_pdf_path


# --- 3. تحويل PDF إلى Word ---
async def convert_pdf_to_word(input_path: str, output_docx_path: str) -> str:
    def _convert():
        cv = Converter(input_path)
        cv.convert(output_docx_path, start=0, end=None)
        cv.close()

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _convert)
    return output_docx_path


# --- 4. تحويل PDF إلى PowerPoint ---
async def convert_pdf_to_ppt(input_path: str, output_dir: str) -> str:
    profile_dir = os.path.join(output_dir, f"profile_{uuid.uuid4().hex}")
    os.makedirs(profile_dir, exist_ok=True)

    cmd = [
        "soffice", "--headless", "--norestore",
        f"-env:UserInstallation=file://{profile_dir}",
        "--convert-to", "pptx", "--outdir", output_dir, input_path
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await asyncio.wait_for(process.communicate(), timeout=180)

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.pptx")
    if not os.path.exists(output_path):
        raise RuntimeError("فشل تحويل PDF إلى PowerPoint.")
    return output_path


# --- 5. تحويل PDF إلى صور (JPEG / PNG) ---
async def convert_pdf_to_images(input_path: str, output_dir: str, fmt: str = "jpeg") -> list[str]:
    def _extract():
        doc = fitz.open(input_path)
        image_paths = []
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=150)
            img_path = os.path.join(output_dir, f"page_{i+1}.{fmt}")
            pix.save(img_path)
            image_paths.append(img_path)
        doc.close()
        return image_paths

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _extract)


# --- 6. حماية ملف PDF بكلمة مرور ---
async def protect_pdf(input_path: str, output_path: str, password: str) -> str:
    reader = PdfReader(input_path)
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    writer.encrypt(password)
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path


# --- 7. فك كلمة مرور PDF ---
async def unlock_pdf(input_path: str, output_path: str, password: str) -> str:
    reader = PdfReader(input_path)
    if reader.is_encrypted:
        if not reader.decrypt(password):
            raise ValueError("كلمة المرور غير صحيحة.")
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path


# --- 8. ضغط ملف PDF ---
async def compress_pdf(input_path: str, output_path: str) -> str:
    cmd = [
        "gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
        "-dPDFSETTINGS=/ebook", "-dNOPAUSE", "-dQUIET", "-dBATCH",
        f"-sOutputFile={output_path}", input_path
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await asyncio.wait_for(process.communicate(), timeout=180)
    return output_path


# --- 9. OCR جعل PDF قابل للبحث ---
async def convert_pdf_to_searchable(input_path: str, output_pdf_path: str) -> str:
    cmd = [
        "ocrmypdf", "-l", "ara+eng", "--skip-text", "--jobs", "1",
        "--output-type", "pdf", input_path, output_pdf_path
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await asyncio.wait_for(process.communicate(), timeout=600)
    return output_pdf_path
