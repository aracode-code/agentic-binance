@echo off
:ulang
set symbol=
set /p symbol=Masukkan pair coin (contoh: BTCUSDT): 
venv\Scripts\python.exe app.py %symbol%
echo.
echo ============================================
echo Ketik pair lain, atau Enter untuk BTCUSDT.
echo Tekan Ctrl+C untuk keluar.
echo ============================================
echo.
goto ulang