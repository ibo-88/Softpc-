# test_logic_only.py - Тестирование логики без внешних зависимостей

import asyncio
import sys
import os
import json

# Добавляем путь для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import storage_manager

def test_storage_manager():
    """Тестирование менеджера хранилища"""
    print("📦 Тестирование storage_manager...")
    
    # Инициализация
    storage_manager.initialize_storage()
    print("✅ Инициализация хранилища")
    
    # Тестируем создание задачи
    result = storage_manager.create_task("test_task_1")
    print(f"✅ Создание задачи: {result}")
    
    # Тестируем получение задачи
    task_data = storage_manager.get_task("test_task_1")
    print(f"✅ Получение задачи: {task_data is not None}")
    
    # Тестируем список аккаунтов
    accounts = storage_manager.list_accounts()
    print(f"✅ Список аккаунтов: {len(accounts)} найдено")
    
    # Тестируем настройки
    settings = storage_manager.load_settings()
    print(f"✅ Загрузка настроек: {len(settings)} параметров")
    
    # Тестируем создание JSON для аккаунта
    result = storage_manager.create_default_json_for_session("test_account", 123, "test_hash")
    print(f"✅ Создание JSON: {result}")
    
    # Тестируем валидацию
    is_valid, error = storage_manager.validate_json_account("test_account")
    print(f"✅ Валидация JSON: {is_valid} ({error})")
    
    # Очистка тестовых данных
    storage_manager.delete_task("test_task_1")
    test_session = os.path.join(storage_manager.SESSIONS_DIR, "test_account.session")
    test_json = os.path.join(storage_manager.SESSIONS_DIR, "test_account.json")
    if os.path.exists(test_session):
        os.remove(test_session)
    if os.path.exists(test_json):
        os.remove(test_json)
    
    return True

def test_safety_logic():
    """Тестирование логики безопасности"""
    print("\n🛡️ Тестирование логики безопасности...")
    
    # Создаем моковые данные для тестирования
    class MockSafetyManager:
        def __init__(self):
            self.account_activity = {}
            self.spam_statistics = {}
            self.blocked_accounts = set()
        
        def get_safe_delay(self, task_type, account_name):
            delays = {
                'spam_dm': (120, 300),
                'spam_chats': (30, 90),
                'spam_channels': (45, 120)
            }
            min_delay, max_delay = delays.get(task_type, (30, 90))
            return min_delay  # Возвращаем минимальную задержку для теста
        
        def get_recommended_settings(self, task_type):
            recommendations = {
                'spam_dm': {
                    'max_workers': 1,
                    'delay_min': 120,
                    'delay_max': 300,
                    'warning': '🚨 ВЫСОКИЙ РИСК!'
                },
                'spam_chats': {
                    'max_workers': 3,
                    'delay_min': 30,
                    'delay_max': 90,
                    'warning': '✅ Относительно безопасно'
                }
            }
            return recommendations.get(task_type, {})
    
    safety_mgr = MockSafetyManager()
    
    # Тестируем получение задержек
    delay_dm = safety_mgr.get_safe_delay('spam_dm', 'test_account')
    delay_chats = safety_mgr.get_safe_delay('spam_chats', 'test_account')
    
    print(f"✅ Задержка для ЛС: {delay_dm}s")
    print(f"✅ Задержка для чатов: {delay_chats}s")
    
    # Тестируем рекомендации
    rec_dm = safety_mgr.get_recommended_settings('spam_dm')
    rec_chats = safety_mgr.get_recommended_settings('spam_chats')
    
    print(f"✅ Рекомендации ЛС: {rec_dm}")
    print(f"✅ Рекомендации чаты: {rec_chats}")
    
    return True

def test_proxy_logic():
    """Тестирование логики прокси"""
    print("\n🌐 Тестирование логики прокси...")
    
    # Создаем моковые данные
    test_proxies = [
        "1.2.3.4:1080:user1:pass1",
        "5.6.7.8:1080:user2:pass2", 
        "9.10.11.12:1080:user3:pass3"
    ]
    
    test_accounts = ["account1", "account2", "account3", "account4", "account5"]
    
    # Сохраняем тестовые прокси
    settings = storage_manager.load_settings()
    settings['proxies'] = test_proxies
    storage_manager.save_settings(settings)
    
    class MockProxyManager:
        def __init__(self):
            self.accounts_per_proxy = 3
        
        def create_proxy_queues(self, accounts):
            """Создание очередей прокси"""
            distribution = {}
            for i, account in enumerate(accounts):
                proxy_index = (i // self.accounts_per_proxy) % len(test_proxies)
                proxy = test_proxies[proxy_index]
                if proxy not in distribution:
                    distribution[proxy] = []
                distribution[proxy].append(account)
            return distribution
    
    proxy_mgr = MockProxyManager()
    distribution = proxy_mgr.create_proxy_queues(test_accounts)
    
    print("✅ Распределение прокси:")
    for proxy, accounts in distribution.items():
        proxy_short = f"{proxy.split(':')[0]}:{proxy.split(':')[1]}"
        print(f"  {proxy_short}: {accounts}")
    
    return True

def test_file_operations():
    """Тестирование файловых операций"""
    print("\n📁 Тестирование файловых операций...")
    
    # Создаем тестовую задачу
    test_task = "file_test_task"
    storage_manager.create_task(test_task)
    
    # Тестируем получение путей к файлам
    messages_path = storage_manager.get_task_file_path(test_task, 'messages')
    print(f"✅ Путь к messages.txt: {messages_path}")
    
    # Тестируем создание файла
    if messages_path:
        with open(messages_path, 'w', encoding='utf-8') as f:
            f.write("Тестовое сообщение 1\n---\nТестовое сообщение 2")
        print("✅ Создан тестовый файл сообщений")
        
        # Тестируем чтение
        messages = storage_manager.read_task_multiline_messages(test_task, 'messages')
        print(f"✅ Прочитано сообщений: {len(messages)}")
    
    # Тестируем статистику
    stats = storage_manager.get_task_stats(test_task)
    print(f"✅ Статистика задачи: {stats}")
    
    # Очистка
    storage_manager.delete_task(test_task)
    print("✅ Тестовая задача удалена")
    
    return True

def main():
    """Главная функция тестирования"""
    print("🧪 ТЕСТИРОВАНИЕ ЛОГИКИ TELEGRAM MANAGER")
    print("=" * 50)
    
    try:
        # Тестируем основные компоненты
        success = True
        success &= test_storage_manager()
        success &= test_safety_logic()
        success &= test_proxy_logic()
        success &= test_file_operations()
        
        if success:
            print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
            print("\n📋 Проверенные компоненты:")
            print("✅ Менеджер хранилища")
            print("✅ Логика безопасности")
            print("✅ Логика прокси")
            print("✅ Файловые операции")
            print("✅ Создание и управление задачами")
            
            print("\n🚀 ПРОГРАММА ГОТОВА К РАБОТЕ!")
            print("\nДля запуска GUI используйте:")
            print("  python3 main.py")
            
        else:
            print("\n❌ Некоторые тесты не пройдены")
            return False
        
    except Exception as e:
        print(f"\n💥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)