# -*- coding: utf-8 -*-
r"""Solar 가 「종류」를 가를 수 있나 — Gemini 와 «같은 조건»으로 잰다. (2026-08-09)

왜 재나
  사용자 증언: 「원래 Solar 를 썼는데 «생각보다 말귀를 잘 못 알아들어서» 바꿨다.
              3.1 Flash 를 쓰다 가격이 심각해서 대용품을 찾던 중이었다.」
  그런데 itda_core.py:2967 주석 한 줄(「Solar 실측」) 말고는 **기록이 없다.**
  발표에서 「Solar 는 못 알아들었습니다」라고 말하려면 숫자가 있어야 한다.

⚠⚠ 먼저 적는 한계 — **당시 Solar 와 지금 Solar 는 다른 물건이다.**
  오늘(2026-08-09) 잡히는 모델: solar-pro4-260806(사흘 전) · pro3 · pro2 · mini.
  당시 어느 것을 썼는지 기록이 없다. 그래서 이 시험이 말할 수 있는 것은
    ✅ 「지금 Solar 로 다시 재보니 이렇다」
    ✗ 「그때 Solar 가 이래서 바꿨다」   ← 이건 «사용자 증언»이지 이 시험의 결과가 아니다
  둘을 섞어 말하지 않는다.

무엇을 재나 — kind_capability_test 와 «같은» 100케이스
  선호 3축(관심분야·활동유형·다루는대상)에 {값·근거·종류}를 얹어 뽑게 하고,
  기대한 종류가 나오는지 본다. 정의(KIND_DESC)는 두 모델에 «글자까지 같은 것»을 준다.

채점 규칙 — 두 모델에 똑같이 적용한다
  기대한 종류가 «슬롯 중 하나에라도» 나오면 맞음.
  ⚠ 관대한 규칙이다. 그래도 되는 이유는 «양쪽에 같이» 적용하기 때문이다.
    저장된 Gemini 원시응답을 이 규칙으로 «다시 채점»해서 비교한다 — 예전 점수를 그대로
    옮겨오지 않는다(조건이 다르면 비교가 안 된다).

비용
  Solar Pro3  $0.15 in / $0.60 out per 1M  (openrouter.ai 확인 2026-08-09)
  100케이스 ≈ 29원.  solar-mini 단가는 **확인 못 했다.**

쓰는 법 (Backend/ 에서)
  python app/itda/scripts/checks/solar_vs_gemini.py
  python app/itda/scripts/checks/solar_vs_gemini.py --models solar-pro3,solar-mini
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

HERE = Path(__file__).resolve().parent


#  ⚠ kind_capability_test 를 «import 하면 안 된다** — 그 파일은 마지막 줄이
#    `asyncio.run(main())` 이라 `if __name__` 가드가 없다. import 만으로 시험 전체가
#    돌아가고 LLM 비용이 나간다(2026-08-09 실제로 그랬다).
#  ⇒ 소스를 «읽어서» 리터럴만 꺼낸다. 실행하지 않는다.
def _pull(name):
    import ast
    src = (HERE / 'kind_capability_test.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return ast.literal_eval(node.value)
    raise SystemExit(f'{name} 을 못 찾았다')


CASES = _pull('CASES')
KIND_DESC = _pull('KIND_DESC')
ENV = HERE.parents[2] / '.env'
URL = 'https://api.upstage.ai/v1/chat/completions'
AXES = ['관심분야', '활동유형', '다루는대상']
_GKEY = ['']          # main() 에서 채운다

SYS = (
    '너는 진로 상담 챗봇의 «이해» 부분이다. 사용자의 한 마디에서 아래 세 칸을 뽑는다.\n'
    f'  관심분야 · 활동유형 · 다루는대상\n\n'
    '칸마다 {값, 근거, 종류} 를 담는다.\n'
    '  값   — 짧은 낱말\n'
    '  근거 — 사용자가 «실제로 한 말»에서 그대로 인용. 원문에 없는 말을 쓰지 마라\n'
    f'  종류 — {KIND_DESC}\n\n'
    '해당 없는 칸은 빈 배열로 둔다. 추측해서 채우지 마라.\n'
    'JSON 만 출력한다. 형식:\n'
    '{"관심분야":[{"값":"","근거":"","종류":"원함|해봤음|못함"}],'
    '"활동유형":[...],"다루는대상":[...]}'
)


def env():
    d = {}
    for ln in ENV.read_text(encoding='utf-8').splitlines():
        ln = ln.strip()
        if ln and not ln.startswith('#') and '=' in ln:
            k, v = ln.split('=', 1)
            d[k.strip()] = v.strip()
    return d


#  ★★ 2026-08-09 — **저장된 Gemini 결과를 기준선으로 쓰면 «불공정»하다.**
#  그건 12,973자짜리 실제 SYSTEM 프롬프트로 돈 것이고, Solar 에게는 아래 500자짜리
#  최소 프롬프트를 준다. Solar 가 훨씬 쉬운 문제를 푸는 셈이다.
#  ⇒ **같은 프롬프트로 Gemini 도 다시 돌린다.** 저장된 결과는 «참고»로만 같이 찍는다.
GEM_URL = ('https://generativelanguage.googleapis.com/v1beta/models/'
           '{m}:generateContent?key={k}')


def _gem_schema():
    """Gemini 는 대문자 타입을 쓴다. 내용은 _SCHEMA 와 «같다»."""
    def conv(s):
        if s.get('type') == 'object':
            return {'type': 'OBJECT',
                    'properties': {k: conv(v) for k, v in s['properties'].items()},
                    'required': s.get('required', [])}
        if s.get('type') == 'array':
            return {'type': 'ARRAY', 'items': conv(s['items'])}
        out = {'type': 'STRING'}
        if s.get('enum'):
            out['enum'] = s['enum']
        return out
    return conv(_SCHEMA)


def call_gemini(key, model, msg):
    body = json.dumps({
        'systemInstruction': {'parts': [{'text': SYS}]},
        'contents': [{'parts': [{'text': msg}]}],
        'generationConfig': {'responseMimeType': 'application/json',
                             'responseSchema': _gem_schema(),
                             'temperature': 0.0},
    }).encode()
    req = urllib.request.Request(
        GEM_URL.format(m=model, k=key), data=body,
        headers={'Content-Type': 'application/json'})
    r = json.loads(urllib.request.urlopen(req, timeout=60).read())
    txt = r['candidates'][0]['content']['parts'][0]['text']
    um = r.get('usageMetadata') or {}
    u = {'prompt_tokens': um.get('promptTokenCount', 0),
         'completion_tokens': um.get('candidatesTokenCount', 0)}
    t = txt.strip()
    if t.startswith('```'):
        t = t.split('\n', 1)[1].rsplit('```', 1)[0]
    return json.loads(t), u


#  ★★ 2026-08-09 (2차) — **1차 시험은 Solar 에게 불리하게 기울어 있었다.**
#  ① Solar 에겐 `json_object`(형식만 보장)를, Gemini 에겐 네이티브 JSON 모드를 줬다.
#     Upstage 도 `json_schema`(구조까지 강제)를 지원한다 → 같은 급으로 맞춘다.
#  ② 「종류없음」(기권)을 오답으로 셌다. 그러면 «수다스러운 모델»이 유리해진다 —
#     슬롯을 많이 채울수록 「하나라도 맞으면 통과」에 걸릴 확률이 오른다.
#     실제로 출력 토큰이 Gemini 7,478 · solar-pro4 3,286 이었고,
#     기권을 빼고 다시 세면 solar-pro4 가 70/72(97%)로 Gemini 75/79(95%)보다 높았다.
#  ⇒ 기권을 «따로» 세고, 케이스별 결과를 파일로 남긴다.
#  ⚠ 남는 편향 — KIND_DESC 는 «Gemini 를 상대로 다듬어진» 문장이다(§6-2: 정의를 넣어
#    8/14 → 12/14). 이건 이 시험으로 못 없앤다. 결론에 반드시 같이 적는다.
_SCHEMA = {
    'type': 'object',
    'properties': {ax: {'type': 'array', 'items': {
        'type': 'object',
        'properties': {'값': {'type': 'string'}, '근거': {'type': 'string'},
                       '종류': {'type': 'string', 'enum': ['원함', '해봤음', '못함']}},
        'required': ['값', '근거', '종류'],
    }} for ax in AXES},
    'required': AXES,
}


def call(key, model, msg):
    if model.startswith('gemini'):
        return call_gemini(_GKEY[0], model, msg)
    body = json.dumps({
        'model': model,
        'messages': [{'role': 'system', 'content': SYS},
                     {'role': 'user', 'content': msg}],
        'temperature': 0.0,
        'response_format': {'type': 'json_schema', 'json_schema': {
            'name': 'slots', 'strict': True, 'schema': _SCHEMA}},
    }).encode()
    req = urllib.request.Request(
        URL, data=body,
        headers={'Authorization': 'Bearer ' + key,
                 'Content-Type': 'application/json'})
    r = json.loads(urllib.request.urlopen(req, timeout=60).read())
    txt = r['choices'][0]['message']['content']
    u = r.get('usage') or {}
    #  ⚠ JSON 모드여도 ```json 울타리를 씌워 오는 모델이 있다. 벗겨 준다.
    t = txt.strip()
    if t.startswith('```'):
        t = t.split('\n', 1)[1].rsplit('```', 1)[0]
    return json.loads(t), u


def kinds_of(raw):
    """{축: [{값,근거,종류}]} → 나온 종류 집합."""
    out = set()
    for ax in AXES:
        for it in (raw.get(ax) or []):
            if isinstance(it, dict) and it.get('종류') in ('원함', '해봤음', '못함'):
                out.add(it['종류'])
    return out


def score(pairs):
    """[(기대, 나온종류집합)] → (맞음, 종류없음, 채점대상)"""
    ok = none = 0
    for want, got in pairs:
        if not got:
            none += 1
        elif want in got:
            ok += 1
    return ok, none, len(pairs)


def regrade_gemini():
    """저장된 Gemini 원시응답을 «같은 규칙»으로 다시 채점한다."""
    p = HERE / '_kind_capability_result.json'
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding='utf-8'))
    pairs = []
    for c in d.get('케이스', []):
        want = c.get('기대')
        if want not in ('원함', '해봤음', '못함'):
            continue
        pairs.append((want, kinds_of(c.get('스키마_원시응답') or {})))
    return d.get('모델'), score(pairs), pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--models', default='solar-pro3')
    ap.add_argument('--n', type=int, default=0)
    a = ap.parse_args()

    e = env()
    key = e.get('SOLAR_KEY') or e.get('UPSTAGE_API_KEY')
    if not key:
        sys.exit('.env 에 SOLAR_KEY 가 없다')
    _GKEY[0] = e.get('GEMINI_API_KEY') or ''

    cases = [(w, m) for w, m, _ in CASES if w in ('원함', '해봤음', '못함')]
    if a.n:
        cases = cases[:a.n]

    print('=' * 92)
    print(f'  Solar vs Gemini — 「종류」를 가를 수 있나 · 케이스 {len(cases)}개')
    print('  ⚠ 당시 Solar 와 지금 Solar 는 «다른 물건»이다. 이 시험은 «지금»만 말한다.')
    print('=' * 92)

    g = regrade_gemini()
    if g:
        gm, (ok, none, n), _ = g
        print(f'  기준선  {gm:24s} 맞음 {ok:3d}/{n}  ({ok / n * 100:.0f}%) · 종류없음 {none}')

    for model in [m.strip() for m in a.models.split(',') if m.strip()]:
        pairs, fails, tin, tout = [], 0, 0, 0
        t0 = time.time()
        wrong = []
        for i, (want, msg) in enumerate(cases, 1):
            try:
                raw, u = call(key, model, msg)
                tin += u.get('prompt_tokens', 0)
                tout += u.get('completion_tokens', 0)
                got = kinds_of(raw)
            except Exception as ex:                                  # noqa: BLE001
                fails += 1
                got = set()
                if fails <= 2:
                    print(f'    [{i}] 실패: {type(ex).__name__}: {str(ex)[:90]}')
            pairs.append((want, got))
            if got and want not in got:
                wrong.append((want, msg, sorted(got)))
            if i % 25 == 0:
                print(f'    … {i}/{len(cases)}')
        ok, none, n = score(pairs)
        answered = n - none
        #  ★ 기권을 «따로» 센다. 그래야 수다스러운 모델이 유리해지지 않는다.
        print(f'\n  {model:24s} 전체 {ok:3d}/{n} ({ok / n * 100:.0f}%) · '
              f'**답한 것 중 {ok}/{answered} ({ok / max(1, answered) * 100:.0f}%)** · '
              f'기권 {none} · 호출실패 {fails} · {time.time() - t0:.0f}초')
        print(f'    토큰 입력 {tin:,} · 출력 {tout:,}')
        #  ⚠ 기권이 어느 종류에서 났나 — 「못함」에서 기권하면 실사용에서는 «오답과 같다».
        #    종류가 안 담기면 그 값은 검색에서 안 빠지므로 해봤음/원함처럼 취급된다.
        by = {}
        for (want, got) in pairs:
            if not got:
                by[want] = by.get(want, 0) + 1
        if by:
            print(f'    기권 분포 — ' + ' · '.join(f'{k} {v}건' for k, v in sorted(by.items())))
            if by.get('못함'):
                print(f'    🔴 「못함」에서 기권 {by["못함"]}건 — 실사용에서는 «오답과 같다»'
                      f' (종류가 안 담기면 검색에서 안 빠진다)')
        if wrong:
            print(f'    틀린 것 {len(wrong)}건 중 앞 8개:')
            for want, msg, got in wrong[:8]:
                print(f'      기대 {want:4s} → {"·".join(got):12s}  「{msg}」')
        (HERE / f'_solar_cmp_{model.replace(".", "_")}.json').write_text(
            json.dumps({'모델': model, '전체': n, '맞음': ok, '기권': none,
                        '기권분포': by, '호출실패': fails,
                        '토큰': {'in': tin, 'out': tout},
                        '케이스': [{'기대': w, '발화': m, '나온종류': sorted(g)}
                                 for (w, g), (_, m) in zip(pairs, cases)]},
                       ensure_ascii=False, indent=1), encoding='utf-8')


main()
