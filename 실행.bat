@echo off
chcp 65001 > nul
title 견적서 자동 추출기

echo.
echo  ========================================
echo   견적서 자동 추출기 시작 중...
echo  ========================================
echo.

:: 현재 스크립트 위치로 이동
cd /d "%~dp0"

:: .env 파일 확인
if not exist ".env" (
    echo  [오류] .env 파일이 없습니다.
    echo.
    echo  프로젝트 폴더에 .env 파일을 만들고
    echo  아래 내용을 입력하세요:
    echo.
    echo    GEMINI_API_KEY=여기에_API_키_입력
    echo.
    echo  API 키 발급: https://aistudio.google.com
    echo.
    pause
    exit /b 1
)

:: uv 설치 여부 확인
where uv > nul 2>&1
if %errorlevel% neq 0 (
    echo  [안내] uv가 설치되어 있지 않습니다. 자동 설치합니다...
    echo.
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    if %errorlevel% neq 0 (
        echo  [오류] uv 설치에 실패했습니다.
        echo  관리자 권한으로 다시 실행해보세요.
        pause
        exit /b 1
    )
    echo.
    echo  uv 설치 완료!
    echo.
    :: PATH 갱신을 위해 새 환경변수 로드
    call refreshenv > nul 2>&1
)

:: 의존성 설치 (처음 한 번만 시간 걸림)
echo  [1/2] 필요한 패키지 확인 중...
uv sync --quiet
if %errorlevel% neq 0 (
    echo  [오류] 패키지 설치에 실패했습니다.
    pause
    exit /b 1
)

:: output 폴더 생성
if not exist "output" mkdir output

echo  [2/2] 서버 시작 중...
echo.
echo  ========================================
echo   4초 후 브라우저가 자동으로 열립니다.
echo   열리지 않으면 아래 주소를 직접 복사하세요:
echo.
echo     http://localhost:8501
echo.
echo   종료: 이 창을 닫거나 Ctrl+C
echo  ========================================
echo.

:: 4초 후 브라우저 자동 오픈 (백그라운드)
start /b powershell -NoProfile -Command "Start-Sleep 4; Start-Process 'http://localhost:8501'"

:: Streamlit 실행 (이 창에서 서버 유지)
uv run streamlit run demo.py --server.headless true --browser.gatherUsageStats false

pause
