#!/bin/bash

echo "========================================"
echo " Telegram Account Manager & Parser v2.0"
echo "========================================"
echo

# Проверка Python
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "ОШИБКА: Python не найден в системе!"
        echo "Установите Python с официального сайта: https://python.org"
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

echo "Python найден: "
$PYTHON_CMD --version

# Проверка pip
if ! command -v pip3 &> /dev/null; then
    if ! command -v pip &> /dev/null; then
        echo "ОШИБКА: pip не найден!"
        exit 1
    else
        PIP_CMD="pip"
    fi
else
    PIP_CMD="pip3"
fi

# Проверка зависимостей
echo
echo "Проверка зависимостей..."
if ! $PYTHON_CMD -c "import telethon" &> /dev/null; then
    echo "Установка зависимостей..."
    $PIP_CMD install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "ОШИБКА: Не удалось установить зависимости!"
        exit 1
    fi
fi

# Запуск приложения
echo
echo "Запуск приложения..."
$PYTHON_CMD main.py

# Проверка на ошибки
if [ $? -ne 0 ]; then
    echo
    echo "Приложение завершилось с ошибкой!"
    read -p "Нажмите Enter для выхода..."
fi