# -*- coding: utf-8 -*-
r"""칩 이름이 «포함 관계»일 때 pick_from_options 가 옳게 고르나 (2026-08-11). **0원**

왜 — 브라우저 시연에서 실제로 겪었다.
  칩 [시각디자인·편집디자인·영상그래픽·**편집**·**영상편집**]
  🧑「영상편집이요」 → 🤖「'편집' 쪽으로 찾아봤어요」 · 카드 = 편집(인쇄·출판)
  '편집'도 '영상편집'도 발화에 «들어 있어» 복수선택으로 읽혔고, 호출부가 첫 번째를 집었다.

⚠ 고치면서 «진짜 복수선택»을 깨뜨리면 안 된다 — 그건 Bing 실운영 근거로 넣은 기능이다.
  그래서 아래에 포함 관계가 «아닌» 복수선택도 같이 넣어 둔다.

쓰는 법 (Backend/ 에서)
  python app/itda/scripts/checks/pick_overlap_test.py
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from app.itda.itda_core import pick_from_options                    # noqa: E402

CHIPS = ['시각디자인', '편집디자인', '영상그래픽', '편집', '영상편집']
NARROW = ['요양지원', '아이돌봄', '산후육아지원']

#  (칩목록, 발화, 기대값)   기대값이 list 면 복수선택
CASES = [
    #  ── 포함 관계 — 이번에 고친 것 ──
    (CHIPS, '영상편집이요', '영상편집'),
    (CHIPS, '영상편집이요. 근데 저는 집 밖으로 오래 못 나가요.', '영상편집'),
    (CHIPS, '편집디자인 할래요', '편집디자인'),
    (CHIPS, '영상그래픽이 좋아요', '영상그래픽'),
    #  ── 짧은 것만 말했으면 짧은 것 (긴 것이 애초에 안 걸린다) ──
    (CHIPS, '편집이요', '편집'),
    (CHIPS, '편집 쪽으로 해주세요', '편집'),
    #  ── 진짜 복수선택 — 깨지면 안 된다 ──
    (NARROW, '요양지원이랑 아이돌봄이요', ['요양지원', '아이돌봄']),
    (CHIPS, '편집디자인이랑 영상편집이요', ['편집디자인', '영상편집']),
    #  ── 순서 표현 (② 경로 — 이 파일이 고친 ①과 무관하다) ──
    (CHIPS, '4번', '편집'),
    #  ⚠ **알려진 한계(2026-08-11 실측)** — ordinal_of 는 **1~4번까지만** 읽는다.
    #    '다섯번째'·'5번'·'다섯째' → None.  그런데 좁히기 칩은 5개까지 나온다(실측).
    #    즉 «마지막 칩을 순서로 못 고른다». 여기 기대값을 None 으로 박아 두는 것은
    #    「맞다」는 뜻이 아니라 **지금 이렇다는 기록**이다. 고치면 이 줄이 먼저 깨진다.
    (CHIPS, '다섯 번째요', None),
    (CHIPS, '5번', None),
    #  ── 아무것도 안 고른 발화 ──
    (CHIPS, '잘 모르겠어요', None),
]

print('=' * 96)
print('  칩 포함 관계 — pick_from_options  ·  **0원**')
print('=' * 96)
ok = 0
for chips, msg, want in CASES:
    got = pick_from_options(msg, chips)
    good = got == want
    ok += good
    print(f'  {"✅" if good else "🔴"} 「{msg}」')
    print(f'       기대 {want!r}   실제 {got!r}')
print()
print(f'  {ok}/{len(CASES)} 통과')
if ok != len(CASES):
    sys.exit(1)
