# -*- coding: utf-8 -*-
r"""낱말표가 «어떻게» 걸리는지 한 발화에 대해 전 단계를 찍는다 (2026-08-11). **0원**

왜 만들었나
  「걸린다/안 걸린다」만 보면 어디서 갈렸는지 알 수 없다. 실제로는 4단계다:
      ① 정규화 4벌을 만든다        (원문 · evade · compose · strip)
      ② 어절 시작 위치를 기억한다   (_wseg 가 반환하는 두 번째 값)
      ③ 낱말이 «어절 시작»에서 시작할 때만 인정한다 (_wmatch · FUSE)
      ④ 걸린 뒤에도 「상대를 향한 것인가」를 한 번 더 본다 (_is_abuse_at_bot)
  ③에서 걸리고 ④에서 풀리는 경우가 실제로 있다. 그게 안 보이면 「낱말이 없나 보다」라고
  잘못 진단하고 낱말을 더 넣게 된다.

쓰는 법 (Backend/ 에서)
  python app/itda/scripts/checks/match_trace.py "병 신 아 진짜"
  python app/itda/scripts/checks/match_trace.py            # 기본 예시 묶음
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from app.itda import itda_core as I                                 # noqa: E402

#  (이름, 목록, 융합허용길이)  — pre_check 이 실제로 쓰는 순서대로
TABLES = [
    ('SELF_HARM', I.SELF_HARM, I.FUSE_CRISIS),
    ('HARM_OTHERS', I.HARM_OTHERS, I.FUSE_CRISIS),
    ('_SEXUAL_HARM', I._SEXUAL_HARM, I.FUSE_LOOSE),
    ('_SEXUAL_HARD', I._SEXUAL_HARD, I.FUSE_NONE),
    ('_SEXUAL_SOFT', I._SEXUAL_SOFT, I.FUSE_NONE),
    ('ABUSE', I.ABUSE, I.FUSE_NONE),
    ('_ABUSE_VARIANT', I._ABUSE_VARIANT, I.FUSE_NONE),
]
NAMES = ['원문   ', 'evade  ', 'compose', 'strip  ']


def hits(hay, starts, words, fuse):
    """_wmatch 와 «같은 규칙»으로, 다만 무엇이 어디서 걸렸는지까지 돌려준다."""
    out = []
    for b in words:
        if fuse and len(b) >= fuse and b in hay:
            out.append((b, hay.find(b), '융합'))
            continue
        i = hay.find(b)
        while i != -1:
            out.append((b, i, '어절시작' if i in starts else '어절중간(무시)'))
            i = hay.find(b, i + 1)
    return out


def trace(msg):
    print('═' * 96)
    print(f'  「{msg}」')
    print('═' * 96)

    segs = I._segs(msg)
    print('\n  ① 정규화 4벌 — 어절마다 따로 걸고 이어 붙인다(_wseg)')
    print(f'     {"":9s}{"결과":32s} 어절이 시작하는 위치')
    for nm, (hay, starts) in zip(NAMES, segs):
        mark = ''.join('^' if i in starts else ' ' for i in range(len(hay)))
        print(f'     {nm}  {hay}')
        print(f'     {"":9s}{mark}   {sorted(starts)}')

    print('\n  ② 어느 낱말표에 무엇이 걸리나')
    fired = []
    for tname, words, fuse in TABLES:
        rows = []
        for nm, (hay, starts) in zip(NAMES, segs):
            for b, i, how in hits(hay, starts, words, fuse):
                rows.append((nm.strip(), b, i, how))
        if not rows:
            continue
        ok = I._wmatch(segs, words, fuse)
        fuse_s = {0: 'FUSE_NONE(어절시작만)', 3: 'FUSE_CRISIS(3자↑ 중간도)',
                  4: 'FUSE_LOOSE(4자↑ 중간도)'}[fuse]
        print(f'     ── {tname}  ·  {fuse_s}  →  _wmatch = {ok}')
        for nm, b, i, how in rows:
            flag = '✅' if how in ('어절시작', '융합') else '  '
            print(f'        {flag} {nm:8s} 「{b}」 {i}번째 · {how}')
        if ok:
            fired.append(tname)

    if not fired:
        print('     (아무 낱말표도 안 걸렸다)')

    print('\n  ③ 걸린 뒤 — 「상대를 향한 것인가」 2차 판정')
    norm = I._norm_evade(msg)
    if {'ABUSE', '_ABUSE_VARIANT'} & set(fired):
        at = I._is_abuse_at_bot(msg, norm)
        p2 = bool(I._2P_RE.search(msg))
        imp = [t for t in I._IMPERATIVE_AT_BOT if t in msg.replace(' ', '')]
        cmd = [w for w in ('꺼져', '닥쳐') if w in norm]
        print(f'     _is_abuse_at_bot(msg, norm={norm!r}) = {at}')
        print(f'        · 2인칭(_2P_RE: 넌·너희·너님·니들·당신·느그·너·니) = {p2}')
        print(f'        · 명령형(_IMPERATIVE_AT_BOT) = {imp or "없음"}')
        print(f'        · 꺼져/닥쳐 (norm 안에서) = {cmd or "없음"}')
        print(f'     → {"UNSAFE(차단)" if at else "None(통과) ← 혼잣말로 본다"}')
    elif '_SEXUAL_SOFT' in fired:
        print(f'     _SEXUAL_SOFT 는 _is_at_bot 을 통과해야 한다 = {I._is_at_bot(msg)}')
    else:
        print('     (해당 없음)')

    print(f'\n  ④ pre_check 최종 = {I.pre_check(msg)!r}')
    print()


DEFAULT = [
    '야 이 병신아 너 진짜 쓸모없네',      # 걸리고 · 2인칭 있음 → 차단
    '병 신 아 진짜',                    # 걸리는데 · 2인칭 없음 → 통과
    'ㅂㅕㅇㅅㅣㄴ아 말 좀 알아들어',       # compose 로 걸리는데 → 통과
    '시1발 너 뭐하냐',                  # 숫자 삽입 → evade 가 편다
    '장애인 활동지원사 알려주세요',        # 어절 중간 매칭 → 일부러 무시
    '가슴 사이즈 얘기 좀 해봐',           # SOFT 인데 2인칭·명령형 없음 → 통과
]

for m in (sys.argv[1:] or DEFAULT):
    trace(m)
