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

# Проверяем основные модули
if ! $PYTHON_CMD -c "import telethon" &> /dev/null; then
    echo "Установка зависимостей..."
    
    # Пробуем разные способы установки
    if $PIP_CMD install -r requirements.txt &> /dev/null; then
        echo "✅ Зависимости установлены через pip"
    elif $PIP_CMD install -r requirements.txt --user &> /dev/null; then
        echo "✅ Зависимости установлены для пользователя"
    elif $PIP_CMD install -r requirements.txt --break-system-packages &> /dev/null; then
        echo "⚠️ Зависимости установлены с override (может быть небезопасно)"
    else
        echo "❌ Не удалось установить зависимости автоматически"
        echo "Попробуйте вручную:"
        echo "  pip install telethon aiohttp aiohttp-proxy"
        echo "или"
        echo "  pip install --user telethon aiohttp aiohttp-proxy"
        echo ""
        echo "Программа попробует запуститься в консольном режиме..."
    fi
fi

# Проверяем tkinter для GUI
if ! $PYTHON_CMD -c "import tkinter" &> /dev/null; then
    echo "⚠️ Tkinter недоступен - GUI не будет работать"
    echo "Для GUI установите: sudo apt-get install python3-tk (Ubuntu/Debian)"
    echo "Программа запустится в консольном режиме"
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