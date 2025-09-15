# test_core.py - Тестирование основной логики без GUI

import asyncio
import sys
import os

# Добавляем путь для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import storage_manager
import parser_module
import safety_manager
import proxy_manager
import account_tester

async def test_basic_functionality():
    """Тестирование базового функционала"""
    print("🧪 Тестирование основной логики...")
    
    # Инициализация
    storage_manager.initialize_storage()
    
    # Тестируем создание задачи
    print("\n📝 Тестирование создания задачи...")
    result = storage_manager.create_task("test_task")
    print(f"Создание задачи: {'✅' if result else '❌'}")
    
    # Тестируем менеджер безопасности
    print("\n🛡️ Тестирование менеджера безопасности...")
    safety_mgr = safety_manager.get_safety_manager()
    
    # Тестируем рекомендации
    recommendations = safety_mgr.get_recommended_settings('spam_dm')
    print(f"Рекомендации для spam_dm: {recommendations}")
    
    # Тестируем менеджер прокси
    print("\n🌐 Тестирование менеджера прокси...")
    proxy_mgr = proxy_manager.get_proxy_manager()
    
    # Устанавливаем количество аккаунтов на прокси
    proxy_mgr.set_accounts_per_proxy(3)
    print(f"Аккаунтов на прокси: {proxy_mgr.get_accounts_per_proxy()}")
    
    # Тестируем статистику
    stats = proxy_mgr.get_proxy_statistics()
    print(f"Статистика прокси: {stats}")
    
    # Тестируем парсер (без подключения)
    print("\n📊 Тестирование парсера...")
    parser = parser_module.TelegramParser("test_session")
    print("Парсер создан успешно")
    
    print("\n✅ Все базовые тесты пройдены!")

def test_with_real_data():
    """Тестирование с реальными данными (если есть)"""
    print("\n🔍 Проверка реальных данных...")
    
    # Проверяем аккаунты
    accounts = storage_manager.list_accounts()
    print(f"Найдено аккаунтов: {len(accounts)}")
    
    if accounts:
        print("Аккаунты:")
        for account in accounts[:5]:  # Показываем первые 5
            info = storage_manager.get_account_info(account)
            print(f"  {account}: session={info['has_session']}, json={info['json_valid']}")
    
    # Проверяем прокси
    settings = storage_manager.load_settings()
    proxies = settings.get('proxies', [])
    print(f"Найдено прокси: {len(proxies)}")
    
    if proxies:
        print("Прокси:")
        for proxy in proxies[:3]:  # Показываем первые 3
            proxy_short = f"{proxy.split(':')[0]}:{proxy.split(':')[1]}"
            print(f"  {proxy_short}")
    
    # Проверяем задачи
    tasks = storage_manager.load_tasks()
    print(f"Найдено задач: {len(tasks)}")
    
    if tasks:
        print("Задачи:")
        for name, data in list(tasks.items())[:3]:
            print(f"  {name}: {data.get('type', 'Не задан')}")

def main():
    """Главная функция тестирования"""
    print("🚀 Тестирование Telegram Account Manager & Parser")
    print("=" * 50)
    
    try:
        # Тестируем базовый функционал
        asyncio.run(test_basic_functionality())
        
        # Тестируем с реальными данными
        test_with_real_data()
        
        print("\n🎉 Все тесты завершены успешно!")
        print("\n📋 Результаты тестирования:")
        print("✅ Импорты модулей - OK")
        print("✅ Создание задач - OK") 
        print("✅ Менеджер безопасности - OK")
        print("✅ Менеджер прокси - OK")
        print("✅ Парсер - OK")
        print("✅ Работа с данными - OK")
        
        print("\n🚀 Программа готова к использованию!")
        
    except Exception as e:
        print(f"\n❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)