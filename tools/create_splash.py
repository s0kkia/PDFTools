from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path("build_assets/splash.png")
OUT.parent.mkdir(parents=True, exist_ok=True)
W, H = 900, 250
im = Image.new("RGB", (W, H), "#171a21")
d = ImageDraw.Draw(im)

# Match the dark PDFTools workspace: sidebar, work area, heading and divider.
d.rectangle((0, 0, 205, H), fill="#202530")
d.text((28, 34), "PDFTools", fill="#e8eaf0", font=ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 28))
d.text((29, 78), "РАБОЧЕЕ ПРОСТРАНСТВО", fill="#9ca7b8", font=ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 11))
d.text((29, 126), "PDF", fill="#356fe5", font=ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 13))
d.text((29, 155), "Запуск приложения", fill="#9ca7b8", font=ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 11))

d.text((240, 28), "Главная", fill="#e8eaf0", font=ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 25))
d.line((240, 82, 870, 82), fill="#394355", width=1)
d.text((240, 214), "Подготавливаем рабочее пространство PDFTools…", fill="#9ca7b8", font=ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 12))
im.save(OUT)
print(f"Created {OUT} ({W}x{H})")
