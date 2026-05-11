@echo off
:: Vzlom Updater — Lance le script Python d'update
:: Si Python pas installé, le télécharge et installe

title Vzlom Updater

echo.
echo  ======================================
echo    Vzlom Updater v2.0
echo  ======================================
echo.

:: Chercher Python
where python >nul 2>&1
if %ERRORLEVEL% == 0 goto RunPython

where python3 >nul 2>&1
if %ERRORLEVEL% == 0 (
    set PYTHON=python3
    goto RunPython
)

:: Python pas trouvé, le télécharger
echo Python n'est pas installe. Telechargement...
echo.
powershell -Command "& {Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe' -OutFile '%TEMP%\python_installer.exe'; Start-Process '%TEMP%\python_installer.exe' -ArgumentList '/quiet InstallAllUsers=0 PrependPath=1' -Wait}"
echo.
echo Python installe. Relance le script.
pause
exit /b

:RunPython
echo Lancement de la mise a jour...
echo.
python VzlomUpdater.py
pause
