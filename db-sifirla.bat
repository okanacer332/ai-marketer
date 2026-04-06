@echo off
setlocal

cd /d "%~dp0"
set "ROOT=%cd%"

set "COMPOSE_FILE=%ROOT%\docker-compose.yml"
set "MONGO_VOLUME=acrtech_mongodb_data"
set "OLD_FRONTEND_VOLUME=acrtech_frontend_node_modules"
set "LEGACY_STORE=%ROOT%\backend\data\workspace_snapshots.json"

echo.
echo ======================================
echo   Acrtech AI Marketer DB Sifirlama
echo ======================================
echo.

call :check_command docker "Docker" || exit /b 1
call :check_file "%COMPOSE_FILE%" "docker-compose.yml" || exit /b 1
call :check_docker || exit /b 1

echo [1/5] Docker stack durduruluyor...
docker compose -f "%COMPOSE_FILE%" down --remove-orphans

echo [2/5] Eski Docker frontend kalintilari temizleniyor...
docker rm -f acrtech-frontend >nul 2>nul
docker volume rm -f %OLD_FRONTEND_VOLUME% >nul 2>nul

echo [3/5] MongoDB volume siliniyor...
docker volume rm -f %MONGO_VOLUME% >nul 2>nul
docker volume inspect %MONGO_VOLUME% >nul 2>nul
if not errorlevel 1 (
  echo [HATA] MongoDB volume silinemedi: %MONGO_VOLUME%
  pause
  exit /b 1
)
echo [OK] MongoDB volume temizlendi: %MONGO_VOLUME%

echo [4/5] Eski dosya tabanli snapshot deposu temizleniyor...
if exist "%LEGACY_STORE%" (
  del /f /q "%LEGACY_STORE%"
  if errorlevel 1 (
    echo [HATA] Legacy snapshot dosyasi silinemedi.
    echo %LEGACY_STORE%
    pause
    exit /b 1
  )
  echo [OK] Legacy snapshot dosyasi silindi.
) else (
  echo [BILGI] Legacy snapshot dosyasi zaten yok.
)

echo [5/5] Sifirlama tamamlandi.
echo.
echo Not:
echo - MongoDB verisi tamamen temizlendi.
echo - Docker frontend artik kullanilmiyor.
echo - Local Vite frontend bu script tarafindan kapatilmaz.
echo - Firebase hesaplari ve browser session bilgileri bu script ile silinmez.
echo.
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
