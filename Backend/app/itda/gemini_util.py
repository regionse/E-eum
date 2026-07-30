# -*- coding: utf-8 -*-
"""Gemini 호출 공용 — 유료 키 1개 · 일시 오류만 재시도 (2026-07-30 슬림화 2차)

키 정책 (확정)
  · 유료 키 **하나**(`GEMINI_API_KEY`)만 쓴다. 키 회전·무료/유료 승격은 하지 않는다.
  · 유료 티어는 분당 한도가 넉넉해 429 가 드물지만, 몰리면 나올 수 있다.
    그때 그냥 실패시키면 데모 중 대화가 툭 끊기므로 짧게 한 번 기다렸다 재시도한다.
  · 네트워크 타임아웃·5xx 도 같은 이유로 한 번 흡수한다.

지운 것 (2026-07-30)
  · 무료/유료 키 분리·유료 승격, ITDA_NO_PAID·ITDA_PAID_KEY_NAMES  (키 1개라 죽은 로직)
  · 하루한도 소진 키 표시(_DEAD)와 자정 리셋                        (키 회전 전제 로직)
  · 여러 키 순회                                                     (유료키 1개 확정)
  되살릴 일이 생기면 git 이력(c83949e 이전)에 남아 있다.

itda_core(대화)·match(임베딩) 양쪽이 이 한 곳을 쓴다.
"""
import re
import json
import asyncio
import urllib.request
import urllib.error

KEY_NAME = 'GEMINI_API_KEY'      # 유료 키. 이름을 바꿀 일이 생기면 여기만 고친다.


def get_key(env):
    """유료 Gemini 키. 없으면 None (호출부가 상태표시·에러로 쓴다)."""
    return env.get(KEY_NAME) or None


def _retry_after(body):
    """429 본문의 retryDelay(초). 못 읽으면 20초."""
    try:
        for d in (json.loads(body).get('error', {}) or {}).get('details', []) or []:
            if 'RetryInfo' in d.get('@type', ''):
                m = re.match(r'(\d+)', str(d.get('retryDelay', '')))
                if m:
                    return float(m.group(1))
    except Exception:
        pass
    return 20.0


async def call(make_request, env, *, key=None, max_retry=2):
    """make_request(key) -> bytes (POST 실행). 반환: 파싱된 json(dict).

    429(한도)·5xx(일시)·네트워크/파싱 오류는 최대 max_retry 회 재시도한다.
    400·404(요청이 잘못됨)·403(권한/결제)은 재시도해도 같으니 즉시 올린다.
    """
    k = key or get_key(env)
    if not k:
        raise RuntimeError(f'{KEY_NAME} 없음 — etc/.env 확인')

    tries = 0
    while True:
        try:
            return json.loads(await asyncio.to_thread(make_request, k))
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', 'replace')
            transient = e.code == 429 or e.code in (500, 502, 503)
            if not transient or tries >= max_retry:
                raise RuntimeError(f'Gemini {e.code}: {body[:150]}') from None
            wait = _retry_after(body) if e.code == 429 else 2.0
            tries += 1
            print(f'[gemini] {e.code} — {wait:.0f}s 후 재시도 ({tries}/{max_retry})')
            await asyncio.sleep(min(wait + 1, 65))
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            # 네트워크(타임아웃·연결실패)·JSON 파싱 오류 — 일시 오류로 보고 재시도.
            if tries >= max_retry:
                raise RuntimeError(f'Gemini 호출 실패 — {type(e).__name__}: {str(e)[:110]}') from None
            tries += 1
            print(f'[gemini] {type(e).__name__} — 2s 후 재시도 ({tries}/{max_retry})')
            await asyncio.sleep(2.0)
