@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "FRONTEND_ENV=%ROOT%.env.local"
set "BACKEND_ENV=%ROOT%backend\.env"
set "COMPOSE_FILE=%ROOT%docker-compose.yml"
set "FRONTEND_URL=http://127.0.0.1:5173"
set "BACKEND_URL=http://127.0.0.1:8000/api/health"

echo.
echo ======================================
echo   Acrtech AI Marketer Docker Baslatma
echo ======================================
echo.

call :check_docker || exit /b 1
call :check_file "%COMPOSE_FILE%" "docker-compose.yml" || exit /b 1
call :check_file "%FRONTEND_ENV%" ".env.local" || exit /b 1
call :check_file "%BACKEND_ENV%" "backend\\.env" || exit /b 1

echo [1/5] MongoDB ve backend image/servisleri hazirlaniyor...
docker compose -f "%COMPOSE_FILE%" up -d --build --remove-orphans mongodb backend
if errorlevel 1 (
  echo [HATA] MongoDB ve backend baslatilamadi.
  pause
  exit /b 1
)

echo [2/5] Backend saglik kontrolu bekleniyor...
call :wait_url "%BACKEND_URL%" "Backend API" 60 || exit /b 1

echo [3/5] Frontend image/servisi hazirlaniyor...
docker compose -f "%COMPOSE_FILE%" up -d --build frontend
if errorlevel 1 (
  echo [HATA] Frontend baslatilamadi.
  pause
  exit /b 1
)

echo [4/5] Frontend hazirlaniyor...
call :wait_url "%FRONTEND_URL%" "Frontend" 60 || exit /b 1

echo [5/5] Servis ozeti:
docker compose -f "%COMPOSE_FILE%" ps

echo.
echo Frontend: %FRONTEND_URL%
echo Backend : http://127.0.0.1:8000
echo MongoDB : mongodb://127.0.0.1:27017
echo.
echo Tarayici aciliyor...
start "" "%FRONTEND_URL%"
echo.
echo Hazir.
exit /b 0

:check_docker
where docker >nul 2>nul
if errorlevel 1 (
  echo [HATA] Docker bulunamadi. Docker Desktop kurulu olmali.
  pause
  exit /b 1
)

docker compose version >nul 2>nul
if errorlevel 1 (
  echo [HATA] docker compose kullanilamiyor. Docker Desktop guncel olmali.
  pause
  exit /b 1
)

docker info >nul 2>nul
if errorlevel 1 (
  echo [HATA] Docker calismiyor. Docker Desktop'i acip tekrar deneyin.
  pause
  exit /b 1
)

exit /b 0

:check_file
if exist "%~1" exit /b 0

echo [HATA] Gerekli dosya bulunamadi: %~2
pause
exit /b 1

:wait_url
set "TARGET_URL=%~1"
set "TARGET_NAME=%~2"
set "MAX_RETRIES=%~3"
set /a RETRY_COUNT=0

:wait_loop
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { $response = Invoke-WebRequest -Uri '%TARGET_URL%' -UseBasicParsing -TimeoutSec 5; if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>nul

if not errorlevel 1 (
  echo [OK] %TARGET_NAME% hazir.
  exit /b 0
)

set /a RETRY_COUNT+=1
if %RETRY_COUNT% geq %MAX_RETRIES% (
  echo [HATA] %TARGET_NAME% beklenen surede hazir olmadi.
  echo [BILGI] Loglar icin: docker compose -f "%COMPOSE_FILE%" logs
  pause
  exit /b 1
)

timeout /t 2 /nobreak >nul
goto wait_loop
