@echo off
setlocal

cd /d "%~dp0"
set "ROOT=%cd%"

set "COMPOSE_FILE=%ROOT%\docker-compose.yml"
set "FRONTEND_ENV=%ROOT%\.env.local"
set "BACKEND_ENV=%ROOT%\backend\.env"
set "FRONTEND_URL=http://localhost:5173"
set "BACKEND_URL=http://localhost:8000/api/health"
set "FRONTEND_WINDOW_TITLE=Acrtech Frontend"

echo.
echo ======================================
echo   Acrtech AI Marketer Baslatma
echo   Docker: backend + mongodb
echo   Local : vite frontend
echo ======================================
echo.

call :check_command docker "Docker" || exit /b 1
call :check_command npm "npm" || exit /b 1
call :check_file "%COMPOSE_FILE%" "docker-compose.yml" || exit /b 1
call :check_file "%FRONTEND_ENV%" ".env.local" || exit /b 1
call :check_file "%BACKEND_ENV%" "backend\\.env" || exit /b 1
call :check_docker || exit /b 1

if not exist "%ROOT%\node_modules" (
  echo [1/6] node_modules bulunamadi, npm install calisiyor...
  call npm install
  if errorlevel 1 (
    echo [HATA] npm install basarisiz oldu.
    pause
    exit /b 1
  )
) else (
  echo [1/6] node_modules hazir.
)

echo [2/6] Eski Docker frontend kalintilari temizleniyor...
docker rm -f acrtech-frontend >nul 2>nul

echo [3/6] MongoDB ve backend Docker uzerinde baslatiliyor...
docker compose -f "%COMPOSE_FILE%" up -d --build --remove-orphans mongodb backend
if errorlevel 1 (
  echo [HATA] Docker servisleri baslatilamadi.
  pause
  exit /b 1
)

echo [4/6] Backend saglik kontrolu bekleniyor...
call :wait_url "%BACKEND_URL%" "Backend API" 90 || exit /b 1

echo [5/6] Frontend kontrol ediliyor...
call :url_ready "%FRONTEND_URL%"
if errorlevel 1 (
  echo [BILGI] Local frontend baslatiliyor...
  start "%FRONTEND_WINDOW_TITLE%" /D "%ROOT%" cmd /k npm run dev
  call :wait_url "%FRONTEND_URL%" "Frontend" 90 || exit /b 1
) else (
  echo [OK] Frontend zaten calisiyor.
)

echo [6/6] Servis ozeti:
docker compose -f "%COMPOSE_FILE%" ps

echo.
echo Frontend: %FRONTEND_URL%
echo Backend : http://localhost:8000
echo MongoDB : mongodb://localhost:27017
echo.
echo Tarayici aciliyor...
start "" "%FRONTEND_URL%"
echo Hazir.
exit /b 0

:check_command
where %~1 >nul 2>nul
if errorlevel 1 (
  echo [HATA] %~2 bulunamadi.
  pause
  exit /b 1
)
exit /b 0

:check_docker
docker compose version >nul 2>nul
if errorlevel 1 (
  echo [HATA] docker compose kullanilamiyor.
  pause
  exit /b 1
)

docker info >nul 2>nul
if errorlevel 1 (
  echo [HATA] Docker Desktop calismiyor.
  pause
  exit /b 1
)

exit /b 0

:check_file
if exist "%~1" exit /b 0

echo [HATA] Gerekli dosya bulunamadi: %~2
pause
exit /b 1

:url_ready
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { $response = Invoke-WebRequest -Uri '%~1' -UseBasicParsing -TimeoutSec 5; if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>nul
exit /b %errorlevel%

:wait_url
set "TARGET_URL=%~1"
set "TARGET_NAME=%~2"
set "MAX_RETRIES=%~3"
set /a RETRY_COUNT=0

:wait_loop
call :url_ready "%TARGET_URL%"
if not errorlevel 1 (
  echo [OK] %TARGET_NAME% hazir.
  exit /b 0
)

set /a RETRY_COUNT+=1
if %RETRY_COUNT% geq %MAX_RETRIES% (
  echo [HATA] %TARGET_NAME% beklenen surede hazir olmadi.
  echo [BILGI] Backend loglari icin: docker compose -f "%COMPOSE_FILE%" logs backend
  pause
  exit /b 1
)

timeout /t 2 /nobreak >nul
goto wait_loop
