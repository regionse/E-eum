# -*- coding: utf-8 -*-
r"""낱말표 전수 조사 — 어디에 몇 개가 있고, 무엇을 대조하나 (2026-08-11). **0원**

왜 만드나
  「낱말표 필요 없는 거 아니냐」는 물음에 답하려면 **먼저 다 세어야** 한다.
  grep 으로 어림잡지 않고 `ast` 로 파싱한다 — import 하면 모듈이 통째로 돌아
  비용이 나가는 것을 이 레포가 이미 겪었다(실측기록 §「ast 로 리터럴만 꺼냈다」).

무엇을 가르나 — 이 파일 3231행에 이미 답이 적혀 있다:
    「이건 낱말 목록이지만 **«닫힌 집합»**이다 — NCS 1,094개는 고정이라 셀 수 있다.
      오늘 내내 「낱말로 못 닫는다」고 한 것은 **«사용자 발화»(열린 집합)** 얘기다.」

  ⇒ **닫힌 집합**(직업명·자격증명·enum·URL·DB 값)을 대조하는 목록은 «명부»다. 문제없다.
    **열린 집합**(사람이 말하는 방식)을 대조하는 목록이 «낱말표»다. 그게 문제다.
    사람이 말하는 방식은 셀 수 없으므로, 목록으로는 원리상 못 닫는다.

쓰는 법 (Backend/ 에서)
  python app/itda/scripts/checks/wordlist_census.py
"""
import ast
import io
import os
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = Path(__file__).resolve().parents[3]        # …/Backend/app
TARGETS = ['itda/itda_core.py', 'itda/prompts.py', 'itda/controllers.py',
           'itda/match.py', 'itda/session.py']

HANGUL = re.compile(r'[가-힣]')


def _strings(node):
    """리터럴 튜플/리스트/집합 안의 문자열을 평평하게 — 중첩도 훑는다."""
    out = []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        out.append(node.value)
    elif isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        for e in node.elts:
            out += _strings(e)
    elif isinstance(node, ast.Call):                 # frozenset((...)) 꼴
        for a in node.args:
            out += _strings(a)
    elif isinstance(node, ast.BinOp):                # A + B 로 이어 붙인 목록
        out += _strings(node.left) + _strings(node.right)
    return out


rows = []
for rel in TARGETS:
    p = ROOT / rel
    if not p.exists():
        continue
    src = p.read_text(encoding='utf-8')
    tree = ast.parse(src)
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        tgt = node.targets[0]
        name = getattr(tgt, 'id', None)
        if not name or not re.fullmatch(r'_?[A-Z][A-Z0-9_]*', name):
            continue
        vals = _strings(node.value)
        #  한글이 든 «짧은 조각»의 모음만 낱말표 후보로 본다.
        #  (문장·안내문 상수는 길어서 걸러진다 — 그건 낱말표가 아니라 문구다)
        ko = [v for v in vals if HANGUL.search(v)]
        if len(ko) < 3:
            continue
        avg = sum(len(v) for v in ko) / len(ko)
        if avg > 14:                                  # 평균 15자 넘으면 «문구»다
            continue
        rows.append({'파일': rel.split('/')[-1], '이름': name, '개수': len(ko),
                     '평균길이': round(avg, 1), '줄': node.lineno,
                     '보기': ' · '.join(ko[:4])})

#  쓰이는 곳을 센다 (정의 줄은 뺀다)
allsrc = {rel.split('/')[-1]: (ROOT / rel).read_text(encoding='utf-8')
          for rel in TARGETS if (ROOT / rel).exists()}
for r in rows:
    n = 0
    for f, s in allsrc.items():
        n += len(re.findall(r'\b' + re.escape(r['이름']) + r'\b', s))
    r['쓰임'] = n - 1                                  # 정의 1회 제외


def w(s):
    return sum(2 if ord(c) > 0x2E80 else 1 for c in str(s))


def pad(s, n):
    return str(s) + ' ' * max(1, n - w(s))


rows.sort(key=lambda r: -r['개수'])
print('=' * 122)
print(f'  낱말표 전수 조사 — {len(rows)}개 · LLM 0회 · **0원**')
print('=' * 122)
print(f'  {pad("이름", 24)} {pad("개수", 6)} {pad("평균자", 7)} {pad("쓰임", 6)} '
      f'{pad("줄", 6)} 보기')
print('  ' + '-' * 118)
for r in rows:
    print(f'  {pad(r["이름"], 24)} {pad(r["개수"], 6)} {pad(r["평균길이"], 7)} '
          f'{pad(r["쓰임"], 6)} {pad(r["줄"], 6)} {r["보기"][:52]}')
print('  ' + '-' * 118)
print(f'  낱말 총 {sum(r["개수"] for r in rows):,}개')
print('=' * 122)
print('  ※ 「쓰임」은 이 파일들 안에서 이름이 등장한 횟수(정의 제외) — 주석 언급도 포함된다.')
print('  ⚠ 이 표는 «무엇을 대조하는지»는 모른다. 닫힌 집합(직업명 등)인지')
print('    열린 집합(사람 말)인지는 사람이 하나씩 봐야 한다.')
