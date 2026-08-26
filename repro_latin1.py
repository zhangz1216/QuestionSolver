# -*- coding: utf-8 -*-
"""复现 latin-1 编码错误：读真实配置 → 实测 free / deepseek 两个引擎。不打印 key 明文。"""
import sys, os, traceback
sys.path.insert(0, r'C:\Users\Administrator\Projects\QuestionSolver')
os.chdir(r'C:\Users\Administrator\Projects\QuestionSolver')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import winreg


def read_qsettings():
    for sub in (r'Software\QuestionSolver\QuestionSolver', r'Software\QuestionSolver'):
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub)
            out = {}
            i = 0
            while True:
                try:
                    n, v, t = winreg.EnumValue(k, i)
                    out[n] = v
                    i += 1
                except OSError:
                    break
            return out
        except FileNotFoundError:
            continue
    return None


cfg = read_qsettings()
if cfg is None:
    print('!!! 注册表没有 QuestionSolver 配置')
    sys.exit(1)

for n, v in cfg.items():
    s = str(v)
    if 'key' in n.lower():
        print(f'{n}: 长度{len(s)}, 前4={s[:4]!r}, 后4={s[-4:]!r}, 全ASCII={s.isascii()}')
    else:
        print(f'{n}: {v}')

from solver.engines import solve

dsk = str(cfg.get('deepseek_key', ''))
fk = str(cfg.get('free_key', ''))
fp = str(cfg.get('free_provider', 'zhipu'))
fm = str(cfg.get('free_model', ''))
dsm = str(cfg.get('deepseek_model', ''))

print(f'\n免费平台={fp}, free_model={fm!r}, free_key存在={bool(fk)}, deepseek_model={dsm!r}, ds_key存在={bool(dsk)}')

Q = '下面关于ArkTS中import用法，正确的是？'

print('\n===== 复现 free.solve（默认搜题路径） =====')
try:
    r = solve(Q, provider='free', api_key=fk, free_provider=fp, model=fm, timeout=20)
    print('OK:', r.text[:80])
except Exception as e:
    print('异常类型:', type(e).__name__)
    print('异常消息:', str(e))
    print('最后3行:', '\n'.join(traceback.format_exc().strip().splitlines()[-3:]))

print('\n===== 复现 deepseek.solve（深度重搜路径） =====')
try:
    r = solve(Q, provider='deepseek', api_key=dsk, model=dsm or 'deepseek-v4-flash', timeout=20)
    print('OK:', r.text[:80])
except Exception as e:
    print('异常类型:', type(e).__name__)
    print('异常消息:', str(e))
    print('最后3行:', '\n'.join(traceback.format_exc().strip().splitlines()[-3:]))
