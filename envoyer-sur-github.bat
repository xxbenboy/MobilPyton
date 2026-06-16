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
echo   Code envoye sur GitHub.
echo   Le build NE demarre PAS tout seul (mode manuel).
echo   Pour fabriquer l'APK quand tu es pret :
echo   1) va sur https://github.com/xxbenboy/MobilPyton/actions
echo   2) clique "Build Android APK" puis "Run workflow"
echo ============================================
pause
