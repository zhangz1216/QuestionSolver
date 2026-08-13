"""临时验证脚本：用标准库 UTF-8 测试各翻译后端对日/韩/俄的识别与翻译。"""
import sys
sys.path.insert(0, ".")
from translator import translate

cases = [
    ("英语", "Hello, please save your work."),
    ("日语", "おはようございます、今日はいい天気ですね。"),
    ("韩语", "안녕하세요, 오늘 날씨가 좋네요."),
    ("俄语", "Здравствуйте, сегодня хорошая погода."),
]
for name, text in cases:
    try:
        out, src = translate.translate(text, target="zh-CN")
        print(f"[{name}] 检测={src} 译文={out}")
    except Exception as e:
        print(f"[{name}] 失败: {e}")
