@echo off
setlocal
cd /d "%~dp0.."
set PY=.venv\Scripts\python.exe
set BROWSERS=%LOCALAPPDATA%\ms-playwright

if not exist %PY% (echo Missing .venv. Run run.bat once first. & exit /b 1)
%PY% -m pip install -q -r requirements-build.txt || exit /b 1

if exist build rmdir /s /q build
if exist dist\PrivacyLens rmdir /s /q dist\PrivacyLens
%PY% -m PyInstaller --noconfirm --distpath dist --workpath build packaging\privacylens.spec || exit /b 1

for /d %%D in ("%BROWSERS%\chromium_headless_shell-*") do (
    robocopy "%%D" "dist\PrivacyLens\browsers\%%~nxD" /E /NFL /NDL /NJH /NJS /NP >nul
)
if not exist dist\PrivacyLens\browsers\chromium_headless_shell-* (echo Headless Chromium not found in %BROWSERS%. & exit /b 1)
copy /y .env.example dist\PrivacyLens\.env.example >nul

if exist dist\PrivacyLens-windows.zip del dist\PrivacyLens-windows.zip
powershell -NoProfile -Command "Compress-Archive -Path dist\PrivacyLens -DestinationPath dist\PrivacyLens-windows.zip"
echo Built dist\PrivacyLens\PrivacyLens.exe and dist\PrivacyLens-windows.zip
