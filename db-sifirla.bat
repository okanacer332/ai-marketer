@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "COMPOSE_FILE=%ROOT%docker-compose.yml"
set "MONGO_VOLUME=acrtech_mongodb_data"
set "LEGACY_STORE=%ROOT%backend\data\workspace_snapshots.json"

echo.
echo ======================================
echo   Acrtech AI Marketer DB Sifirlama
echo ======================================
echo.

call :check_docker || exit /b 1
call :check_file "%COMPOSE_FILE%" "docker-compose.yml" || exit /b 1

echo [1/4] Docker stack durduruluyor...
docker compose -f "%COMPOSE_FILE%" down --remove-orphans

echo [2/4] MongoDB volume siliniyor...
docker volume rm -f %MONGO_VOLUME% >nul 2>nul
docker volume inspect %MONGO_VOLUME% >nul 2>nul
if not errorlevel 1 (
  echo [HATA] MongoDB volume silinemedi: %MONGO_VOLUME%
  pause
  exit /b 1
)
echo [OK] MongoDB volume temizlendi: %MONGO_VOLUME%

echo [3/4] Eski dosya tabanli snapshot deposu temizleniyor...
if exist "%LEGACY_STORE%" (
  del /f /q "%LEGACY_STORE%"
  if errorlevel 1 (
    echo [HATA] Legacy snapshot dosyasi silinemedi:
    echo %LEGACY_STORE%
    pause
    exit /b 1
  )
  echo [OK] Legacy snapshot dosyasi silindi.
) else (
  echo [BILGI] Legacy snapshot dosyasi zaten yok.
)

echo [4/4] Sifirlama tamamlandi.
echo.
echo Not:
echo - MongoDB verisi tamamen temizlendi.
echo - Firebase hesaplari silinmedi.
echo - Uygulama workspace cache'i artik browser'da tutulmuyor.
echo - Firebase oturum verisi tarayicida kalabilir; gerekirse cikis yapin ya da oturumu temizleyin.
echo.
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
