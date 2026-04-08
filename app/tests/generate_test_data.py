"""
Generate test fixture files for receipt pipeline tests.

Run once:  python tests/generate_fixtures.py

Creates:
  tests/fixtures/receipt.jpg
  tests/fixtures/receipt.png
  tests/fixtures/receipt.pdf

Each contains the same receipt text, readable by tesseract OCR.
"""

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

FIXTURES_DIR = Path(__file__).parent / "fixtures"

RECEIPT_TEXT = """ACME GROCERY STORE
123 Main Street
Date: 2026-03-15

Milk          $3.99
Bread         $2.49
Eggs          $4.99
Discount     -$1.00

Tax           $0.84
Total        $11.31

Payment: Visa ****1234

Thank you for shopping!"""


def create_receipt_image() -> Image.Image:
    """Render receipt text onto a white image."""
    img = Image.new("RGB", (600, 500), "white")
    draw = ImageDraw.Draw(img)

    # use default font at readable size
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 18)
    except OSError:
        font = ImageFont.load_default()

    draw.text((30, 20), RECEIPT_TEXT, fill="black", font=font)
    return img


def generate_jpeg(path: Path):
    img = create_receipt_image()
    img.save(path, "JPEG", quality=95)
    print(f"Created {path}")


def generate_png(path: Path):
    img = create_receipt_image()
    img.save(path, "PNG")
    print(f"Created {path}")


def generate_pdf(path: Path):
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    text_obj = c.beginText(50, height - 50)
    text_obj.setFont("Courier", 14)
    for line in RECEIPT_TEXT.split("\n"):
        text_obj.textLine(line)
    c.drawText(text_obj)
    c.save()
    print(f"Created {path}")


def main():
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    generate_jpeg(FIXTURES_DIR / "receipt.jpg")
    generate_png(FIXTURES_DIR / "receipt.png")
    generate_pdf(FIXTURES_DIR / "receipt.pdf")
    print("All fixtures generated.")


if __name__ == "__main__":
    main()