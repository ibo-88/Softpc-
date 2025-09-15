#!/usr/bin/env python3
# main.py - Точка входа в приложение

"""
Telegram Account Manager & Parser
Десктопное приложение для управления Telegram аккаунтами и парсинга данных

Возможности:
- Управление множественными Telegram аккаунтами
- Проверка статуса аккаунтов (спам-блок, заморожены, валидные)
- Парсинг участников групп и каналов
- Парсинг сообщений из чатов
- Автоматизированные задачи (рассылка, смена профилей, создание каналов)
- Управление прокси
- Экспорт данных в CSV/JSON форматы

Автор: AI Assistant
Версия: 2.0
"""

import sys
import os
import tkinter as tk
from tkinter import messagebox
import logging

# Добавляем текущую директорию в путь для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def setup_logging():
    """Настройка логирования"""
    log_dir = os.path.join("data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'app.log')),
            logging.StreamHandler()
        ]
    )

def check_dependencies():
    """Проверка необходимых зависимостей"""
    required_modules = [
        'telethon', 'aiohttp', 'tkinter'
    ]
    
    missing = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    
    if missing:
        error_msg = f"Отсутствуют необходимые модули: {', '.join(missing)}\n\n"
        error_msg += "Установите их командой:\n"
        error_msg += f"pip install {' '.join(missing)}"
        
        # Показываем ошибку в GUI если tkinter доступен
        if 'tkinter' not in missing:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Ошибка зависимостей", error_msg)
            root.destroy()
        else:
            print(error_msg)
        
        return False
    
    return True

def main():
    """Главная функция приложения"""
    print("🚀 Запуск Telegram Account Manager & Parser v2.0")
    
    # Настройка логирования
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Проверка зависимостей
        if not check_dependencies():
            sys.exit(1)
        
        logger.info("Проверка зависимостей пройдена")
        
        # Импорт основного приложения
        try:
            from gui_app import TelegramManagerGUI
        except ImportError as e:
            logger.error(f"Ошибка импорта GUI приложения: {e}")
            messagebox.showerror("Ошибка", f"Не удалось загрузить приложение: {e}")
            sys.exit(1)
        
        # Создание и запуск приложения
        logger.info("Создание GUI приложения...")
        app = TelegramManagerGUI()
        
        logger.info("Запуск основного цикла приложения")
        app.run()
        
        logger.info("Приложение завершено")
        
    except KeyboardInterrupt:
        logger.info("Приложение прервано пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        
        # Показываем ошибку пользователю
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Критическая ошибка", 
                               f"Произошла неожиданная ошибка:\n\n{e}\n\nПроверьте логи для подробностей.")
            root.destroy()
        except:
            print(f"Критическая ошибка: {e}")
        
        sys.exit(1)

if __name__ == "__main__":
    main()