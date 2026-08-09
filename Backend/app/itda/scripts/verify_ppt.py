# -*- coding: utf-8 -*-
"""생성한 pptx 를 «PowerPoint 로 실제로 열어» 확인한다. (2026-08-07 신설)

왜 만들었나 — 🔴 리허설 당일에 데인 것
  `build_ppt_team.py` 가 만든 덱이 **PowerPoint 에서 안 열렸다.** 그런데
    · python-pptx 로는 정상적으로 열렸다 (45장, 텍스트 전부 정상)
    · zip 무결성 검사 통과
    · 슬라이드 파일 수 == 인식 장수
  검사를 다 통과하는데 **정작 PowerPoint 가 거부했다.**
  원인은 슬라이드 복제 때 `notesSlide` 관계까지 복사한 것이었다(build_ppt_team.py 참고).

  ⇒ **「검사 통과 = 동작함」이 아니다.** 잇다 엔진에서 배운 것과 정확히 같은 교훈이
     발표 자료에서 되풀이됐다(골든셋 34/34 인데 카드가 전부 죽어 있던 일).
     열어보는 것 말고는 확인할 방법이 없다.

쓰는 법
  python verify_ppt.py <파일.pptx> [파일2.pptx ...]
  종료코드 0 = 전부 열림 / 1 = 하나라도 못 엶

⚠ Windows + PowerPoint 설치 필요. COM 을 쓴다.
⚠ 한글 경로에서 COM 이 실패한 적이 있다 → ASCII 경로로 «복사해서» 연다.
"""
import sys
import io
import os
import shutil
import subprocess
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PS = r'''
$app = New-Object -ComObject PowerPoint.Application
$code = 0
foreach ($p in @({paths})) {{
  try {{
    $pr = $app.Presentations.Open($p, $true, $false, $false)
    Write-Output ("OK`t" + $pr.Slides.Count + "`t" + $p)
    $pr.Close()
  }} catch {{
    Write-Output ("FAIL`t0`t" + $p)
    $code = 1
  }}
}}
$app.Quit()
exit $code
'''


def verify(paths):
    """pptx 들을 PowerPoint 로 열어본다. (열림여부, 장수) 목록을 준다."""
    tmp = tempfile.mkdtemp(prefix='pptverify_')
    try:
        #  ASCII 경로로 복사 — 한글 파일명에서 COM Open 이 실패한다
        mapping = []
        for i, src in enumerate(paths):
            dst = os.path.join(tmp, f'deck{i}.pptx')
            shutil.copy2(src, dst)
            mapping.append((src, dst))
        #  ⚠ PowerShell 의 큰따옴표 문자열에서 «역슬래시는 이스케이프 문자가 아니다»(백틱이다).
        #    처음에 파이썬 습관으로 '\\' → '\\\\' 로 바꿔 넣었더니 경로가 통째로 깨져서
        #    **정상 파일까지 「못 엶」으로 나왔다.** 검사기가 거짓말을 하면 검사가 없느니만 못하다.
        #    → 경로는 그대로 넣는다. 작은따옴표로 감싸 $ 치환도 막는다.
        quoted = ','.join("'%s'" % d.replace("'", "''") for _, d in mapping)
        script = PS.replace('{paths}', quoted).replace('{{', '{').replace('}}', '}')
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
                           capture_output=True, text=True)
        out = {}
        for line in r.stdout.splitlines():
            parts = line.strip().split('\t')
            if len(parts) == 3:
                out[os.path.normcase(parts[2])] = (parts[0] == 'OK', int(parts[1]))
        return [(src, *out.get(os.path.normcase(dst), (False, 0))) for src, dst in mapping]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    paths = sys.argv[1:]
    if not paths:
        print('쓰는 법: python verify_ppt.py <파일.pptx> [...]')
        return 2
    bad = 0
    for src, ok, n in verify(paths):
        print(f"  {'✅ 열림 ' if ok else '🔴 못엶 '} {n:>3}장  {os.path.basename(src)}")
        if not ok:
            bad += 1
    if bad:
        print(f'\n  🔴 {bad}개가 PowerPoint 에서 안 열린다. 발표에 쓰면 안 된다.')
    return 1 if bad else 0


sys.exit(main())
