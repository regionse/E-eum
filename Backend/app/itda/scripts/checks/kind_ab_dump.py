# -*- coding: utf-8 -*-
"""「종류」 필드 A/B — 한 턴마다 **전부** 찍는다 (2026-08-08).

무엇을 보나
  같은 대화를 두 조건으로 돌리고, 턴마다 아래를 나란히 남긴다.
    · 사용자 발화
    · 스키마 원시응답 (값·근거·종류)      ← 「받아들이는 과정」
    · verify 뒤 남은 슬롯 · 출처 · 종류
    · can_land 무게 계산을 «풀어서»       ← 왜 착지했나/못했나
    · 행동(ask/card) · 봇의 대답 · 그중 질문 문장
    · 카드가 나왔으면 직업명

  A 기준선  종류 필드 없음 + git HEAD 의 프롬프트(내 변경 «전»)
  B 지금    종류 필드 있음 + 현재 프롬프트

왜 git HEAD 를 쓰나
  prompts.py 는 수정했지만 커밋은 안 했다. 따라서 HEAD 가 곧 «변경 전»이다.
  손으로 잘라내면 잘못 자를 수 있어, 원본을 그대로 읽어 온다.

쓰는 법
  python -m app.itda.scripts.checks.kind_ab_dump
  python -m app.itda.scripts.checks.kind_ab_dump --flow 7
"""
import asyncio
import io
import json
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from app.itda import itda_core as C                # noqa: E402
from app.itda.db import async_session              # noqa: E402

REPO = Path(r'C:\e-um-1\E-eum-team')
OUT = Path(__file__).with_name('_kind_ab_dump.json')

FLOWS = {
    1: ('① 돌봄만 말함 — 핵심 케이스', [
        '할머니 돌보느라 아무것도 못 해봤어요',
        '벌써 3년째예요',
        '그래서 뭘 해야 될지 모르겠어요',
    ]),
    7: ('⑦ 점진적으로 정보 제공 — land_speed 에서 퇴행한 흐름', [
        '집에서 할머니 챙기고 있어요',
        '약 챙겨드리고 병원도 같이 가요',
        '그런 건 이제 익숙해졌어요',
        '이런 걸로 뭐 할 수 있는 게 있을까요',
    ]),
    8: ('⑧ 한 문장 지목 — 대조군(변하면 안 된다)', [
        '제빵사가 되고 싶어요',
        '빵 만드는 게 재밌더라고요',
    ]),
}


def baseline_system():
    """git HEAD 의 prompts.py 에서 SYSTEM 만 꺼낸다 — 내 변경 «전» 원본."""
    src = subprocess.run(
        ['git', 'show', 'HEAD:Backend/app/itda/prompts.py'],
        cwd=str(REPO), capture_output=True, text=True, encoding='utf-8').stdout
    ns = {}
    exec(compile(src, '<prompts@HEAD>', 'exec'), ns)     # noqa: S102
    return ns['SYSTEM']


def schema_without_kind():
    """선호 3축에서 「종류」를 뺀 스키마 — 기준선 재현."""
    s = json.loads(json.dumps(C.PROFILE_SCHEMA))
    for k in C.ASK_ORDER:
        items = s['properties'][k].get('items') or s['properties'][k]
        items.get('properties', {}).pop('종류', None)
        items['required'] = [x for x in items.get('required', []) if x != '종류']
    return s


def weight_detail(p):
    """can_land 무게를 «풀어서» 문자열로 — 왜 착지했나/못했나."""
    axes = [k for k in C.ASK_ORDER if p.get(k)]
    src = p.get('_slot_src') or {}
    parts, tot = [], 0.0
    for k in axes:
        base = C.LAND_W_CODE if src.get(k) == 'code' else C.LAND_W_USER
        #  ★ 2026-08-10 — _slot_kind 는 «값 단위»({슬롯:{값:종류}})다. kind.get(k) 는
        #    안쪽 dict 를 돌려줘서 KIND_W.get(dict) 가 unhashable TypeError 로 죽었다 —
        #    B런 첫 「못함」 턴(흐름① 1턴)에서 항상. 축 대표는 엔진과 같은 axis_kind 로 잰다.
        ak = C.axis_kind(p, k)
        kw = C.KIND_W.get(ak, 1.0)
        tot += base * kw
        parts.append(f"{k}({src.get(k) or 'user'}"
                     f"{'/' + ak if ak else ''}) {base}×{kw}")
    need = (C.LAND_NEED_LATE if int(p.get('_turns') or 0) >= C.LAND_RELAX_AFTER
            else C.LAND_NEED)
    return ' + '.join(parts) + f' = {tot:.2f}  (문턱 {need})', tot, need


async def run(label, flow, use_kind):
    #  ★★ 캐시를 반드시 비운다. _TURN_CACHE 는 **프로세스 전역**이라 세션 구분이 없다.
    #    A 를 먼저 돌리면 B 가 같은 발화에서 «A 의 응답»을 그대로 받아온다.
    #    실제로 그 함정에 빠져 A/B 가 완전히 동일하게 나왔다(2026-08-08).
    C._TURN_CACHE.clear()
    orig_schema, orig_system = C.PROFILE_SCHEMA, C.SYSTEM
    orig_verify, seen = C.verify_slots, {}

    def spy(raw, user_msg, kinds_out=None):
        seen['raw'] = raw
        return orig_verify(raw, user_msg, kinds_out)

    if not use_kind:
        C.PROFILE_SCHEMA = schema_without_kind()
        C.SYSTEM = baseline_system()
    C.verify_slots = spy

    out = []
    try:
        eng = C.ItdaEngine()
        profile = {}
        async with async_session() as db:
            for i, msg in enumerate(flow, 1):
                seen.clear()
                r = await eng.step(db, profile, msg)
                profile = r.get('profile') or {}
                det, tot, need = weight_detail(profile)
                reply = r.get('reply') or ''
                card = ((r.get('card') or {}).get('job') or {}).get('name')
                out.append({
                    '턴': i, '발화': msg,
                    '스키마_원시응답': seen.get('raw') or {},
                    '슬롯': {k: profile[k] for k in
                             ('관심분야', '활동유형', '다루는대상', '세부관심',
                              '강점성향', '제약', '대상세부') if profile.get(k)},
                    '출처': profile.get('_slot_src') or {},
                    '종류': profile.get('_slot_kind') or {},
                    '무게계산': det, '무게': round(tot, 2), '문턱': need,
                    '착지가능': C.can_land(profile),
                    '행동': r.get('kind'),
                    '대답': reply,
                    '질문문장': [s.strip() + '?' for s in reply.split('?')[:-1] if s.strip()],
                    '카드': card,
                })
    finally:
        C.PROFILE_SCHEMA, C.SYSTEM, C.verify_slots = orig_schema, orig_system, orig_verify
    return out


def show(title, A, B):
    print('\n' + '=' * 100)
    print(f'  {title}')
    print('=' * 100)
    for a, b in zip(A, B):
        print(f"\n🧑 [{a['턴']}턴] {a['발화']}")
        for tag, x in (('A 기준선', a), ('B 종류적용', b)):
            print(f'\n  ── {tag} ' + '─' * (86 - len(tag)))
            raw = x['스키마_원시응답'] or {}
            if raw:
                for k, v in raw.items():
                    for it in (v if isinstance(v, list) else [v]):
                        if isinstance(it, dict) and it.get('값'):
                            kd = f" · 종류={it['종류']}" if it.get('종류') else ''
                            print(f"     받음   {k}={it['값']}  근거「{it.get('근거','')[:26]}」{kd}")
            else:
                print('     받음   (없음)')
            print(f"     슬롯   {json.dumps(x['슬롯'], ensure_ascii=False)}")
            print(f"     무게   {x['무게계산']}  →  착지 {'✅' if x['착지가능'] else '✗'}")
            print(f"     행동   {x['행동']}" + (f"   🃏 {x['카드']}" if x['카드'] else ''))
            print(f"     대답   {x['대답'][:150]}")


async def main():
    only = None
    for i, a in enumerate(sys.argv):
        if a == '--flow' and i + 1 < len(sys.argv):
            only = int(sys.argv[i + 1])
    flows = {k: v for k, v in FLOWS.items() if only is None or k == only}
    n = sum(len(f[1]) for f in flows.values()) * 2
    print(f'\n흐름 {len(flows)}개 · 턴 합계 {n//2} · 두 조건 → LLM 최소 {n}콜\n')

    dump = {}
    for key, (title, flow) in flows.items():
        A = await run('A', flow, use_kind=False)
        B = await run('B', flow, use_kind=True)
        show(title, A, B)
        dump[title] = {'A_기준선': A, 'B_종류적용': B}
    OUT.write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n\n▸ 전체 기록 저장: {OUT}')


asyncio.run(main())
