# -*- coding: utf-8 -*-
"""잇다 공용 .env 로더 (2026-07-30 신설 — 세 곳에 흩어져 있던 read_env 통합)

왜 만들었나
  itda_core.py · match.py · db.py 가 각자 `read_env()` 를 갖고 있었고, **경로 목록이 서로 달랐다**.
  match.py 만 `'../../etc/.env'` 가 빠져 있어서, 실행 위치(cwd)에 따라
  DB 는 붙는데 PINECONE_API_KEY 만 None 이 되는 조합이 가능했다(그러면 첫 검색에서 죽는다).
  셋 다 `C:\\e-um-1\\e-um\\etc\\.env` 절대경로를 마지막에 박아 두고 있었는데, 그건 이 노트북에서만 맞다.

어떻게 고쳤나
  cwd 가 아니라 **이 파일 위치(__file__)에서 위로 올라가며** `etc/.env` 를 찾는다.
  → 어디서 실행해도(uvicorn·스크립트·테스트) 같은 파일을 읽고, 다른 사람 PC 에서도 동작한다.
  cwd 기준 후보와 ITDA_ENV_FILE 환경변수도 함께 지원한다(배포 시 명시 지정용).

주의: 값은 절대 로그로 찍지 않는다(키가 섞여 있다).
"""
import os
from pathlib import Path


def _candidates():
    """읽어볼 .env 경로들 — 앞쪽이 우선(먼저 채운 값이 이긴다)."""
    out = []
    explicit = os.environ.get('ITDA_ENV_FILE')
    if explicit:
        out.append(Path(explicit))
    # 이 파일: <repo>/backend/app/itda/env.py → 위로 올라가며 etc/.env 를 찾는다.
    here = Path(__file__).resolve()
    for parent in here.parents:
        out.append(parent / 'etc' / '.env')
        out.append(parent / '.env')
    # cwd 기준(예전 동작 호환)
    for rel in ('.env', 'etc/.env', '../etc/.env', '../../etc/.env'):
        out.append(Path(rel))
    return out


def read_env():
    """.env 들을 훑어 dict 로. 같은 키는 **먼저 찾은 파일**이 이긴다(setdefault)."""
    d = {}
    for p in _candidates():
        try:
            with open(p, encoding='utf-8') as f:
                for line in f:
                    s = line.strip()
                    if not s or s.startswith('#') or '=' not in s:
                        continue
                    k, v = s.split('=', 1)
                    k = k.strip()
                    if not k or not k.replace('_', '').isalnum():
                        continue          # '=====' 구분선·주석 잔재 무시
                    d.setdefault(k, v.strip().strip('"').strip("'"))
        except (FileNotFoundError, NotADirectoryError, OSError):
            continue
    return d


#  프로세스 전체가 공유하는 최종 ENV — 실제 환경변수가 파일보다 우선한다.
ENV = {**read_env(), **os.environ}
