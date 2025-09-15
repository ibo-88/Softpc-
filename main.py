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
    required_modules = ['telethon', 'aiohttp']
    optional_modules = ['tkinter']
    
    missing_required = []
    missing_optional = []
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_required.append(module)
    
    for module in optional_modules:
        try:
            __import__(module)
        except ImportError:
            missing_optional.append(module)
    
    if missing_required:
        error_msg = f"❌ Отсутствуют обязательные модули: {', '.join(missing_required)}\n\n"
        error_msg += "Установите их командой:\n"
        error_msg += f"pip install {' '.join(missing_required)}"
        print(error_msg)
        return False, False
    
    gui_available = 'tkinter' not in missing_optional
    
    if missing_optional:
        print(f"⚠️ Отсутствуют дополнительные модули: {', '.join(missing_optional)}")
        if 'tkinter' in missing_optional:
            print("GUI интерфейс недоступен. Будет запущен режим командной строки.")
    
    return True, gui_available

def main():
    """Главная функция приложения"""
    print("🚀 Запуск Telegram Account Manager & Parser v2.0")
    
    # Настройка логирования
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Проверка зависимостей
        deps_ok, gui_available = check_dependencies()
        if not deps_ok:
            sys.exit(1)
        
        logger.info("Проверка зависимостей пройдена")
        
        if gui_available:
            # Запуск GUI версии
            try:
                from gui_app import TelegramManagerGUI
                logger.info("Создание GUI приложения...")
                app = TelegramManagerGUI()
                logger.info("Запуск основного цикла приложения")
                app.run()
                logger.info("GUI приложение завершено")
            except ImportError as e:
                logger.error(f"Ошибка импорта GUI: {e}")
                print(f"❌ Не удалось запустить GUI: {e}")
                print("🔄 Попробуйте консольную версию...")
                gui_available = False
        
        if not gui_available:
            # Запуск консольной версии
            print("\n🖥️ Запуск в режиме командной строки...")
            print("📋 Доступные команды:")
            print("1. Тестирование логики")
            print("2. Проверка аккаунтов")
            print("3. Проверка прокси")
            print("4. Создание тестовых данных")
            print("0. Выход")
            
            while True:
                try:
                    choice = input("\nВыберите команду (0-4): ").strip()
                    
                    if choice == "0":
                        break
                    elif choice == "1":
                        os.system("python3 test_logic_only.py")
                    elif choice == "2":
                        print("🔍 Проверка аккаунтов...")
                        accounts = storage_manager.list_accounts()
                        print(f"Найдено аккаунтов: {len(accounts)}")
                        for acc in accounts[:10]:
                            info = storage_manager.get_account_info(acc)
                            print(f"  {acc}: {'✅' if info['json_valid'] else '❌'}")
                    elif choice == "3":
                        print("🌐 Проверка прокси...")
                        settings = storage_manager.load_settings()
                        proxies = settings.get('proxies', [])
                        print(f"Найдено прокси: {len(proxies)}")
                        for proxy in proxies[:5]:
                            proxy_short = f"{proxy.split(':')[0]}:{proxy.split(':')[1]}"
                            print(f"  {proxy_short}")
                    elif choice == "4":
                        print("🛠️ Создание тестовых данных...")
                        storage_manager.create_task("test_task_console")
                        print("✅ Тестовая задача создана")
                    else:
                        print("❌ Неверная команда")
                        
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"❌ Ошибка: {e}")
            
            print("👋 Консольная версия завершена")
        
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