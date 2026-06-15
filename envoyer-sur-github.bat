@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   Envoi du projet MobilPyton sur GitHub
echo ============================================
echo.

git add .

set /p msg="Decris ton changement (ou appuie sur Entree) : "
if "%msg%"=="" set msg=mise a jour

git commit -m "%msg%"
git push

echo.
echo ============================================
echo   Termine. Le build APK demarre tout seul :
echo   https://github.com/xxbenboy/MobilPyton/actions
echo ============================================
pause
