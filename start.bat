@echo off
title Telegram Account Manager & Parser

echo ========================================
echo  Telegram Account Manager ^& Parser v2.0
echo ========================================
echo.

:: Проверка Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ОШИБКА: Python не найден в системе!
    echo Установите Python с официального сайта: https://python.org
    pause
    exit /b 1
)

echo Python найден: 
python --version

:: Проверка зависимостей
echo.
echo Проверка зависимостей...
pip show telethon >nul 2>&1
if %errorlevel% neq 0 (
    echo Установка зависимостей...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo ОШИБКА: Не удалось установить зависимости!
        pause
        exit /b 1
    )
)

:: Запуск приложения
echo.
echo Запуск приложения...
python main.py

:: Пауза при ошибке
if %errorlevel% neq 0 (
    echo.
    echo Приложение завершилось с ошибкой!
    pause
)