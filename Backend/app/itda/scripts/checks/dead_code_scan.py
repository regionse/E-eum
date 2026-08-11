# -*- coding: utf-8 -*-
r"""«실제로 안 불리는» 코드를 찾는다 — 주석·독스트링을 «빼고» 센다 (2026-08-11). **0원**

왜 이렇게 세나
  텍스트로 이름을 세면 **주석에만 나오는 것도 「참조됨」으로 잡힌다.**
  이 레포는 주석 밀도가 매우 높아서(파일의 절반 이상) 그 오차가 크다.
  실제로 처음 만든 스캔이 「죽은 것 1개」라고 했는데, 그건 틀린 계측이었다.

  ⇒ `ast` 로 «코드 노드»만 본다. 주석은 ast 에 아예 안 들어오고,
    독스트링은 Expr(Constant) 이라 이름 참조로 안 세어진다.

무엇을 세나
  정의  — 함수 · 메서드 · 클래스 · 모듈 상수(대문자)
  참조  — ast.Name(Load) · ast.Attribute(attr) · 데코레이터 · 문자열이 아닌 모든 이름 사용
  ⇒ 참조 0 이면 «코드에서 아무도 안 부른다».

⚠ 이 도구가 못 보는 것 (삭제 전에 반드시 사람이 확인)
  · `getattr(x, '이름')` · `globals()['이름']` 처럼 **문자열로 부르는 것**
  · FastAPI 라우트 함수처럼 **데코레이터가 등록만 하고 이름으로 안 부르는 것**
  · 프론트(JS)나 다른 서비스가 HTTP 로 쓰는 것
  · `__init__.py` 재수출 · 테스트/스크립트에서만 쓰는 것(그건 아래에 따로 표시한다)

쓰는 법 (Backend/ 에서)
  python app/itda/scripts/checks/dead_code_scan.py
  python app/itda/scripts/checks/dead_code_scan.py --lines   # 줄 수까지
"""
import argparse
import ast
import io
import os
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = Path(os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..')))     # …/Backend/app
FILES = [p for p in ROOT.rglob('*.py') if '__pycache__' not in str(p)]
#  «런타임»과 «도구»를 가른다 — 스크립트에서만 쓰는 것은 런타임에선 죽은 것이다.
def is_tool(p):
    s = str(p).replace('\\', '/')
    return '/scripts/' in s or '/checks/' in s


def strip_line(p, ln):
    try:
        return p.read_text(encoding='utf-8').splitlines()[ln - 1].strip()[:60]
    except Exception:                                   # noqa: BLE001
        return ''


defs = {}          # (파일, 이름) -> (종류, 줄, 줄수)
skipped = []       # 데코레이터가 붙은 것 — 프레임워크가 부른다
used_rt, used_tool = set(), set()


def _collect_defs(body, p, depth=0):
    """**모듈/클래스 «본문»만** 훑는다 — 함수 안의 지역 정의는 안 센다.

    ★ 2026-08-11 — 처음엔 ast.walk 로 전부 훑었다가 크게 틀렸다:
      · 클래스 본문의 상수(enum 멤버 STUDENT·PARENT…)가 「죽음」으로 잡혔다
      · 함수 안의 지역 상수도 잡혔다
    """
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, 'end_lineno', node.lineno) or node.lineno
            #  ★ 데코레이터가 붙은 것은 **프레임워크가 이름 없이 부른다.**
            #    FastAPI 라우트(@router.get) · Pydantic 검증자(@field_validator) 등.
            #    이걸 안 걸러서 처음에 router.py 함수 20개를 「죽음」이라고 했다.
            if node.decorator_list:
                _d = [ast.unparse(d).split('(')[0] for d in node.decorator_list]
                if not all(x in ('staticmethod', 'classmethod') for x in _d):
                    skipped.append((p, node.name, ' · '.join(_d)[:30]))
                    continue
            defs[(p, node.name)] = ('def', node.lineno, end - node.lineno + 1)
        elif isinstance(node, ast.ClassDef):
            end = getattr(node, 'end_lineno', node.lineno) or node.lineno
            defs[(p, node.name)] = ('class', node.lineno, end - node.lineno + 1)
            _collect_defs(node.body, p, depth + 1)      # 메서드는 본다
        elif isinstance(node, ast.Assign) and depth == 0:
            #  ★ 모듈 수준 상수만. 클래스 본문 상수는 enum 멤버라 이름으로 안 불린다.
            for t in node.targets:
                n = getattr(t, 'id', None)
                if n and re.fullmatch(r'_?[A-Z][A-Z0-9_]*', n) and len(n) > 2:
                    end = getattr(node, 'end_lineno', node.lineno) or node.lineno
                    defs[(p, n)] = ('const', node.lineno, end - node.lineno + 1)


for p in FILES:
    try:
        #  ★ utf-8-sig — PowerShell 이 붙인 BOM 때문에 utf-8 로는 체한다.
        #    (파이썬 import 는 BOM 을 알아서 처리하므로 «파일은 멀쩡하다»)
        src = p.read_text(encoding='utf-8-sig')
        tree = ast.parse(src)
    except Exception as e:                              # noqa: BLE001
        print(f'  (파싱 실패 {p.name}: {type(e).__name__})')
        continue

    _collect_defs(tree.body, p)
    for node in ast.walk(tree):
        #  ── 참조 (주석·독스트링은 ast 에 없다) ──
        tgt = used_tool if is_tool(p) else used_rt
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            tgt.add(node.id)
        elif isinstance(node, ast.Attribute):
            tgt.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                tgt.add(a.name)
                if a.asname:
                    tgt.add(a.asname)
        elif isinstance(node, ast.keyword) and node.arg:
            tgt.add(node.arg)

ap = argparse.ArgumentParser()
ap.add_argument('--lines', action='store_true')
a = ap.parse_args()

dead, tool_only = [], []
for (p, name), (kind, ln, nl) in defs.items():
    if name.startswith('__') or is_tool(p):
        continue                       # 도구 파일의 정의는 여기서 안 따진다
    if name in used_rt:
        continue
    (tool_only if name in used_tool else dead).append((p, name, kind, ln, nl))

dead.sort(key=lambda r: -r[4])
tool_only.sort(key=lambda r: -r[4])

print('=' * 104)
print(f'  죽은 코드 스캔 — 파일 {len(FILES)}개 · 정의 {len(defs)}개 · **주석 제외** · 0원')
print('=' * 104)
print()
print(f'  ── ① 런타임에서도 도구에서도 «안 불리는» 것 : {len(dead)}개 '
      f'({sum(r[4] for r in dead):,}줄) ──')
for p, name, kind, ln, nl in dead:
    print(f'    {kind:6s} {name:32s} {nl:5d}줄  {p.name}:{ln}')
print()
print(f'  ── ② 런타임엔 없고 «스크립트·검사»에서만 쓰는 것 : {len(tool_only)}개 '
      f'({sum(r[4] for r in tool_only):,}줄) ──')
for p, name, kind, ln, nl in tool_only[:30]:
    print(f'    {kind:6s} {name:32s} {nl:5d}줄  {p.name}:{ln}')
if len(tool_only) > 30:
    print(f'    … 외 {len(tool_only)-30}개')
print()
print('=' * 104)
print(f'  ①+② 합계 **{sum(r[4] for r in dead) + sum(r[4] for r in tool_only):,}줄**')
print(f'  (데코레이터가 붙어 «프레임워크가 부르는» 것 {len(skipped)}개는 애초에 제외했다)')
print('  ⚠ 문자열 호출(getattr·globals)·프론트 HTTP 사용은 여전히 못 본다.')
print('    ②는 «지우면 안 되는 것»이 섞여 있다 — 검사 도구가 쓰는 것이다.')

#  ── 주석 밀도 (「주석 70%가 옛날」이라는 지적을 숫자로 ) ─────────────
print()
print('  ── 주석·독스트링이 차지하는 비율 (런타임 파일만) ──')
tot_all = tot_cmt = 0
rows_c = []
for p in FILES:
    if is_tool(p):
        continue
    try:
        lines = p.read_text(encoding='utf-8-sig').splitlines()
    except Exception:                                   # noqa: BLE001
        continue
    if len(lines) < 80:
        continue
    cmt = sum(1 for x in lines if x.strip().startswith('#'))
    rows_c.append((len(lines), cmt, p.name))
    tot_all += len(lines)
    tot_cmt += cmt
rows_c.sort(reverse=True)
for n, c, nm in rows_c[:8]:
    print(f'    {nm:22s} {n:6,}줄 중 주석 {c:5,}줄 ({c/n*100:4.0f}%)')
print(f'    {"합계":22s} {tot_all:6,}줄 중 주석 {tot_cmt:5,}줄 '
      f'(**{tot_cmt/max(1,tot_all)*100:.0f}%**)')
print('  ※ 「#」로 시작하는 줄만 셌다. 독스트링은 «안» 셌으니 실제 비중은 더 크다.')
