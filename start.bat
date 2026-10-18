@echo off
title Telegram MTProto Stream Server
echo ======================================================
echo    Telegram MTProto File Storage and Stream Server
echo ======================================================
echo.

if not exist .env (
    echo [!] .env file nahi mili!
    echo [.env.example] ko copy karke [.env] banaya ja raha hai...
    copy .env.example .env
    echo.
    echo [ACTION REQUIRED] Kripya '.env' file me apna API_ID, API_HASH,
    echo BOT_TOKEN aur BIN_CHANNEL daalein, phir is script ko dobara run karein.
    echo.
    notepad .env
    pause
    exit /b
)

if not exist venv (
    echo [*] Creating Python Virtual Environment...
    python -m venv venv
    call .\venv\Scripts\activate
    echo [*] Installing dependencies...
    pip install -r requirements.txt
) else (
    call .\venv\Scripts\activate
)

echo [*] Starting Server...
python main.py
pause
