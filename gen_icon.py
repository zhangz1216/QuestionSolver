"""生成应用图标 icon.ico（蓝底白字「译」）。"""
from PIL import Image, ImageDraw, ImageFont

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
# 圆角蓝底
d.rounded_rectangle([8, 8, SIZE - 8, SIZE - 8], radius=56, fill=(47, 123, 255, 255))
# 白字「译」
try:
    font = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 130)
except Exception:
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 130)
d.text((SIZE // 2, SIZE // 2 + 6), "译", font=font, fill="white", anchor="mm")

sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
img.save("icon.ico", sizes=sizes)
print("icon.ico 已生成")
