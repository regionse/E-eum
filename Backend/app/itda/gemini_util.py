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
import random
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


def _jitter(sec):
    """대기에 지터를 섞는다 — 절반은 고정, 절반은 무작위(equal jitter).

    근거(원문 확인) — Gemini API 공식 troubleshooting 문서가 명시한다:
      "Use exponential backoff … then increase the delay exponentially (2s, 4s, 8s)"
      "Add jitter: Add random 'jitter' to the delay to help prevent all clients from
       retrying at the exact same time."
    우리는 지금 서버가 준 retryDelay 를 «그대로» 쓰고 있었다. 사용자가 여럿이면
    한도에 걸린 요청들이 정확히 같은 시각에 되돌아온다(thundering herd).
    """
    return sec * 0.5 + random.random() * sec * 0.5


async def call(make_request, env, *, key=None, max_retry=2, deadline=None,
               call_timeout=0.0):
    """make_request(key) -> bytes (POST 실행). 반환: 파싱된 json(dict).

    429(한도)·5xx(일시)·네트워크/파싱 오류는 최대 max_retry 회 재시도한다.
    400·404(요청이 잘못됨)·403(권한/결제)은 재시도해도 같으니 즉시 올린다.

    deadline
      이 호출 «전체»(재시도·대기 포함)에 쓸 수 있는 초. None 이면 무제한.

      ★★ 2026-08-06 — **왜 개별 타임아웃이 아니라 전체 예산인가.**
        예전엔 urlopen(timeout=90) 하나뿐이었다. 그런데 재시도가 곱해진다:
            90 + 대기65 + 90 + 대기65 + 90 ≈ **400초**
        한 턴이 6분 넘게 매달릴 수 있었고, HTTP 층에도 타임아웃이 없어 아무도 안 끊었다.

        근거(원문 확인):
          · Google SRE, Addressing Cascading Failures —
            "Having deadlines several orders of magnitude longer than the mean request
             latency is usually bad."   우리 실측 평균은 2.6초(골든셋 110초/42콜)다.
             90초는 그 **35배**였다.
          · 같은 장 — 층마다 재시도하면 "a single user action may create 64 attempts (4³)"
          · gRPC 공식 블로그 — **"Always set a deadline."** 없으면 "resources will be held
            for all in-flight requests … could crash the entire process in the worst case."
          · Google SRE, Handling Overload — "If a request has already failed three times,
            we let the failure bubble up to the caller." (우리 max_retry=2 = 3회 시도. 맞다)

      ⚠ **기본값이 None 인 이유** — 이 함수는 배치 스크립트도 쓴다
        (build_course_coverage 411콜 · embed_jobs · build_calibration_set).
        그쪽은 «오래 걸려도 되는» 작업이라 예산을 걸면 안 된다.
        대화 경로(itda_core.gemini)만 명시적으로 준다.

      ⚠ **남은 한계를 정직하게 적는다** — 예산은 «대기 전»에만 본다. 이미 시작한 요청은
        못 끊는다(make_request 가 타임아웃을 갖고 있어서). 그래서 실제 상한은
        per-call timeout × 시도횟수 + 대기 이고, 25초 기준 최악 ≈ 79초다.
        400초 → 79초는 5배 개선이지만 0 은 아니다. 완전히 끊으려면 make_request 에
        남은 예산을 넘겨야 하는데 호출부 5곳을 다 고쳐야 해서 발표 뒤로 미룬다.
    """
    k = key or get_key(env)
    if not k:
        raise RuntimeError(f'{KEY_NAME} 없음 — etc/.env 확인')

    _loop = asyncio.get_running_loop()
    _t0 = _loop.time()

    def _left():
        """남은 예산(초). deadline 이 없으면 None."""
        return None if deadline is None else deadline - (_loop.time() - _t0)

    async def _hold(wait, why, tries):
        """대기해도 예산 안에 드나 — 아니면 **기다리지 않고** 여기서 끝낸다.

        ★ 판정은 `남은 > 대기` 가 아니라 `남은 > 대기 + 한 번 더 걸릴 시간` 이다.
          앞엣것으로 했다가 실측에서 이렇게 나왔다(2026-08-06):
              예산 45s · 대기 36s  →  36초를 «기다린 뒤» 예산 초과로 실패
          기다려 봐야 그 뒤에 요청을 끝낼 시간이 없다. 사용자는 36초를 헛기다린다.
          ⇒ call_timeout(한 번의 요청 상한)을 같이 받아서 **미리** 포기한다.
        """
        left = _left()
        need = wait + call_timeout
        if left is not None and left <= need:
            raise RuntimeError(
                f'Gemini 예산 초과 — {deadline:.0f}s 예산으로는 못 끝냄 ({why}). '
                f'남은 {left:.0f}s ≤ 대기 {wait:.0f}s + 요청 {call_timeout:.0f}s') from None
        print(f'[gemini] {why} — {wait:.1f}s 후 재시도 ({tries}/{max_retry})')
        await asyncio.sleep(wait)

    tries = 0
    while True:
        try:
            return json.loads(await asyncio.to_thread(make_request, k))
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', 'replace')
            transient = e.code == 429 or e.code in (500, 502, 503)
            if not transient or tries >= max_retry:
                raise RuntimeError(f'Gemini {e.code}: {body[:150]}') from None
            #  429 는 서버가 준 retryDelay 를 존중한다. 5xx 는 지수 백오프(2·4·8초).
            wait = _retry_after(body) if e.code == 429 else 2.0 * (2 ** tries)
            wait = _jitter(min(wait + 1, 65))
            tries += 1
            await _hold(wait, f'HTTP {e.code}', tries)
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            # 네트워크(타임아웃·연결실패)·JSON 파싱 오류 — 일시 오류로 보고 재시도.
            if tries >= max_retry:
                raise RuntimeError(f'Gemini 호출 실패 — {type(e).__name__}: {str(e)[:110]}') from None
            wait = _jitter(2.0 * (2 ** tries))
            tries += 1
            await _hold(wait, type(e).__name__, tries)
