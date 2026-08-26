"""引擎连通性测试：验证 DeepSeek / 免费引擎能否正常搜题。

用法（任选）：
  1. 直接运行，按提示输入 key：  python test_engine.py
  2. 带参数： python test_engine.py --provider deepseek --key sk-xxxx
     python test_engine.py --provider free --key xxxx --free-provider zhipu
  3. 环境变量： DEEPSEEK_KEY=sk-xxx FREE_KEY=xxx python test_engine.py --all

不会把 key 写入任何文件。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from solver.engines import solve, EngineError, FREE_PROVIDERS, probe_free_engine

TEST_QUESTIONS = [
    "已知一次函数 y=2x+1，求它与 x 轴的交点坐标。",
    "英语选择题：He said he ___ the book before 2010. A. has read B. had read C. read D. reads",
]


def run_provider(provider, api_key, **kw):
    print(f"\n===== 测试引擎：{provider} =====")
    for i, q in enumerate(TEST_QUESTIONS, 1):
        print(f"\n[题目{i}] {q[:50]}…")
        try:
            result = solve(q, provider=provider, api_key=api_key, **kw)
            print(f"[√] {result.engine_name} · {result.model} · {result.elapsed:.1f}s")
            preview = " ".join(result.text.split())
            print(f"    答案预览：{preview[:120]}…")
        except EngineError as e:
            print(f"[×] {e}")
            return False
    return True


def main():
    ap = argparse.ArgumentParser(description="搜题引擎连通性测试")
    ap.add_argument("--provider", choices=["deepseek", "free", "all"], default=None)
    ap.add_argument("--key", default="")
    ap.add_argument("--free-provider", choices=list(FREE_PROVIDERS.keys()), default="zhipu")
    args = ap.parse_args()

    provider = args.provider
    if provider is None:
        provider = "all"

    all_ok = True
    if provider in ("deepseek", "all"):
        key = args.key or os.environ.get("DEEPSEEK_KEY", "")
        if not key:
            key = input("请输入 DeepSeek API Key（sk- 开头，不会保存）：").strip()
        if not key:
            print("未提供 Key，跳过 DeepSeek 测试")
            all_ok = False
        else:
            ok = run_provider("deepseek", key)
            all_ok = all_ok and ok

    if provider in ("free", "all"):
        key = args.key or os.environ.get("FREE_KEY", "")
        if not key:
            key = input("请输入免费平台 API Key（智谱 open.bigmodel.cn 或硅基流动注册）：").strip()
        if not key:
            print("未提供 Key，跳过免费引擎测试")
            all_ok = False
        else:
            print("\n先探测哪个免费平台可用…")
            try:
                hit = probe_free_engine(key)
                print(f"[√] 可用平台：{hit['display']}（{hit['model']}）")
                ok = run_provider("free", key, free_provider=hit["provider"],
                                  model=hit["model"])
                all_ok = all_ok and ok
            except EngineError as e:
                print(f"[×] 免费平台探测失败：{e}")
                all_ok = False

    print("\n" + ("===== 全部通过，可以去设置里填 Key 正式使用了 ====="
                  if all_ok else "===== 有失败项，请检查上面的错误信息 ====="))


if __name__ == "__main__":
    main()
