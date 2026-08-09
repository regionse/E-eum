# -*- coding: utf-8 -*-
r"""RDS 에 SQL 한 방 던지는 도구 — 확인용. 쓰기는 «안» 한다(막지는 않지만 그럴 일이 없다).

왜 필요한가
  2026-08-09. mysql.exe 를 subprocess 로 부를 때마다 두 가지에 계속 걸렸다:
    ① --default-character-set 을 안 주면 stdout 이 cp949 로 나와 UnicodeDecodeError
      (파이썬이 utf-8 로 읽으려다 0xc1 에서 죽는다 — 실제로 두 번 겪었다)
    ② errors='replace' 가 없으면 한 글자 때문에 결과 전체를 잃는다
  그래서 한 곳에 모은다.

쓰는 법
  python -m tools.q "SELECT COUNT(*) FROM certification"
  python -m tools.q --file some.sql
"""
import argparse
import io
import os
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ENV = Path(__file__).resolve().parent.parent / 'app' / '.env'
MYSQL = r'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe'


def env():
    d = {}
    for ln in ENV.read_text(encoding='utf-8').splitlines():
        ln = ln.strip()
        if ln and not ln.startswith('#') and '=' in ln:
            k, v = ln.split('=', 1)
            d[k.strip()] = v.strip()
    return d


def run(sql):
    e = env()
    r = subprocess.run(
        [MYSQL, '-h', e['DB_HOST'], '-P', e.get('DB_PORT', '3306'),
         '-u', e['DB_USER'], '-D', e.get('DB_NAME', 'eum'),
         '--default-character-set=utf8mb4',      # ← ① 없으면 cp949 로 나온다
         '--connect-timeout=15', '-e', sql],
        capture_output=True, env=dict(os.environ, MYSQL_PWD=e['DB_PASSWORD']))
    out = r.stdout.decode('utf-8', 'replace')    # ← ② 한 글자로 전체를 잃지 않는다
    err = '\n'.join(l for l in r.stderr.decode('utf-8', 'replace').splitlines()
                    if 'password on the command line' not in l)
    return r.returncode, out, err


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('sql', nargs='?')
    ap.add_argument('--file')
    a = ap.parse_args()
    q = Path(a.file).read_text(encoding='utf-8') if a.file else a.sql
    rc, out, err = run(q)
    print(out)
    if err.strip():
        print('ERR', err.strip()[:1000])
    sys.exit(rc)
