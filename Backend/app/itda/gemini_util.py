# -*- coding: utf-8 -*-
"""Gemini 호출 공용 — 무료 키 우선 · 분당 한도는 대기 · 유료는 '하루' 소진 때만 (2026-07-24)

사용자 정책
  · 무료 키(GEMINI_API_KEY, GEMINI_API_KEY2)로 계속 돈다.
  · 분당 한도(429 PerMinute)에 걸리면 → retryDelay 만큼 기다렸다 같은 키로 재시도.
    (유료로 넘어가지 않는다 — 분당 한도는 1분 뒤 풀리니까)
  · 하루 한도(429 PerDay)에 걸린 키만 '오늘 죽은 키'로 표시하고 다음 키로.
  · 무료 키가 전부 하루 소진됐을 때 → 그제서야 유료 키(GEMINI_API_KEY3).
  · ITDA_NO_PAID=1 이면 유료를 아예 안 쓴다.

유료/무료 구분은 키 이름으로 한다. 유료 키 이름은 ITDA_PAID_KEY_NAMES 로 바꿀 수 있고
기본값은 'GEMINI_API_KEY3'. itda_core·match 양쪽이 이 한 곳을 쓴다.
"""
import re
import json
import asyncio
import datetime
import urllib.request
import urllib.error


def split_keys(env):
    """ENV → (무료 키 목록, 유료 키 목록). 이름으로 가른다."""
    paid_names = [s.strip() for s in
                  (env.get('ITDA_PAID_KEY_NAMES') or 'GEMINI_API_KEY3').split(',') if s.strip()]
    items = sorted((k, v) for k, v in env.items() if k.startswith('GEMINI_API_KEY') and v)
    free = list(dict.fromkeys(v for k, v in items if k not in paid_names))
    paid = list(dict.fromkeys(v for k, v in items if k in paid_names))
    return (free or [None]), paid


# 오늘 하루 한도가 소진된 키(값). 프로세스가 사는 동안만 기억한다.
_DEAD = set()
_DEAD_DATE = None          # _DEAD 를 기록한 날짜 — 날이 바뀌면(자정 지나 쿼터 리셋) 자동으로 비운다


def _parse_429(body):
    """429 본문에서 (하루한도인가, 재시도 대기초) 를 뽑는다. 못 읽으면 (False, 30)."""
    is_daily, retry = False, 30.0
    try:
        det = (json.loads(body).get('error', {}) or {}).get('details', []) or []
        for d in det:
            t = d.get('@type', '')
            if 'QuotaFailure' in t:
                for v in d.get('violations', []):
                    qid = (str(v.get('quotaId', '')) + str(v.get('quotaMetric', ''))).lower()
                    if 'perday' in qid or 'per_day' in qid:
                        is_daily = True
            if 'RetryInfo' in t:
                m = re.match(r'(\d+)', str(d.get('retryDelay', '')))
                if m:
                    retry = float(m.group(1))
    except Exception:
        pass
    return is_daily, retry


async def call(make_request, env, *, keys_override=None, max_rpm_wait=4):
    """make_request(key) -> bytes (POST 실행) 를 무료→(하루소진 시)유료 순으로 호출.

    반환: 파싱된 json(dict). 분당 한도는 내부에서 기다렸다 재시도한다.
    keys_override 가 있으면 그 키들만 쓴다(테스트/명시 키). 유료 승격 없음.
    """
    if keys_override is not None:
        free, paid = list(keys_override), []
    else:
        free, paid = split_keys(env)
    no_paid = (env.get('ITDA_NO_PAID') or '') not in ('', '0', 'false', 'False')

    global _DEAD_DATE                       # 날짜 바뀌면 하루한도 죽은 키 초기화(자정 쿼터 리셋 반영)
    _today = datetime.date.today()
    if _today != _DEAD_DATE:
        _DEAD.clear()
        _DEAD_DATE = _today

    last = None
    # ── 1) 무료(또는 지정) 키 — 분당 한도는 기다렸다 재시도 ──
    #   에러코드별로 갈라야 유료 폴백이 제대로 산다(코드감사 #2):
    #     하루한도·403(망가진 키) → _DEAD 표시 → 무료가 다 죽으면 유료로.
    #     분당한도 → 기다렸다 재시도, 초과하면 다음 키(죽은 건 아님 → 유료 안 감, 비용 규율).
    #     5xx(일시) → 다른 무료 키 시도.  400·404(요청 문제) → 다른 키로도 같으니 즉시 중단.
    for key in free:
        if key in _DEAD:
            last = 'daily/권한 소진'
            continue
        waits = 0
        while True:
            try:
                return json.loads(await asyncio.to_thread(make_request, key))
            except urllib.error.HTTPError as e:
                body = e.read().decode('utf-8', 'replace')
                if e.code == 429:
                    is_daily, retry = _parse_429(body)
                    if is_daily:
                        _DEAD.add(key); last = 'daily 소진'
                        print('[gemini] 무료 키 하루 소진 → 죽은 키 표시(유료 후보)')
                        break
                    if waits < max_rpm_wait:
                        waits += 1; last = f'분당한도 — {retry:.0f}s 대기'
                        await asyncio.sleep(min(retry + 1, 65)); continue
                    last = '분당한도 초과'; break                       # 다음 키 (죽은 건 아님)
                if e.code == 403:
                    _DEAD.add(key); last = '403(권한/결제)'
                    print('[gemini] 무료 키 403(권한/결제) → 죽은 키 표시')
                    break                                              # 망가진 키 → 유료 후보로
                if e.code in (500, 502, 503):
                    last = f'{e.code}(일시)'; break                     # 다른 무료 키 시도
                raise RuntimeError(f'Gemini {e.code}: {body[:150]}') from None
            except (urllib.error.URLError, TimeoutError, ValueError) as e:
                # 네트워크(타임아웃·연결실패)·JSON 파싱 오류 — HTTPError 밖이라 예전엔 키회전 못 하고
                # 그 턴이 통째 실패했다(코드감사). 이제 일시 오류로 보고 다음 무료 키를 시도한다.
                last = f'네트워크/파싱({type(e).__name__})'; break

    # ── 2) 유료 키 — '무료 키가 전부 하루 소진'됐을 때만 ──
    if paid and not no_paid and keys_override is None and all(k in _DEAD for k in free):
        print('[gemini] 무료 키 전부 하루 소진 → 유료 키로 전환')
        for key in paid:
            try:
                return json.loads(await asyncio.to_thread(make_request, key))
            except urllib.error.HTTPError as e:
                body = e.read().decode('utf-8', 'replace')
                if e.code in (429, 503):
                    _, retry = _parse_429(body)
                    await asyncio.sleep(min(retry + 1, 65))
                    try:
                        return json.loads(await asyncio.to_thread(make_request, key))
                    except urllib.error.HTTPError as e2:
                        body = e2.read().decode('utf-8', 'replace')
                        raise RuntimeError(f'Gemini(유료) {e2.code}: {body[:150]}') from None
                raise RuntimeError(f'Gemini(유료) {e.code}: {body[:150]}') from None

    raise RuntimeError(
        f'Gemini 무료 키 소진 (마지막: {last}). '
        f'분당 한도면 잠시 뒤 다시 시도돼요. 무료 하루 한도가 전부 빠졌으면 유료로 자동 전환됩니다.')
