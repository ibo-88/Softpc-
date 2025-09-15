# core_manager.py

import asyncio
import threading
from typing import Dict, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
import storage_manager
import telegram_worker
import parser_module

class CoreManager:
    """Основной менеджер для управления задачами без Telegram бота"""
    
    def __init__(self, progress_callback: Optional[Callable] = None):
        self.progress_callback = progress_callback
        self.active_tasks: Dict[str, Dict] = {}
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.loop = None
        self.loop_thread = None
        self.start_event_loop()
    
    def start_event_loop(self):
        """Запуск event loop в отдельном потоке"""
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
        
        self.loop_thread = threading.Thread(target=run_loop, daemon=True)
        self.loop_thread.start()
        
        # Ждем инициализации loop
        while self.loop is None:
            threading.Event().wait(0.1)
    
    def log(self, message: str):
        """Логирование с callback"""
        if self.progress_callback:
            self.progress_callback(message)
        else:
            print(message)
    
    def run_async_task(self, coro):
        """Запуск асинхронной задачи в event loop"""
        if self.loop and not self.loop.is_closed():
            future = asyncio.run_coroutine_threadsafe(coro, self.loop)
            return future
        return None
    
    def check_account_async(self, account_name: str) -> threading.Thread:
        """Асинхронная проверка аккаунта"""
        def check_account():
            async def _check():
                try:
                    # Создаем callback для прогресса
                    async def progress_callback(text):
                        self.log(text)
                    
                    # Создаем воркера
                    proxy_queue = asyncio.Queue()
                    file_lock = asyncio.Lock()
                    settings_lock = asyncio.Lock()
                    cancel_event = asyncio.Event()
                    semaphore = asyncio.Semaphore(1)
                    
                    # Фиктивные данные задачи для проверки
                    task_data = {
                        'type': 'check_all',
                        'settings': {}
                    }
                    
                    worker = telegram_worker.TelethonWorker(
                        account_name, proxy_queue, file_lock, settings_lock,
                        progress_callback, cancel_event, semaphore, 
                        'account_check', task_data
                    )
                    
                    # Запускаем проверку
                    await worker.run_task(
                        worker.task_check_account,
                        change_name=False,
                        change_avatar=False,
                        change_lastname=False,
                        perform_spam_check=True
                    )
                    
                except Exception as e:
                    self.log(f"Ошибка проверки аккаунта {account_name}: {e}")
            
            # Запускаем в event loop
            future = self.run_async_task(_check())
            if future:
                future.result()  # Ждем завершения
        
        thread = threading.Thread(target=check_account)
        thread.start()
        return thread
    
    def check_all_accounts_async(self, accounts: List[str]) -> threading.Thread:
        """Массовая проверка аккаунтов"""
        def check_all():
            async def _check_all():
                try:
                    self.log(f"Начинаю проверку {len(accounts)} аккаунтов...")
                    
                    # Создаем общие ресурсы
                    global_settings = storage_manager.load_settings()
                    proxies = global_settings.get('proxies', [])
                    proxy_queue = asyncio.Queue()
                    for p in proxies:
                        proxy_queue.put_nowait(p)
                    
                    file_lock = asyncio.Lock()
                    settings_lock = asyncio.Lock()
                    cancel_event = asyncio.Event()
                    semaphore = asyncio.Semaphore(5)  # Ограничиваем одновременные проверки
                    
                    async def progress_callback(text):
                        self.log(text)
                    
                    # Данные задачи
                    task_data = {
                        'type': 'check_all',
                        'settings': {}
                    }
                    
                    # Создаем задачи для каждого аккаунта
                    tasks = []
                    for account_name in accounts:
                        worker = telegram_worker.TelethonWorker(
                            account_name, proxy_queue, file_lock, settings_lock,
                            progress_callback, cancel_event, semaphore,
                            'mass_check', task_data
                        )
                        
                        task = worker.run_task(
                            worker.task_check_account,
                            change_name=False,
                            change_avatar=False,
                            change_lastname=False,
                            perform_spam_check=True
                        )
                        tasks.append(task)
                    
                    # Запускаем все задачи параллельно
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Обновляем статусы аккаунтов
                    self.log("Проверка завершена. Обновляю статусы аккаунтов...")
                    
                except Exception as e:
                    self.log(f"Ошибка массовой проверки: {e}")
            
            future = self.run_async_task(_check_all())
            if future:
                future.result()
        
        thread = threading.Thread(target=check_all)
        thread.start()
        return thread
    
    def start_parsing_async(self, account_name: str, parse_type: str, 
                          target: str, options: Dict) -> threading.Thread:
        """Асинхронный запуск парсинга"""
        def parse():
            async def _parse():
                try:
                    self.log(f"Начинаю парсинг: {parse_type} из {target}")
                    
                    async def progress_callback(text):
                        self.log(text)
                    
                    # Создаем очередь прокси
                    global_settings = storage_manager.load_settings()
                    proxies = global_settings.get('proxies', [])
                    proxy_queue = asyncio.Queue()
                    for p in proxies:
                        proxy_queue.put_nowait(p)
                    
                    # Создаем парсер с прокси
                    parser = parser_module.TelegramParser(account_name, progress_callback, proxy_queue)
                    
                    if not await parser.connect():
                        self.log("Не удалось подключиться для парсинга")
                        return
                    
                    data = []
                    
                    if parse_type == "members":
                        limit = options.get('limit', 10000)
                        data = await parser.parse_group_members(target, limit)
                    elif parse_type == "usernames":
                        limit = options.get('limit', 10000)
                        data = await parser.parse_usernames_only(target, limit)
                    elif parse_type == "multiple_usernames":
                        # target должен содержать список чатов
                        chat_list = [chat.strip() for chat in target.split('\n') if chat.strip()]
                        limit_per_chat = options.get('limit_per_chat', 5000)
                        data = await parser.parse_multiple_chats_usernames(chat_list, limit_per_chat)
                    elif parse_type == "messages":
                        limit = options.get('limit', 1000)
                        data = await parser.parse_chat_messages(target, limit)
                    elif parse_type == "dialogs":
                        data = await parser.get_user_dialogs()
                    
                    # Экспорт данных
                    if data and options.get('export_format'):
                        from datetime import datetime
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        safe_target = target.replace('@', '').replace('/', '_').replace(':', '_')[:50]  # Ограничиваем длину
                        filename = f"{parse_type}_{safe_target}_{timestamp}"
                        
                        if options['export_format'] == 'csv':
                            await parser.export_to_csv(data, f"{filename}.csv")
                        elif options['export_format'] == 'json':
                            await parser.export_to_json(data, f"{filename}.json")
                        elif options['export_format'] == 'txt' and parse_type in ['usernames', 'multiple_usernames']:
                            await parser.export_usernames_to_txt(data, f"{filename}.txt")
                    
                    await parser.disconnect()
                    self.log(f"Парсинг завершен. Получено записей: {len(data)}")
                    
                    return data
                    
                except Exception as e:
                    self.log(f"Ошибка парсинга: {e}")
                    return []
            
            future = self.run_async_task(_parse())
            if future:
                return future.result()
            return []
        
        thread = threading.Thread(target=parse)
        thread.start()
        return thread
    
    def execute_task_async(self, task_name: str) -> threading.Thread:
        """Асинхронное выполнение задачи"""
        def execute():
            async def _execute():
                try:
                    task_data = storage_manager.get_task(task_name)
                    if not task_data:
                        self.log(f"Задача {task_name} не найдена")
                        return
                    
                    if not task_data.get('accounts'):
                        self.log(f"К задаче {task_name} не привязаны аккаунты")
                        return
                    
                    self.log(f"Запускаю задачу: {task_name}")
                    
                    # Создаем общие ресурсы
                    global_settings = storage_manager.load_settings()
                    proxies = global_settings.get('proxies', [])
                    proxy_queue = asyncio.Queue()
                    for p in proxies:
                        proxy_queue.put_nowait(p)
                    
                    file_lock = asyncio.Lock()
                    settings_lock = asyncio.Lock()
                    cancel_event = asyncio.Event()
                    
                    # Сохраняем cancel_event для возможности остановки
                    self.active_tasks[task_name] = {
                        'cancel_event': cancel_event,
                        'status': 'running'
                    }
                    
                    task_worker_limit = task_data.get('settings', {}).get('concurrent_workers', 5)
                    semaphore = asyncio.Semaphore(task_worker_limit)
                    
                    async def progress_callback(text):
                        self.log(text)
                    
                    # Создаем воркеров для каждого аккаунта
                    tasks = []
                    accounts = task_data['accounts']
                    task_type = task_data['type']
                    
                    # Общая очередь для задач типа join_chats
                    shared_work_queue = asyncio.Queue()
                    if task_type == 'join_chats':
                        all_chats = storage_manager.read_task_text_file_lines(task_name, 'chats')
                        for chat in all_chats:
                            await shared_work_queue.put(chat)
                    
                    for account_name in accounts:
                        worker = telegram_worker.TelethonWorker(
                            account_name, proxy_queue, file_lock, settings_lock,
                            progress_callback, cancel_event, semaphore,
                            task_name, task_data
                        )
                        
                        # Определяем корутину в зависимости от типа задачи
                        coro = None
                        task_parts = task_type.split(':')
                        base_task = task_parts[0]
                        
                        if base_task == 'check_all':
                            coro = worker.run_task(worker.task_check_account, 
                                                 change_name=False, change_avatar=False, 
                                                 change_lastname=False, perform_spam_check=True)
                        elif base_task == 'change_profile':
                            change = task_parts[1] if len(task_parts) > 1 else 'name'
                            if change == 'bio':
                                coro = worker.run_task(worker.task_change_bio)
                            else:
                                coro = worker.run_task(worker.task_check_account,
                                                     change_name=(change in ['name', 'name_last', 'name_avatar', 'all']),
                                                     change_lastname=(change in ['lastname', 'name_last', 'last_avatar', 'all']),
                                                     change_avatar=(change in ['avatar', 'name_avatar', 'last_avatar', 'all']),
                                                     perform_spam_check=False)
                        elif base_task == 'create_channel':
                            coro = worker.run_task(worker.task_create_channel)
                        elif base_task == 'update_channel_design':
                            coro = worker.run_task(worker.task_update_channel_design)
                        elif base_task == 'join_chats':
                            coro = worker.run_task(worker.task_join_chats, work_queue=shared_work_queue)
                        elif base_task == 'start_broadcast':
                            coro = worker.run_task(worker.task_autobroadcast)
                        elif base_task in ['spam_chats', 'spam_channels', 'spam_both']:
                            coro = worker.run_task(worker.task_advanced_spam)
                        elif base_task in ['spam_dm', 'spam_dm_existing']:
                            coro = worker.run_task(worker.task_dm_spam)
                        elif base_task == 'delete_avatars':
                            coro = worker.run_task(worker.task_delete_avatars)
                        elif base_task == 'delete_lastnames':
                            coro = worker.run_task(worker.task_delete_lastnames)
                        elif base_task == 'set_2fa':
                            password = task_data.get('settings', {}).get('two_fa_password')
                            coro = worker.run_task(worker.task_set_2fa, password=password)
                        elif base_task == 'remove_2fa':
                            password = task_data.get('settings', {}).get('two_fa_password')
                            coro = worker.run_task(worker.task_remove_2fa, password=password)
                        elif base_task == 'terminate_sessions':
                            coro = worker.run_task(worker.task_terminate_sessions)
                        elif base_task == 'reauthorize':
                            coro = worker.run_task(worker.task_reauthorize_account)
                        elif base_task == 'clean_account':
                            coro = worker.run_task(worker.task_clean_account)
                        
                        if coro:
                            tasks.append(coro)
                    
                    # Запускаем все задачи
                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Обновляем статус задачи
                    if task_name in self.active_tasks:
                        del self.active_tasks[task_name]
                    
                    # Обновляем статусы аккаунтов для задачи check_all
                    if task_type == 'check_all':
                        self.log("Обновляю статусы аккаунтов...")
                        # TODO: Реализовать обновление статусов
                    
                    self.log(f"Задача {task_name} завершена")
                    
                except Exception as e:
                    self.log(f"Ошибка выполнения задачи {task_name}: {e}")
                    if task_name in self.active_tasks:
                        del self.active_tasks[task_name]
            
            future = self.run_async_task(_execute())
            if future:
                future.result()
        
        thread = threading.Thread(target=execute)
        thread.start()
        return thread
    
    def stop_task(self, task_name: str):
        """Остановка задачи"""
        if task_name in self.active_tasks:
            self.active_tasks[task_name]['cancel_event'].set()
            self.log(f"Отправлен сигнал остановки для задачи: {task_name}")
        else:
            self.log(f"Задача {task_name} не активна")
    
    def get_active_tasks(self) -> List[str]:
        """Получение списка активных задач"""
        return list(self.active_tasks.keys())
    
    def is_task_active(self, task_name: str) -> bool:
        """Проверка активности задачи"""
        return task_name in self.active_tasks
    
    def shutdown(self):
        """Завершение работы менеджера"""
        # Останавливаем все активные задачи
        for task_name in list(self.active_tasks.keys()):
            self.stop_task(task_name)
        
        # Останавливаем event loop
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.loop.stop)
        
        # Завершаем executor
        self.executor.shutdown(wait=True)
        
        self.log("CoreManager завершен")

# Глобальный экземпляр менеджера
_core_manager = None

def get_core_manager(progress_callback: Optional[Callable] = None) -> CoreManager:
    """Получение глобального экземпляра CoreManager"""
    global _core_manager
    if _core_manager is None:
        _core_manager = CoreManager(progress_callback)
    return _core_manager