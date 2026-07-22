@echo off
chcp 65001 >nul
title 이음(E-um) 개발 서버
cd /d "%~dp0"

echo ============================================
echo   이음(E-um) 개발 서버를 시작합니다.
echo   (처음이면 라이브러리 설치로 1~2분 걸려요)
echo ============================================
echo.

where node >nul 2>nul
if errorlevel 1 (
  echo [!] Node.js 가 설치돼 있지 않아요.
  echo     https://nodejs.org 에서 LTS 버전을 먼저 설치한 뒤 다시 실행해주세요.
  echo.
  pause
  exit /b 1
)

REM 서버가 뜬 뒤 브라우저를 자동으로 연다 (5초 대기)
start "" /b cmd /c "timeout /t 5 >nul & start http://localhost:5173"

REM predev(자동설치) -> vite 실행
call npm run dev

pause
