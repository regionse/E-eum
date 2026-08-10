# -*- coding: utf-8 -*-
r"""JSX 주석이 «화면에 새어 나오는지» 정적으로 잡는다. LLM 0회 · 0원. (2026-08-09 신설)

왜 만들었나 — 실제로 이틀 동안 사용자 화면에 찍혀 있었다
  잇다 첫 화면, 인사말 «위»에 이것이 그대로 렌더링되고 있었다:
      글자 크기  －  100%  ＋
      를 못 쓴다. 주석은 여는 태그 «위»에 둔다. */}
      안녕하세요, 교육·상담을 맡은 잇다예요. …
  원인 — 그 주석이 「JSX 속성 안에는 중괄호 주석을 못 쓴다」고 «설명»하면서
    닫는 기호를 **글자로 적었다.** 자바스크립트 파서는 처음 만나는 닫는 기호에서
    주석을 끝내므로, 그 뒤의 글이 통째로 JSX 텍스트가 된다.
  ⚠ 이걸 고치다가 **같은 실수를 한 번 더 했다.** 사람 눈으로는 안 잡힌다.

왜 «백엔드 검사»로는 영원히 못 잡나
  골든셋·0원 검사·talk.py·페르소나 — 전부 엔진만 부른다. 화면을 아무도 안 연다.
  이건 브라우저를 열거나, 이렇게 소스를 읽는 수밖에 없다.

무엇을 보나
  ① 중괄호 주석이 «조기 종료»되는가
     여는 기호 뒤 첫 닫는 기호를 찾고, 그 다음 글자가 } 가 아니면 → 새어 나온다.
  ② JSX 자식 자리의 // 주석
     여는 태그 «안»(속성 목록)의 // 는 안전하다. 태그 «밖»(자식 자리)의 // 는 글자가 된다.
  ③ 렌더될 텍스트에 개발자 흔적 낱말
     TODO · FIXME · console.log · 「임시」 등이 따옴표 밖에 있으면 의심한다.

쓰는 법 (아무 데서나)
  python Backend/app/itda/scripts/checks/jsx_leak_test.py
  python .../jsx_leak_test.py --root frontend/src/pages/learn
"""
import argparse
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

#  ⚠ parents[5] 다 — checks/scripts/itda/app/Backend/E-eum-team 순이다.
#    2026-08-09 에 [4] 로 적었다가 Backend/frontend/src 를 봤고, 그 경로가 «없어서»
#    **0개 파일을 검사하고 「✅ 없음」이라고 보고했다.** 아래 «0개면 실패» 가드가 그래서 있다.
ROOT = Path(__file__).resolve().parents[5] / 'frontend' / 'src'
OPEN = '{' + '/' + '*'          # 여는 기호 — 이 파일 자신이 안 걸리게 조립해서 쓴다
CLOSE = '*' + '/'               # 닫는 기호
SUSPECT = ('TODO', 'FIXME', 'XXX', 'console.log', 'debugger')


def scan_comment_leak(src):
    """주석 «밖»에 닫는 기호가 나오는 자리를 찾는다 → [(줄번호, 새어나갈 글)]

    ★★ 논리를 한 번 다시 짰다(2026-08-09). 처음엔 「첫 닫는 기호 뒤가 } 가 아니면 누수」로
      봤는데, **실제 사고를 못 잡았다.** 사고 원문이 이랬기 때문이다:

          {/*  …  안에는 {/*…*/} 를 못 쓴다.
               주석은 여는 태그 «위»에 둔다. */}

      안쪽의 `*/}` 는 뒤에 } 가 붙어 있어 「제대로 닫힘」으로 보였다. 그런데 파서는
      **거기서 주석을 끝낸다.** 그 뒤의 「를 못 쓴다. …」가 통째로 화면 글자가 됐다.
      ⇒ 자기시험이 이걸 잡아냈다. 자기시험이 없었으면 「0건 · 깨끗함」으로 넘겼다.

    바뀐 규칙 — **닫는 기호가 «주석 안이 아닌 곳»에 나오면 누수다.**
      주석은 여는 기호에서 시작해 «첫» 닫는 기호에서 끝난다. 그 뒤에 또 닫는 기호가
      보이면, 그건 원래 주석의 일부였어야 할 글이 밖으로 나온 것이다.

    ⚠ 평범한 JS 주석(noop 표시 · jsdoc)까지 잡으면 안 된다. 그래서 **JSX 전용
      닫는 기호(닫는 기호 바로 뒤에 중괄호가 붙은 꼴)**가 «주석 밖»에 있을 때만 센다.
      (2026-08-09 — 이 조건을 안 걸었더니 오탐 12건이 났다)
    """
    JCLOSE = CLOSE + '}'
    out = []
    i = 0
    in_comment = False
    while i < len(src):
        if not in_comment:
            s = src.find(OPEN, i)
            j = src.find(JCLOSE, i)
            if j >= 0 and (s < 0 or j < s):
                #  주석 밖에서 JSX 닫는 기호를 만났다 → 앞의 주석이 «일찍 닫혔다»
                ln = src.count('\n', 0, j) + 1
                start = src.rfind('\n', 0, max(0, j - 130)) + 1
                out.append((ln, src[start:j + len(JCLOSE)].strip()[-72:]))
                i = j + len(JCLOSE)
                continue
            if s < 0:
                break
            in_comment = True
            i = s + len(OPEN)
        else:
            e = src.find(CLOSE, i)                  # 주석은 «첫» 닫는 기호에서 끝난다
            if e < 0:
                out.append((src.count('\n', 0, i) + 1, '(닫히지 않음)'))
                break
            in_comment = False
            i = e + len(CLOSE)
    return out


#  ★★ 2026-08-09 — 「JSX 자식 자리의 // 주석」 검사는 **넣었다가 뺐다.**
#  정규식으로 태그 깊이를 세려 했더니 «오탐 501건»이 나왔다 — < 와 > 가 비교연산자·
#  화살표함수에도 쓰이기 때문이다. 제대로 하려면 JSX 파서가 필요하다.
#  ⇒ 뺀다. **오탐 501건짜리 검사기는 아무도 안 본다. 없느니만 못하다.**
#    (골든셋이 「전부 통과」로 읽혀 진짜 실패를 덮은 것과 같은 종류의 해악이다)
#  이 부류는 «브라우저를 열어» 렌더된 글자를 보는 것이 맞다 — 아래 안내 참고.


def scan_suspect(src):
    out = []
    for n, line in enumerate(src.splitlines(), 1):
        for w in SUSPECT:
            if w in line and not line.strip().startswith(('//', '*', OPEN)):
                out.append((n, w, line.strip()[:60]))
    return out


def self_test():
    """★★ 검사기가 «진짜 그 버그»를 잡는지 먼저 증명한다.

    왜 — 0건이 나왔을 때 「깨끗하다」인지 「검사기가 아무것도 안 본다」인지 구별이 안 된다.
      오늘(2026-08-09) 경로를 한 자리 틀려 0개 파일을 검사하고 「✅ 없음」을 찍었다.
    ⇒ 실제로 화면에 새어 나갔던 **그 글자 그대로**를 넣어 «잡히는지» 본다.
      이게 실패하면 아래 본 검사 결과는 «믿을 수 없다».
    """
    #  실제 사고 원문. 닫는 기호를 «글자로» 적어 주석이 거기서 끝났다.
    broken = ('        ' + OPEN + '  높이를 화면에 맞춘다\n'
              '           JSX 속성 목록 안에는 ' + OPEN + '…' + CLOSE + '} 를 못 쓴다.\n'
              '           주석은 여는 태그 «위»에 둔다. ' + CLOSE + '}\n'
              '        <div className="chat-wrap">\n')
    good = ('        ' + OPEN + '  높이를 화면에 맞춘다\n'
            '           속성 목록 안에는 중괄호 주석을 못 쓴다.\n'
            '           주석은 여는 태그 «위»에 둔다. ' + CLOSE + '}\n'
            '        <div className="chat-wrap">\n')
    hit_bad = scan_comment_leak(broken)
    hit_good = scan_comment_leak(good)
    ok = bool(hit_bad) and not hit_good
    print(f'  자기시험  깨진 주석 {"잡음 ✅" if hit_bad else "🔴 «못 잡음»"}'
          f' · 멀쩡한 주석 {"안 잡음 ✅" if not hit_good else "🔴 «오탐»"}')
    if hit_bad:
        print(f'            └ 잡아낸 누수 → 「{hit_bad[0][1]}」')
    if not ok:
        print('  🔴 검사기 자신이 고장났다. 아래 결과를 믿지 마라.')
        sys.exit(3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=str(ROOT))
    a = ap.parse_args()
    self_test()
    root = Path(a.root)
    files = sorted(root.rglob('*.jsx')) + sorted(root.rglob('*.js'))

    print('=' * 92)
    print(f'  JSX 화면 누수 검사 — {len(files)}개 파일 · LLM 0회 · 0원')
    print(f'  대상 {root}')
    print('=' * 92)

    #  ★★ 「검사할 게 없는데 통과라고 말하는 것」을 막는다.
    #    경로를 한 자리 틀렸다가 0개를 검사하고 「✅ 없음」을 찍은 적이 있다(2026-08-09).
    #    검사기가 «조용히 아무것도 안 하는 것»이 버그를 놓치는 것보다 나쁘다 —
    #    통과 표시를 보고 안심하기 때문이다.
    if len(files) < 10:
        print(f'  🔴 파일이 {len(files)}개뿐이다. 경로가 틀렸을 가능성이 높다 — 검사를 멈춘다.')
        sys.exit(2)

    n_leak = n_susp = 0
    for f in files:
        src = f.read_text(encoding='utf-8', errors='replace')
        rel = f.relative_to(root)
        for ln, leak in scan_comment_leak(src):
            n_leak += 1
            print(f'  🔴 주석 조기종료   {rel}:{ln}')
            print(f'       화면에 나옴 → 「{leak}」')
        for ln, w, txt in scan_suspect(src):
            n_susp += 1
            print(f'  ⚠ 개발 흔적 {w:12s} {rel}:{ln}  「{txt}」')

    print('-' * 92)
    print(f'  주석 조기종료 {n_leak}건 · 개발 흔적 {n_susp}건   ({len(files)}개 파일)')
    if n_leak:
        print('  🔴 주석 조기종료는 «반드시» 고쳐야 한다 — 그 글이 사용자 화면에 그대로 나온다.')
    else:
        print('  ✅ 화면에 새어 나오는 주석 없음')
    print('  ※ 이 검사가 못 잡는 것 — JSX 자식 자리의 // 주석. 파서가 필요하다.')
    print('    그 부류는 «브라우저를 열어» 렌더된 글자를 보는 수밖에 없다.')
    sys.exit(1 if n_leak else 0)


main()
