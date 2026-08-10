# -*- coding: utf-8 -*-
r"""나누다 API 를 «실제로 불러서» 살아 있는지 본다 — 2026-08-09.

왜 만들었나
  「나누다 쪽 오류 있어?」에 답하려면 코드를 읽는 걸로는 부족하다. import 가 되는
  것과 요청이 200 으로 돌아오는 건 다른 문제다(실제로 import 는 다 됐는데
  nanuda/main.py 는 죽은 파일이었다).

무엇을 «안» 하나
  쓰기(POST) 는 기본으로 안 부른다. 편지·가족방·초대코드를 만들면 운영 데이터가
  더러워지고, 주간분석·시설추천은 LLM/Pinecone 비용이 붙는다.
  --write 를 줘야 그것들도 부른다.

쓰는 법
  python -m tools.nanuda_probe            # 읽기만 (0원)
  python -m tools.nanuda_probe --write    # 쓰기까지 (비용 발생 — 먼저 보고할 것)
"""
import argparse
import io
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = 'http://127.0.0.1:8000'
ENV = Path(__file__).resolve().parent.parent / 'app' / '.env'
USER_ID = 6          # care_groups 2·3·4 의 소유자. 그룹 2 에 편지 59통 + 주간분석 1건
GROUP = 2


def env():
    d = {}
    for ln in ENV.read_text(encoding='utf-8').splitlines():
        ln = ln.strip()
        if ln and not ln.startswith('#') and '=' in ln:
            k, v = ln.split('=', 1)
            d[k.strip()] = v.strip()
    return d


def token(secret, uid=USER_ID):
    now = datetime.now(timezone.utc)
    #  app/user/security.py 의 create_access_token 과 «같은» 모양이어야 한다.
    #  sub 가 str 이 아니면 PyJWT 가 인코딩에서 거부한다.
    return jwt.encode({'sub': str(uid), 'is_admin': False,
                       'iat': now, 'exp': now + timedelta(minutes=30)},
                      secret, algorithm='HS256')


def call(method, path, hdr, **kw):
    t0 = time.time()
    try:
        r = requests.request(method, BASE + path, headers=hdr, timeout=120, **kw)
    except Exception as e:
        return None, f'{type(e).__name__}: {e}', time.time() - t0
    try:
        body = r.json()
    except Exception:
        body = r.text[:300]
    return r.status_code, body, time.time() - t0


def show(method, path, code, body, sec, note=''):
    mark = {2: '✅', 4: '⚠', 5: '🔴'}.get((code or 0) // 100, '🔴')
    head = f'{mark} {code or "연결실패"} {method:5s} {path}'
    print(f'{head:<64s} {sec:5.2f}s {note}')
    if code is None or code >= 400:
        print(f'      └ {json.dumps(body, ensure_ascii=False)[:400] if not isinstance(body, str) else body[:400]}')
    elif isinstance(body, list):
        print(f'      └ {len(body)}건' + (f' · 첫 항목 키 {list(body[0])[:8]}' if body and isinstance(body[0], dict) else ''))
    elif isinstance(body, dict):
        print(f'      └ 키 {list(body)[:10]}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()

    e = env()
    if not e.get('JWT_SECRET_KEY'):
        sys.exit('JWT_SECRET_KEY 가 .env 에 없다')
    hdr = {'Authorization': 'Bearer ' + token(e['JWT_SECRET_KEY'])}

    print(f'\n== 나누다 실제 호출 (user_id={USER_ID}, care_group={GROUP}) ==\n')

    print('── 인증 없이 부르면 막히는가 ──')
    show('GET', '/care-groups/my', *call('GET', '/care-groups/my', {}), note='← 401 이어야 정상')

    print('\n── 읽기 (0원) ──')
    #  ⚠ facility_type 은 «영문 enum» 이다(DB 실측: MENTAL_HEALTH / YOUTH_SAFETY /
    #    LONG_TERM_CARE / FAMILY_CENTER). 한글로 주면 400 「허용되지 않은 기관 유형」.
    #  ⚠ letter 1 은 care_group 1 소속이라 user 6 으로는 403 이 «맞다» — 그 확인도 겸한다.
    for m, p, kw, note in [
        ('GET', '/care-groups/my', {'params': {'user_id': USER_ID}}, ''),
        ('GET', f'/care-groups/{GROUP}/members', {'params': {'user_id': USER_ID}}, ''),
        ('GET', '/family-letters', {'params': {'user_id': USER_ID, 'care_group_id': GROUP}}, ''),
        ('GET', '/family-letters/108', {'params': {'user_id': USER_ID}}, '← 내 그룹 편지'),
        ('GET', '/family-letters/1', {'params': {'user_id': USER_ID}}, '← 남의 그룹, 403 이어야 정상'),
        ('GET', '/support-facilities', {'params': {'facility_type': 'FAMILY_CENTER'}}, ''),
        ('GET', '/support-facilities', {'params': {'facility_type': 'LONG_TERM_CARE'}}, ''),
        ('GET', '/support-facilities/46/map', {}, '← 카카오 지도 API'),
        ('GET', '/support-facilities/route', {'params': {
            'origin_latitude': 37.5665, 'origin_longitude': 126.9780,
            'destination_latitude': 37.5512, 'destination_longitude': 126.9882}}, '← 카카오 길찾기'),
    ]:
        show(m, p, *call(m, p, hdr, **kw), note=note)

    if not a.write:
        print('\n(쓰기·LLM 경로는 --write 를 줘야 부른다)')
        return

    print('\n── 쓰기 / LLM (비용 발생) ──')
    for m, p, kw in [
        ('POST', f'/weekly-care-analyses/{GROUP}', {'params': {'user_id': USER_ID}}),
        ('POST', f'/weekly-care-analyses/{GROUP}/recommend', {'params': {'user_id': USER_ID}}),
    ]:
        show(m, p, *call(m, p, hdr, **kw))


if __name__ == '__main__':
    main()
