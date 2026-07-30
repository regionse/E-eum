# -*- coding: utf-8 -*-
"""Solar(Upstage) 어댑터 — Gemini와 같은 (prompt, schema, temp) → dict 계약 (2026-07-24)

왜: 착지 판단을 코드로 옮긴 뒤 모델의 일이 '한국어 추출 + 말투 + enum 선택'으로 줄어,
    한국어 특화 + 저렴한 Solar Pro 3 가 후보가 됨. 골든셋 A/B로 3.6-flash 와 붙여본다.
    임베딩은 그대로 Gemini(match.py) — 여기선 '대화 모델'만 교체한다.

Upstage 는 OpenAI 호환. 구조화 출력은 response_format=json_schema(strict).
  · 키   : .env 의 SOLAR* / UPSTAGE* (이름만 본다. 값은 안 찍는다)
  · 모델 : ITDA_SOLAR_MODEL (기본 'solar-pro2'). 정확한 ID는 Upstage 콘솔 확인.
"""
import re
import json
import asyncio
import urllib.request
import urllib.error

ENDPOINT = 'https://api.upstage.ai/v1/chat/completions'


def _key(env):
    for k, v in sorted(env.items()):
        if v and re.search(r'SOLAR|UPSTAGE', k, re.I):
            return v
    return None


def _to_json_schema(gs):
    """Gemini 스키마(대문자 type: OBJECT/STRING) → OpenAI JSON Schema(소문자). 재귀 변환."""
    if not isinstance(gs, dict):
        return gs
    out = {}
    for k, v in gs.items():
        if k == 'type' and isinstance(v, str):
            out['type'] = v.lower()
        elif k == 'properties' and isinstance(v, dict):
            out['properties'] = {pk: _to_json_schema(pv) for pk, pv in v.items()}
            # OpenAI strict 모드는 additionalProperties:false + 모든 키 required 를 요구
            out['additionalProperties'] = False
            out.setdefault('required', list(v.keys()))
        elif k == 'items':
            out['items'] = _to_json_schema(v)
        else:
            out[k] = v
    return out


async def call(prompt, schema, temp, env, model=None):
    """Solar 로 구조화 JSON 을 받아 (파싱된 dict, usage) 반환. usage 는 Gemini 형식으로 맞춤."""
    key = _key(env)
    if not key:
        raise RuntimeError('Solar 키 없음 (.env 에 SOLAR* 또는 UPSTAGE* 추가)')
    model = model or env.get('ITDA_SOLAR_MODEL') or 'solar-pro2'
    js = _to_json_schema(schema)
    body = json.dumps({
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': temp,
        'response_format': {'type': 'json_schema',
                            'json_schema': {'name': 'itda', 'schema': js, 'strict': True}},
    }).encode()

    def _post():
        req = urllib.request.Request(ENDPOINT, data=body, headers={
            'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'})
        return urllib.request.urlopen(req, timeout=90).read()

    try:
        j = json.loads(await asyncio.to_thread(_post))
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', 'replace')[:200]
        raise RuntimeError(f'Solar {e.code}: {detail}') from None
    #  응답 형태 검증 — 빈 choices·안전필터 차단·토큰절단 시 무방비 인덱싱이면 KeyError/IndexError(코드감사)
    choices = j.get('choices') or []
    content = (choices[0].get('message') or {}).get('content') if choices else None
    if not content:
        raise RuntimeError(f'Solar 빈/이상 응답(안전필터·절단?): {str(j)[:150]}')
    u = j.get('usage', {}) or {}
    usage = {'in': u.get('prompt_tokens', 0), 'out': u.get('completion_tokens', 0),
             'think': 0, 'cached': 0}
    return json.loads(content), usage
