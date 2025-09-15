# safety_manager.py

import asyncio
import random
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import storage_manager

class SafetyManager:
    """Менеджер безопасности для снижения рисков блокировок"""
    
    def __init__(self):
        self.account_activity = {}  # Отслеживание активности аккаунтов
        self.proxy_usage = {}       # Отслеживание использования прокси
        self.spam_statistics = {}   # Статистика спама для каждого аккаунта
        self.blocked_accounts = set()  # Заблокированные аккаунты
        
    def get_safe_delay(self, task_type: str, account_name: str) -> int:
        """Получение безопасной задержки с учетом истории аккаунта"""
        base_delays = {
            'spam_dm': (120, 300),      # 2-5 минут для ЛС
            'spam_dm_existing': (90, 180),  # 1.5-3 минуты для существующих ЛС
            'spam_chats': (30, 90),     # 30-90 сек для чатов
            'spam_channels': (45, 120), # 45-120 сек для каналов
            'spam_both': (30, 90),      # 30-90 сек для смешанного
            'join_chats': (20, 60),     # 20-60 сек для вступления
            'create_channel': (60, 180), # 1-3 минуты для создания каналов
        }
        
        min_delay, max_delay = base_delays.get(task_type, (30, 90))
        
        # Увеличиваем задержку если аккаунт был активен недавно
        if account_name in self.account_activity:
            last_activity = self.account_activity[account_name]
            time_since_last = time.time() - last_activity
            
            if time_since_last < 300:  # Если активность была менее 5 минут назад
                min_delay = int(min_delay * 1.5)
                max_delay = int(max_delay * 1.5)
        
        # Увеличиваем задержку если у аккаунта много активности
        spam_count = self.spam_statistics.get(account_name, {}).get('today_count', 0)
        if spam_count > 50:  # Если уже отправлено много сообщений сегодня
            min_delay = int(min_delay * 2)
            max_delay = int(max_delay * 2)
        
        return random.randint(min_delay, max_delay)
    
    def record_activity(self, account_name: str, activity_type: str, success: bool = True):
        """Записываем активность аккаунта"""
        current_time = time.time()
        today = datetime.now().date()
        
        # Записываем последнюю активность
        self.account_activity[account_name] = current_time
        
        # Статистика спама
        if account_name not in self.spam_statistics:
            self.spam_statistics[account_name] = {
                'today_count': 0,
                'last_reset': today,
                'total_sent': 0,
                'errors_count': 0,
                'last_error': None
            }
        
        stats = self.spam_statistics[account_name]
        
        # Сброс счетчика если новый день
        if stats['last_reset'] != today:
            stats['today_count'] = 0
            stats['last_reset'] = today
        
        if success:
            stats['today_count'] += 1
            stats['total_sent'] += 1
        else:
            stats['errors_count'] += 1
            stats['last_error'] = current_time
    
    def is_account_safe_to_use(self, account_name: str, task_type: str) -> Tuple[bool, str]:
        """Проверка безопасности использования аккаунта"""
        if account_name in self.blocked_accounts:
            return False, "Аккаунт заблокирован ранее"
        
        if account_name not in self.spam_statistics:
            return True, "Новый аккаунт"
        
        stats = self.spam_statistics[account_name]
        today = datetime.now().date()
        
        # Проверяем дневной лимит
        daily_limits = {
            'spam_dm': 20,          # Очень низкий лимит для ЛС
            'spam_dm_existing': 30, # Чуть выше для существующих ЛС
            'spam_chats': 100,      # Средний лимит для чатов
            'spam_channels': 80,    # Средний лимит для каналов
            'spam_both': 100,       # Средний лимит для смешанного
        }
        
        limit = daily_limits.get(task_type, 50)
        
        if stats['today_count'] >= limit:
            return False, f"Превышен дневной лимит ({stats['today_count']}/{limit})"
        
        # Проверяем количество ошибок
        if stats['errors_count'] > 5:
            if stats['last_error'] and (time.time() - stats['last_error']) < 3600:  # Ошибки в последний час
                return False, "Слишком много ошибок в последний час"
        
        # Проверяем частоту использования
        if account_name in self.account_activity:
            last_activity = self.account_activity[account_name]
            if (time.time() - last_activity) < 60:  # Использовался менее минуты назад
                return False, "Аккаунт использовался слишком недавно"
        
        return True, "Безопасно"
    
    def get_recommended_settings(self, task_type: str) -> Dict:
        """Получение рекомендуемых настроек безопасности"""
        recommendations = {
            'spam_dm': {
                'max_workers': 1,
                'delay_min': 120,
                'delay_max': 300,
                'daily_limit': 20,
                'warning': "🚨 ВЫСОКИЙ РИСК! Используйте только запасные аккаунты!"
            },
            'spam_dm_existing': {
                'max_workers': 2,
                'delay_min': 90,
                'delay_max': 180,
                'daily_limit': 30,
                'warning': "⚠️ Средний риск. Мониторьте логи на ошибки."
            },
            'spam_chats': {
                'max_workers': 3,
                'delay_min': 30,
                'delay_max': 90,
                'daily_limit': 100,
                'warning': "✅ Относительно безопасно при соблюдении интервалов."
            },
            'spam_channels': {
                'max_workers': 3,
                'delay_min': 45,
                'delay_max': 120,
                'daily_limit': 80,
                'warning': "✅ Безопасно для каналов с комментариями."
            },
            'spam_both': {
                'max_workers': 3,
                'delay_min': 30,
                'delay_max': 90,
                'daily_limit': 100,
                'warning': "✅ Универсальный режим с умеренными рисками."
            }
        }
        
        return recommendations.get(task_type, {
            'max_workers': 5,
            'delay_min': 30,
            'delay_max': 90,
            'daily_limit': 50,
            'warning': "ℹ️ Стандартные настройки безопасности."
        })
    
    def mark_account_blocked(self, account_name: str, reason: str):
        """Отметить аккаунт как заблокированный"""
        self.blocked_accounts.add(account_name)
        
        # Обновляем статус в базе данных
        statuses = storage_manager.load_account_statuses()
        if 'spamblock' in reason.lower():
            statuses[account_name] = 'spamblock_temporary' if 'temporary' in reason.lower() else 'spamblock_permanent'
        elif 'frozen' in reason.lower() or 'tos' in reason.lower():
            statuses[account_name] = 'frozen'
        else:
            statuses[account_name] = 'invalid'
        
        storage_manager.save_account_statuses(statuses)
    
    def get_proxy_distribution(self, accounts: List[str], accounts_per_proxy: int = 3) -> Dict:
        """Распределение аккаунтов по прокси"""
        settings = storage_manager.load_settings()
        proxies = settings.get('proxies', [])
        
        if not proxies:
            return {}
        
        # Фильтруем только рабочие прокси
        proxy_statuses = settings.get('proxy_statuses', {})
        working_proxies = [p for p in proxies if proxy_statuses.get(p, {}).get('status') == 'working']
        
        if not working_proxies:
            working_proxies = proxies  # Если нет данных о статусе, используем все
        
        distribution = {}
        proxy_index = 0
        
        for i, account in enumerate(accounts):
            if i % accounts_per_proxy == 0:
                proxy_index = (proxy_index + 1) % len(working_proxies)
            
            proxy = working_proxies[proxy_index]
            if proxy not in distribution:
                distribution[proxy] = []
            distribution[proxy].append(account)
        
        return distribution
    
    def validate_task_safety(self, task_name: str, task_data: Dict) -> Tuple[bool, str]:
        """Валидация безопасности задачи перед запуском"""
        task_type = task_data.get('type', '')
        accounts = task_data.get('accounts', [])
        settings = task_data.get('settings', {})
        
        if not accounts:
            return False, "Нет привязанных аккаунтов"
        
        # Проверяем каждый аккаунт
        unsafe_accounts = []
        for account in accounts:
            is_safe, reason = self.is_account_safe_to_use(account, task_type)
            if not is_safe:
                unsafe_accounts.append(f"{account}: {reason}")
        
        if unsafe_accounts:
            return False, f"Небезопасные аккаунты:\n" + "\n".join(unsafe_accounts[:5])
        
        # Проверяем настройки задачи
        recommendations = self.get_recommended_settings(task_type)
        
        workers = settings.get('concurrent_workers', 5)
        if workers > recommendations.get('max_workers', 5):
            return False, f"Слишком много воркеров ({workers}). Рекомендуется: {recommendations['max_workers']}"
        
        interval = settings.get('broadcast_interval', [30, 90])
        if len(interval) >= 2:
            if interval[0] < recommendations.get('delay_min', 30):
                return False, f"Слишком маленький интервал ({interval[0]}с). Минимум: {recommendations['delay_min']}с"
        
        # Специальная проверка для спама по ЛС
        if task_type in ['spam_dm', 'spam_dm_existing']:
            if not settings.get('dm_spam_warning_accepted', False):
                return False, "Не принято предупреждение о рисках спама по ЛС"
        
        return True, "Задача безопасна для запуска"

# Глобальный экземпляр менеджера безопасности
_safety_manager = None

def get_safety_manager() -> SafetyManager:
    """Получение глобального экземпляра SafetyManager"""
    global _safety_manager
    if _safety_manager is None:
        _safety_manager = SafetyManager()
    return _safety_manager