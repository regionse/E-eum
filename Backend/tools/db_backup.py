# -*- coding: utf-8 -*-
r"""RDS(eum) 를 로컬 .sql 로 덤프한다 — 읽기 전용. DB 를 «건드리지 않는다».

왜 만들었나
  2026-08-09. 발표(8/11) 뒤 프로젝트를 박제하기로 했고, 그 전에 운영 DB 사본이
  하나도 없었다. RDS 자동 스냅샷은 콘솔에서 확인해야 하는데 이 기계엔 aws CLI 가
  «없다»(where aws → not found). 그래서 mysqldump 로 파일 사본을 만든다.

왜 이 플래그들인가 — 전부 이유가 있다
  --single-transaction  일관된 시점의 사본. InnoDB 라 락을 «안» 잡는다.
                        이게 없으면 덤프 도중 들어온 쓰기가 섞여 깨진 사본이 된다.
  --no-tablespaces      RDS 의 admin 계정엔 PROCESS 권한이 없다. 없으면
                        「Access denied; you need PROCESS privilege」로 «죽는다».
  --set-gtid-purged=OFF GTID 가 켜져 있으면 덤프 앞에 SET @@GLOBAL.gtid_purged 가
                        박히고, 그 사본은 다른 서버에 그냥 못 넣는다.
  --routines --triggers 스키마만이 아니라 로직도 같이. 이벤트(--events)는 RDS 에서
                        권한이 갈려 빼 뒀다 — 지금 eum 에 이벤트도 없다.
  --default-character-set=utf8mb4
                        한글이다. 빼면 «조용히» 깨진다(파일은 만들어진다).

⚠ 비밀번호는 MYSQL_PWD 환경변수로 넘긴다. -p 로 넘기면 작업 관리자·ps 에 그대로 뜬다.
  mysqldump 가 경고를 찍긴 하지만 명령줄 노출보다 낫다.

쓰는 법
  python -m tools.db_backup                 # 기본 위치 C:\e-um-1\backup\
  python -m tools.db_backup --out D:\어딘가
  python -m tools.db_backup --schema-only   # 구조만 (빠름, 확인용)
"""
import argparse
import datetime
import gzip
import io
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

#  ⚠ 없으면 마지막 출력에서 cp949 로 «죽는다». 덤프는 이미 끝난 뒤라 더 헷갈린다
#    (파일은 멀쩡한데 스크립트는 실패로 보인다 — 2026-08-09 실제로 그랬다).
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ENV = Path(__file__).resolve().parent.parent / 'app' / '.env'
MYSQLDUMP = r'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe'
DEFAULT_OUT = Path(r'C:\e-um-1\backup')     # ⚠ 저장소 «밖». 안에 두면 커밋에 딸려 간다


def read_env():
    env = {}
    for ln in ENV.read_text(encoding='utf-8').splitlines():
        ln = ln.strip()
        if ln and not ln.startswith('#') and '=' in ln:
            k, v = ln.split('=', 1)
            env[k.strip()] = v.strip()
    return env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(DEFAULT_OUT))
    ap.add_argument('--schema-only', action='store_true')
    ap.add_argument('--no-gzip', action='store_true')
    a = ap.parse_args()

    if not Path(MYSQLDUMP).exists():
        sys.exit(f'mysqldump 가 없다: {MYSQLDUMP}')

    env = read_env()
    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    tag = 'schema' if a.schema_only else 'full'
    sql = outdir / f'eum_{tag}_{stamp}.sql'

    cmd = [MYSQLDUMP,
           '-h', env['DB_HOST'], '-P', env.get('DB_PORT', '3306'),
           '-u', env['DB_USER'],
           '--single-transaction', '--no-tablespaces',
           '--set-gtid-purged=OFF', '--routines', '--triggers',
           '--default-character-set=utf8mb4',
           '--databases', env.get('DB_NAME', 'eum')]
    if a.schema_only:
        cmd.append('--no-data')

    print(f'  대상   {env["DB_HOST"]} / {env.get("DB_NAME")}')
    print(f'  파일   {sql}')
    t0 = time.time()
    penv = dict(os.environ, MYSQL_PWD=env['DB_PASSWORD'])
    with open(sql, 'wb') as f:
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, env=penv)
    err = (r.stderr or b'').decode('utf-8', 'replace')
    #  「Using a password on the command line」 경고는 MYSQL_PWD 를 써도 나온다. 무시.
    err = '\n'.join(l for l in err.splitlines() if 'password on the command line' not in l)

    if r.returncode != 0:
        print(f'  🔴 실패 (rc={r.returncode})')
        print(err[:2000])
        #  ★ 2026-08-10 — 부분 파일을 지운다(검토가 잡음). 남겨 두면 정상 백업과
        #    같은 이름 규칙(eum_full_*.sql)이라 복원 때 손상본을 집을 수 있다.
        try:
            sql.unlink()
            print('  부분 파일 삭제함')
        except OSError:
            pass
        sys.exit(1)
    if err.strip():
        print(f'  ⚠ 경고: {err.strip()[:500]}')

    size = sql.stat().st_size
    #  ★ 크기 검사 — mysqldump 는 «실패해도 파일을 만든다». 몇 KB 짜리 껍데기를
    #    성공으로 착각한 적이 있어서 여기서 막는다.
    if not a.schema_only and size < 1_000_000:
        print(f'  🔴 파일이 {size:,}B 밖에 안 된다 — 덤프가 제대로 안 됐을 가능성. 열어서 확인할 것')

    #  마지막 줄에 「Dump completed」가 있어야 «끝까지» 쓰인 것이다.
    with open(sql, 'rb') as f:
        f.seek(max(0, size - 400))
        tail = f.read().decode('utf-8', 'replace')
    ok = 'Dump completed' in tail
    print(f'  완결   {"✅ Dump completed 확인" if ok else "🔴 끝맺음 없음 — 중간에 끊겼다"}')

    final = sql
    #  ★ 2026-08-10 — 끝맺음(Dump completed)이 없는 파일은 이름에 .FAILED 를 박는다
    #    (검토가 잡음). 예전엔 rc=0 이면 압축까지 해서 «정상 이름»으로 남겼다 —
    #    복원하는 사람이 이름만 보고 손상본을 못 가려낸다.
    if not ok:
        failed = sql.with_name(sql.stem + '.FAILED' + sql.suffix)
        sql.rename(failed)
        print(f'  이름   {failed.name} (끝맺음 없음 — 압축·정리 생략)')
        sys.exit(2)
    if not a.no_gzip:
        gz = sql.with_suffix('.sql.gz')
        with open(sql, 'rb') as fi, gzip.open(gz, 'wb', compresslevel=6) as fo:
            shutil.copyfileobj(fi, fo, 1 << 20)
        sql.unlink()
        final = gz

    print(f'  크기   {size:,}B → {final.stat().st_size:,}B ({final.name})')
    print(f'  걸린   {time.time() - t0:.1f}초')


if __name__ == '__main__':
    main()
