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
import os
import re
import subprocess
import sys
import time
from pathlib import Path

#  Backend/ — `python -m app.itda.scripts.…` 가 동작하려면 여기가 작업 디렉터리여야 한다.
BACKEND_ROOT = Path(__file__).resolve().parents[2]

#  화면에 보이는 3단계. 덜다(API 호출 → 크롤링 → 해시 비교 및 임베딩)와 같은 수로 맞췄다.
STEPS = [
    {
        'key': 'load',
        'title': '데이터 적재',
        'desc': '자격증·강좌·시험일정 원본 데이터 동기화',
        #  ★ 2026-08-05 — **시험일정을 여기 넣는다.** 빠져 있었다.
        #    화면의 「최신화」 버튼이 자격증·강좌만 갱신하고 exam_schedule 은 안 건드려서,
        #    카드에 「접수 ~2026-08-02 (마감)」 같은 지난 회차가 계속 나갔다(실측).
        #    사용자가 카드에서 제일 먼저 보는 게 그 날짜다 — 여기가 낡으면 카드 전체가 낡는다.
        #    ※ Q-Net API 는 당해년도만 준다. 그래서 자주 돌릴수록 다음 회차가 빨리 잡힌다.
        'commands': [
            ['-m', 'app.itda.scripts.load_certification'],
            ['-m', 'app.itda.scripts.load_course'],
            ['-m', 'app.itda.scripts.load_exam_schedule'],
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
             'percent': 0,
             #  배치가 «300/613 (48%)» 을 찍으면 앞의 두 숫자도 함께 담는다.
             #  퍼센트만 보여주면 "얼마나 남았나"를 가늠할 수 없다 — 8,273개짜리 강좌 임베딩에선
             #  48% 라는 말보다 «3,971 / 8,273» 이 훨씬 쓸모 있다.
             'done': 0, 'total': 0,
             'elapsed': 0,             # 그 단계가 시작된 뒤 흐른 초
             'log': ''}
            for s in STEPS
        ],
    }


def snapshot() -> dict | None:
    """현재 진행 상황. 아직 한 번도 안 돌렸으면 None.

    ★ 도는 중인 단계의 경과시간은 **여기서 다시 계산한다.**
      배치가 한 줄 찍을 때만 갱신하면, 적재처럼 조용히 오래 도는 단계에서 시계가 멈춰 보인다
      (「경과 0초」인 채로 3분이 흐른다). 화면이 물어볼 때마다 지금 시각으로 다시 잰다.
    """
    if _STATE is None:
        return None
    now = time.time()
    steps = []
    for s in _STATE['steps']:
        c = dict(s)
        t0 = c.pop('_t0', None)          # 내부용 — 화면에 내보내지 않는다
        if t0 and c['status'] == 'running':
            c['elapsed'] = int(now - t0)
        steps.append(c)
    return {**_STATE, 'steps': steps}


def is_running() -> bool:
    return _STATE is not None and _STATE['status'] == 'running'


def _run_blocking(cmd: list[str], step: dict, holder: dict) -> tuple[bool, str]:
    """배치 하나를 **동기** subprocess 로 돌리며 진행 로그를 읽는다. 별도 스레드에서 호출된다.

    ★ 왜 asyncio.create_subprocess_exec 을 안 쓰나 (2026-08-04 실측)
      윈도우에서 uvicorn 이 SelectorEventLoop 를 쓰면 그 함수가 **NotImplementedError** 를 낸다.
      (윈도우에서 asyncio 서브프로세스는 ProactorEventLoop 에서만 된다)
      혼자 asyncio.run() 으로 돌린 시험은 기본값이 Proactor 라 통과했는데, uvicorn 아래에서는
      3단계가 전부 NotImplementedError 로 죽었다 — 내 시험이 실제 실행 환경과 달랐던 것이다.
      리눅스 서버에서는 안 났을 버그지만, 개발 PC 에서만 죽는 코드는 두면 안 된다.
      ⇒ 이벤트 루프에 기대지 않는 subprocess.Popen 을 스레드에서 돌린다. 어느 OS·어느 루프에서도 같다.

    ★ PYTHONIOENCODING 을 박아 자식이 무조건 utf-8 로 찍게 한다.
      없으면 윈도우 파이썬이 파이프에 cp949 로 써서, 화면에 뜨는 로그가
      «자격증 임베딩 완료» → «?????? ?????? ???» 로 깨진다(실측).
    """
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    proc = subprocess.Popen(
        [sys.executable, *cmd],
        cwd=str(BACKEND_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',      # 깨진 바이트가 와도 죽지 않는다 — 로그가 목적이다
        bufsize=1,             # 줄 단위 — 배치가 찍는 대로 바로 읽힌다
    )
    holder['proc'] = proc      # 타임아웃 때 바깥에서 kill 할 수 있게 넘겨둔다
    last = ''
    t0 = time.time()
    for raw in proc.stdout:
        line = raw.rstrip()
        if not line:
            continue
        last = line
        step['log'] = line[:200]
        step['elapsed'] = int(time.time() - t0)
        m = _PROGRESS.search(line)
        if m:
            step['done'] = int(m.group(1))
            step['total'] = int(m.group(2))
            step['percent'] = min(100, int(m.group(3)))
    proc.wait()
    return proc.returncode == 0, last


async def _run_one(cmd: list[str], step: dict) -> tuple[bool, str]:
    """위 동기 실행을 스레드로 넘기고 타임아웃을 건다. (성공여부, 마지막 줄)

    ★ 타임아웃 때는 **반드시 프로세스를 kill 한다.** 스레드만 버리면 자식은 그대로 살아남아
      임베딩이 몰래 계속 돌면서 Pinecone·Gemini 쿼터를 태운다.
      kill 하면 stdout 이 닫혀 for 루프가 끝나고 스레드도 따라서 정리된다.
    """
    holder: dict = {}
    task = asyncio.create_task(asyncio.to_thread(_run_blocking, cmd, step, holder))
    try:
        return await asyncio.wait_for(asyncio.shield(task), timeout=STEP_TIMEOUT)
    except (asyncio.TimeoutError, asyncio.CancelledError) as e:
        proc = holder.get('proc')
        if proc and proc.poll() is None:
            proc.kill()
        try:
            await task                      # 스레드가 정리될 때까지 기다린다
        except Exception:                   # noqa: BLE001
            pass
        if isinstance(e, asyncio.CancelledError):
            raise
        #  1분 미만이면 «0분» 이 되어 말이 안 되므로 초로 적는다(시험 때 실측).
        #  괄호로 감싸면 «분/초» 어느 쪽이 와도 조사가 어색해지지 않는다.
        limit = (f'{STEP_TIMEOUT // 60}분' if STEP_TIMEOUT >= 60 else f'{STEP_TIMEOUT}초')
        return False, f'제한 시간({limit})을 넘겨 중단했어요.'


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
            step['_t0'] = time.time()          # snapshot() 이 경과시간을 다시 재는 기준
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
