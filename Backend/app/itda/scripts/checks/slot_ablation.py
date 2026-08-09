# -*- coding: utf-8 -*-
"""어블레이션 — **슬롯이 검색을 «더 낫게» 하는가.** (2026-08-07)

무엇을 정하려는 건가
  잇다는 발화를 7개의 칸(슬롯)으로 바꿔서 검색한다. 그런데 **그게 도움이 되나?**
  슬롯은 발화를 enum 으로 «압축»한다 —
    「엄청나게 큰 데이터를 모으고 저장해서 인프라를 만드는 일」
      → 관심분야=데이터 · 활동유형=만들기 · 다루는대상=컴퓨터·데이터
  정보가 줄어든다. 줄어든 만큼 검색이 나빠질 수도 있다. 아무도 안 재봤다.

세 갈래를 같은 질의로 비교한다
  ⓐ 원문      사용자가 한 말을 «그대로» 검색
  ⓑ 슬롯      LLM 이 뽑은 슬롯을 이어붙여 검색 (_search_query)
  ⓒ LLM질의   LLM 이 직접 써 준 검색어 (turn 의 query)
  ⓑⓒ 는 turn() 한 번으로 «둘 다» 얻는다 — 호출이 두 배가 되지 않는다.

정답표
  `build_calibration_set.py` 가 만든 것을 쓴다. NCS 직무정의를 주고 「그 직업을 원하는
  사람이 할 법한 말」을 짓게 했으므로 **정답이 원본 직업으로 자동 확정**된다.
  ⚠ 사람 라벨이 아니다. 대신 「어느 직업에서 나온 문장인가」라는 «생성 규칙»이 정답이다.
  ⚠ 직업명을 그대로 쓴 문장은 생성기가 이미 버렸다(이름 찾기가 되므로).

⚠ 이 시험의 한계 — 먼저 적는다
  · 질의가 **한 문장**이다. 슬롯의 진짜 값어치는 «여러 턴에 흩어진 정보를 모으는 것»인데
    한 문장에서는 모을 게 없다. 즉 **슬롯에 불리한 시험**이다.
    그래도 재는 이유: 「압축해서 잃는 게 있나」는 이 시험으로 답할 수 있다.
  · 합성 질의다. 실사용 발화보다 깔끔하다.

비용
  turn() 100회 ≈ 70원 · 임베딩/검색 300회. 15~20분.

쓰는 법 (Backend/ 에서)
  python app/itda/scripts/checks/slot_ablation.py [--n 100]
"""
import argparse
import asyncio
import io
import json
import os
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from app.itda.db import async_session                              # noqa: E402
from app.itda import match                                         # noqa: E402
from app.itda.itda_core import ItdaEngine, verify_slots            # noqa: E402

SET = Path(__file__).resolve().parents[1] / 'calibration_set.json'
TOPK = 20


def rank_of(rows, code):
    """정답 직업이 몇 등인가. 없으면 None."""
    for i, r in enumerate(rows, 1):
        if str(r.get('job_code')) == str(code):
            return i
    return None


def score(ranks, n):
    """Recall@k 와 MRR. ranks 는 None 을 포함할 수 있다."""
    out = {}
    for k in (1, 3, 5, 10, 20):
        out[f'@{k}'] = sum(1 for r in ranks if r and r <= k)
    out['MRR'] = sum(1 / r for r in ranks if r) / max(1, n)
    out['못찾음'] = sum(1 for r in ranks if not r)
    return out


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=100)
    a = ap.parse_args()

    data = json.loads(SET.read_text(encoding='utf-8'))
    items = data.get('items') if isinstance(data, dict) else data
    items = items[:a.n]
    print('=' * 92)
    print(f'  슬롯 어블레이션 — 질의 {len(items)}개 · top{TOPK} 안에서 정답 순위를 본다')
    print(f'  ⓐ 원문   ⓑ 슬롯 조립   ⓒ LLM 이 쓴 검색어')
    print('=' * 92)

    eng = ItdaEngine()
    ra, rb, rc = [], [], []
    #  ⚠ ⓒ 는 «LLM 이 검색어를 만든 경우»에만 의미가 있다. 1턴차엔 모델이 SEARCH 가 아니라
    #    ASK 를 내는 일이 많고, 그러면 query 가 빈다. 그건 «질의가 나쁜 것»이 아니라
    #    «아직 물어보겠다»는 뜻이다. 빈 것을 실패로 세면 ⓒ 를 부당하게 깎는다.
    n_llm_q = 0
    async with async_session() as db:
        for i, it in enumerate(items, 1):
            #  ⚠ 키 이름 — build_calibration_set 의 출력은 job_code / job_name 이다.
            #    처음에 code / name 으로 읽었다가 «정답=None» 이 되어 전부 못찾음으로
            #    나왔다. 3개로 스모크 테스트해서 잡았다(100개 돌렸으면 70원을 버렸다).
            q = it.get('question') or it.get('q')
            code = it.get('job_code')
            name = it.get('job_name') or ''
            #  ⓐ 원문 그대로
            try:
                rows_a = await match.match_jobs(db, q, top_k=TOPK)
            except Exception as e:                                  # noqa: BLE001
                print(f'  [{i}] 검색 실패(원문): {type(e).__name__}'); rows_a = []
            #  ⓑⓒ — turn() 한 번으로 슬롯과 LLM 질의를 «둘 다» 받는다
            slots, llm_q = {}, ''
            try:
                t = await eng.turn({}, q) or {}
                #  ⚠ turn_schema(2641행)의 키는 'profile' 이다. 'slots' 가 아니다.
                raw = t.get('profile') or {}
                slots, _ = verify_slots(raw, q)
                llm_q = (t.get('query') or '').strip()
            except Exception as e:                                  # noqa: BLE001
                print(f'  [{i}] turn 실패: {type(e).__name__}: {str(e)[:60]}')
            slot_q = eng._search_query(slots, '')
            rows_b = []
            if slot_q:
                try:
                    rows_b = await match.match_jobs(db, slot_q, top_k=TOPK)
                except Exception:                                   # noqa: BLE001
                    pass
            rows_c = []
            if llm_q:
                n_llm_q += 1
                try:
                    rows_c = await match.match_jobs(db, llm_q, top_k=TOPK)
                except Exception:                                   # noqa: BLE001
                    pass

            pa, pb, pc = rank_of(rows_a, code), rank_of(rows_b, code), rank_of(rows_c, code)
            ra.append(pa); rb.append(pb); rc.append(pc)
            if i <= 6 or i % 20 == 0:
                print(f'  [{i:>3}] {str(q)[:44]:<46}')
                print(f'        정답={name or code}  ⓐ원문={pa or "—"}  '
                      f'ⓑ슬롯={pb or "—"}  ⓒLLM={pc or "—"}')
                if i <= 6:
                    print(f'        슬롯질의: {slot_q[:70]!r}')
                    print(f'        LLM질의 : {llm_q[:70]!r}')

    n = len(items)
    print('\n' + '=' * 92)
    print(f'{"":10} {"@1":>6}{"@3":>6}{"@5":>6}{"@10":>7}{"@20":>7}{"MRR":>9}{"못찾음":>8}')
    print('-' * 92)
    for label, rr, denom in (('ⓐ 원문', ra, n), ('ⓑ 슬롯', rb, n),
                             ('ⓒ LLM질의', rc, max(1, n_llm_q))):
        s = score(rr, denom)
        print(f'{label:<10} {s["@1"]:>6}{s["@3"]:>6}{s["@5"]:>6}{s["@10"]:>7}'
              f'{s["@20"]:>7}{s["MRR"]:>9.3f}{s["못찾음"]:>8}')
    print('=' * 92)
    print(f'  ⚠ ⓒ 는 LLM 이 «검색어를 만든» {n_llm_q}/{n} 건만 분모로 썼다.')
    print(f'    나머지 {n - n_llm_q} 건은 모델이 SEARCH 가 아니라 ASK 를 냈다 —')
    print(f'    질의가 나쁜 게 아니라 «더 물어보겠다»는 뜻이라 실패로 안 센다.')
    #  ⓑ 가 ⓐ 보다 «나쁜» 건수 — 압축으로 잃은 사례
    lost = sum(1 for x, y in zip(ra, rb) if x and (not y or y > x))
    gain = sum(1 for x, y in zip(ra, rb) if y and (not x or y < x))
    print(f'  ⓑ슬롯이 ⓐ원문보다 «나쁨» {lost}건 · «나음» {gain}건')
    u = eng.total_usage
    print(f'  LLM {u.get("calls", 0)}회 · 입력 {u.get("in", 0):,} · 출력 {u.get("out", 0):,}')


asyncio.run(main())
