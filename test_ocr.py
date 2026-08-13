"""OCR 冒烟测试：生成带文字的图，跑 RapidOCR 识别。"""
import sys
sys.path.insert(0, ".")
from PIL import Image, ImageDraw, ImageFont
from translator import ocr

# 生成一张带英文文本的测试图
img = Image.new("RGB", (640, 140), "white")
d = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 42)
except Exception:
    font = ImageFont.load_default()
d.text((24, 40), "Save your work now", fill="black", font=font)
img.save("test_image.png")
print("测试图已生成")

# 用文件路径识别
text = ocr.recognize("test_image.png")
print("路径识别 ->", repr(text))

# 用 PNG 字节识别（模拟真实流程）
with open("test_image.png", "rb") as f:
    data = f.read()
text2 = ocr.recognize(data)
print("字节识别 ->", repr(text2))
