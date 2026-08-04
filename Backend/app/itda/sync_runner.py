# -*- coding: utf-8 -*-
"""잇다 · 데이터 최신화 실행기 (2026-08-04 신설)

무엇을 하나
  관리자 화면의 「진로 데이터 최신화」 버튼이 이걸 부른다. 적재 배치와 임베딩 배치를
  **순서대로 백그라운드에서 돌리고**, 진행 상황을 화면이 폴링해 볼 수 있게 들고 있는다.

왜 서브프로세스인가 (중요)
  배치 스크립트(app/itda/scripts/*.py)는 **모듈 최상위 실행형**이다.
    · main() 함수가 없다 — import 하는 순간 전체가 실행된다
    · sys.argv 를 최상위에서 읽는다   (예: embed_cert.py 의 FORCE = '--all' in sys.argv)
    · 블로킹 time.sleep 과 동기 pymysql 커넥션을 쓴다 — 이벤트 루프를 통째로 멈춘다
  그래서 import 해서 함수처럼 부를 수 없다. 억지로 부르려면 배치 4개를 다 뜯어고쳐야 하는데,
  그건 지금 잘 도는 코드를 발표 직전에 흔드는 일이다.
  ⇒ 지금 사람이 터미널에서 치는 것과 **똑같은 명령**을 서브프로세스로 돌리고,
    스크립트가 이미 찍고 있는 진행 로그를 읽어 퍼센트를 뽑는다.

진행률은 어디서 오나
  embed_cert·embed_course 가 배치마다 이렇게 찍는다:
      «  300/613  (48%)  경과 21초»
  이 줄을 정규식으로 읽는다. 못 읽어도 단계 진행에는 지장이 없다(퍼센트만 안 보인다).

상태를 메모리에 두는 이유와 그 한계
  덜다는 policy_embedding_result 테이블에 진행 상태를 쌓는다. 잇다는 그런 테이블이 없고,
  itda_sync_log 는 **끝난 뒤 한 줄 INSERT** 구조라 진행 중 상태를 담을 자리가 없다.
  테이블을 새로 파는 건 ERD 를 건드리는 일이라 지금은 메모리에 둔다.
  한계 — 프로세스가 재시작되면 진행 상태가 사라진다. 워커가 여러 개면 워커마다 따로 본다.
  (실행 **이력**은 배치들이 itda_sync_log 에 남기므로 그대로 남는다. 잃는 건 '진행 중' 표시뿐.)
"""
import asyncio
import datetime
import re
import sys
from pathlib import Path

#  Backend/ — `python -m app.itda.scripts.…` 가 동작하려면 여기가 작업 디렉터리여야 한다.
BACKEND_ROOT = Path(__file__).resolve().parents[2]

#  화면에 보이는 3단계. 덜다(API 호출 → 크롤링 → 해시 비교 및 임베딩)와 같은 수로 맞췄다.
STEPS = [
    {
        'key': 'load',
        'title': '데이터 적재',
        'desc': '자격증·강좌 원본 데이터 동기화',
        'commands': [
            ['-m', 'app.itda.scripts.load_certification'],
            ['-m', 'app.itda.scripts.load_course'],
        ],
    },
    {
        'key': 'embed_cert',
        'title': '자격증 임베딩',
        'desc': '해시가 바뀐 자격증만 벡터화',
        'commands': [['-m', 'app.itda.scripts.embed_cert']],
    },
    {
        'key': 'embed_course',
        'title': '강좌 임베딩',
        'desc': '해시가 바뀐 강좌만 벡터화',
        'commands': [['-m', 'app.itda.scripts.embed_course']],
    },
]

#  «  300/613  (48%)  경과 21초» 에서 퍼센트를 집는다.
_PROGRESS = re.compile(r'(\d+)\s*/\s*(\d+)\s*\((\d+)%\)')

#  단계별 타임아웃 — 강좌 8,273개 전체 재임베딩이 최악이다(실측 10분대).
#  넉넉히 두되 무한정 매달리지는 않게 한다.
STEP_TIMEOUT = 60 * 40

_STATE: dict | None = None
_LOCK = asyncio.Lock()


def _fresh_state() -> dict:
    return {
        'run_id': datetime.datetime.now().strftime('%Y%m%d%H%M%S'),
        'status': 'running',          # running · done · failed
        'started_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'finished_at': None,
        'current': STEPS[0]['key'],
        'message': '',
        'steps': [
            {'key': s['key'], 'title': s['title'], 'desc': s['desc'],
             'status': 'waiting',      # waiting · running · ok · failed
             'percent': 0, 'log': ''}
            for s in STEPS
        ],
    }


def snapshot() -> dict | None:
    """현재 진행 상황. 아직 한 번도 안 돌렸으면 None."""
    if _STATE is None:
        return None
    #  얕은 복사로 충분하다 — 호출부는 읽기만 한다. steps 만 각각 복사한다.
    return {**_STATE, 'steps': [dict(s) for s in _STATE['steps']]}


def is_running() -> bool:
    return _STATE is not None and _STATE['status'] == 'running'


async def _run_one(cmd: list[str], step: dict) -> tuple[bool, str]:
    """배치 하나를 서브프로세스로 돌리며 진행 로그를 읽는다. (성공여부, 마지막 줄)

    ★ 타임아웃을 **여기 안에서** 건다. 바깥에서 asyncio.wait_for 로 감싸면 이 코루틴만
      취소되고 자식 프로세스는 그대로 살아남아, 임베딩이 몰래 계속 돌면서 Pinecone·
      Gemini 쿼터를 태운다. 취소하려면 반드시 kill 까지 해야 한다.
    """
    proc = await asyncio.create_subprocess_exec(
        sys.executable, *cmd,
        cwd=str(BACKEND_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    last = ''

    async def pump():
        nonlocal last
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                break
            #  배치는 한글을 찍는다. 서버(리눅스)는 utf-8, 개발 PC(윈도우)는 cp949 일 수 있어
            #  깨져도 죽지 않게 replace 로 받는다 — 로그가 목적이지 파싱 정확도가 목적이 아니다.
            line = raw.decode('utf-8', errors='replace').rstrip()
            if not line:
                continue
            last = line
            step['log'] = line[:200]
            m = _PROGRESS.search(line)
            if m:
                step['percent'] = min(100, int(m.group(3)))
        await proc.wait()

    try:
        await asyncio.wait_for(pump(), timeout=STEP_TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return False, f'{STEP_TIMEOUT // 60}분을 넘겨 중단했어요.'
    except asyncio.CancelledError:
        proc.kill()
        await proc.wait()
        raise
    return proc.returncode == 0, last


async def _run_all() -> None:
    """단계를 순서대로 실행한다. 한 단계가 실패해도 다음 단계는 계속한다.

    왜 계속하나: 적재(외부 API)가 실패해도 이미 있는 데이터로 임베딩은 할 수 있다.
    한 곳이 막혔다고 전체를 포기하면 관리자가 할 수 있는 일이 없어진다.
    """
    failed_any = False
    try:
        for spec, step in zip(STEPS, _STATE['steps']):
            _STATE['current'] = spec['key']
            step['status'] = 'running'
            ok_all = True
            for cmd in spec['commands']:
                try:
                    #  타임아웃·취소는 _run_one 안에서 kill 까지 책임진다(위 주석 참고).
                    ok, last = await _run_one(cmd, step)
                except Exception as e:                      # noqa: BLE001
                    ok, last = False, f'{type(e).__name__}: {str(e)[:120]}'
                if not ok:
                    ok_all = False
                    step['log'] = last[:200]
                    break
            step['status'] = 'ok' if ok_all else 'failed'
            step['percent'] = 100 if ok_all else step['percent']
            failed_any = failed_any or not ok_all
    finally:
        _STATE['status'] = 'failed' if failed_any else 'done'
        _STATE['finished_at'] = datetime.datetime.now().isoformat(timespec='seconds')
        _STATE['message'] = ('일부 단계가 실패했어요. 각 단계의 메시지를 확인해 주세요.'
                             if failed_any else '최신화가 끝났어요.')


async def start() -> dict:
    """최신화를 시작한다. 이미 돌고 있으면 그 상태를 그대로 돌려준다(중복 실행 금지)."""
    global _STATE
    async with _LOCK:
        if is_running():
            return snapshot()
        _STATE = _fresh_state()
        asyncio.create_task(_run_all())
        return snapshot()
