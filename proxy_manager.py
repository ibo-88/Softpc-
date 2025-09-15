# proxy_manager.py

import asyncio
import random
import time
from typing import Dict, List, Optional, Tuple
import aiohttp
from aiohttp_proxy import ProxyConnector
import storage_manager

class ProxyManager:
    """Менеджер прокси с распределением аккаунтов"""
    
    def __init__(self):
        self.proxy_pools = {}  # proxy_str -> queue аккаунтов
        self.proxy_stats = {}  # Статистика использования прокси
        self.accounts_per_proxy = 3  # По умолчанию 3 аккаунта на прокси
        
    def set_accounts_per_proxy(self, count: int):
        """Установка количества аккаунтов на прокси"""
        self.accounts_per_proxy = max(1, min(count, 10))  # От 1 до 10
    
    def get_accounts_per_proxy(self) -> int:
        """Получение текущего количества аккаунтов на прокси"""
        return self.accounts_per_proxy
    
    async def test_proxy(self, proxy_str: str) -> Dict:
        """Тестирование одного прокси"""
        result = {
            'proxy': proxy_str,
            'success': False,
            'response_time': 0,
            'error': None,
            'country': 'N/A'
        }
        
        try:
            parts = proxy_str.split(':')
            if len(parts) != 4:
                result['error'] = "Неверный формат"
                return result
            
            start_time = time.time()
            
            connector = ProxyConnector.from_url(f'socks5://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}')
            async with aiohttp.ClientSession(connector=connector) as session:
                # Тестируем скорость
                async with session.get('http://httpbin.org/ip', timeout=15) as response:
                    if response.status == 200:
                        result['response_time'] = round(time.time() - start_time, 2)
                        
                        # Получаем страну
                        try:
                            async with session.get('http://ip-api.com/json/?fields=countryCode', timeout=10) as geo_response:
                                if geo_response.status == 200:
                                    geo_data = await geo_response.json()
                                    result['country'] = geo_data.get('countryCode', 'N/A')
                        except:
                            pass
                        
                        result['success'] = True
                    else:
                        result['error'] = f"HTTP {response.status}"
        
        except asyncio.TimeoutError:
            result['error'] = "Таймаут"
        except Exception as e:
            result['error'] = f"{type(e).__name__}"
        
        return result
    
    async def test_all_proxies(self, progress_callback=None) -> Dict:
        """Тестирование всех прокси с подробной статистикой"""
        settings = storage_manager.load_settings()
        proxies = settings.get('proxies', [])
        
        if not proxies:
            return {'working': [], 'not_working': [], 'total': 0}
        
        if progress_callback:
            await progress_callback(f"🔍 Тестирую {len(proxies)} прокси...")
        
        # Тестируем параллельно с ограничением
        semaphore = asyncio.Semaphore(20)
        
        async def test_with_semaphore(proxy):
            async with semaphore:
                result = await self.test_proxy(proxy)
                if progress_callback:
                    status = "✅" if result['success'] else "❌"
                    await progress_callback(f"{status} {proxy.split(':')[0]}:{proxy.split(':')[1]} ({result.get('response_time', 0)}s)")
                return result
        
        tasks = [test_with_semaphore(proxy) for proxy in proxies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обрабатываем результаты
        working = []
        not_working = []
        proxy_statuses = {}
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                proxy_statuses[proxies[i]] = {
                    'status': 'not_working',
                    'error': str(result),
                    'country': 'N/A'
                }
                not_working.append(proxies[i])
            else:
                if result['success']:
                    working.append(proxies[i])
                    proxy_statuses[proxies[i]] = {
                        'status': 'working',
                        'response_time': result['response_time'],
                        'country': result['country']
                    }
                else:
                    not_working.append(proxies[i])
                    proxy_statuses[proxies[i]] = {
                        'status': 'not_working',
                        'error': result['error'],
                        'country': 'N/A'
                    }
        
        # Сохраняем статусы
        storage_manager.save_proxy_statuses(proxy_statuses)
        
        if progress_callback:
            await progress_callback(f"📊 Результат: {len(working)} работает, {len(not_working)} не работает")
        
        return {
            'working': working,
            'not_working': not_working,
            'total': len(proxies),
            'statuses': proxy_statuses
        }
    
    def create_proxy_queues(self, accounts: List[str]) -> Dict[str, asyncio.Queue]:
        """Создание очередей прокси с распределением аккаунтов"""
        settings = storage_manager.load_settings()
        proxies = settings.get('proxies', [])
        proxy_statuses = settings.get('proxy_statuses', {})
        
        # Фильтруем только рабочие прокси
        working_proxies = [p for p in proxies if proxy_statuses.get(p, {}).get('status') == 'working']
        
        if not working_proxies:
            working_proxies = proxies  # Если нет данных о статусе, используем все
        
        if not working_proxies:
            return {}
        
        # Создаем распределение
        proxy_queues = {}
        accounts_distribution = {}
        
        # Распределяем аккаунты по прокси
        for i, account in enumerate(accounts):
            proxy_index = (i // self.accounts_per_proxy) % len(working_proxies)
            proxy = working_proxies[proxy_index]
            
            if proxy not in accounts_distribution:
                accounts_distribution[proxy] = []
            accounts_distribution[proxy].append(account)
        
        # Создаем очереди для каждого прокси
        for proxy, proxy_accounts in accounts_distribution.items():
            queue = asyncio.Queue()
            for _ in range(len(proxy_accounts) * 2):  # Добавляем прокси несколько раз
                queue.put_nowait(proxy)
            proxy_queues[proxy] = queue
        
        self.proxy_pools = accounts_distribution
        return proxy_queues
    
    def get_proxy_for_account(self, account_name: str) -> Optional[str]:
        """Получение прокси для конкретного аккаунта"""
        for proxy, accounts in self.proxy_pools.items():
            if account_name in accounts:
                return proxy
        return None
    
    def get_proxy_statistics(self) -> Dict:
        """Получение статистики использования прокси"""
        settings = storage_manager.load_settings()
        proxies = settings.get('proxies', [])
        proxy_statuses = settings.get('proxy_statuses', {})
        
        stats = {
            'total_proxies': len(proxies),
            'working_proxies': 0,
            'not_working_proxies': 0,
            'untested_proxies': 0,
            'accounts_per_proxy': self.accounts_per_proxy,
            'distribution': self.proxy_pools
        }
        
        for proxy in proxies:
            status = proxy_statuses.get(proxy, {}).get('status', 'untested')
            if status == 'working':
                stats['working_proxies'] += 1
            elif status == 'not_working':
                stats['not_working_proxies'] += 1
            else:
                stats['untested_proxies'] += 1
        
        return stats
    
    def remove_non_working_proxies(self) -> int:
        """Удаление нерабочих прокси"""
        settings = storage_manager.load_settings()
        proxies = settings.get('proxies', [])
        proxy_statuses = settings.get('proxy_statuses', {})
        
        working_proxies = []
        removed_count = 0
        
        for proxy in proxies:
            status = proxy_statuses.get(proxy, {}).get('status', 'untested')
            if status == 'working' or status == 'untested':
                working_proxies.append(proxy)
            else:
                removed_count += 1
        
        # Обновляем списки
        settings['proxies'] = working_proxies
        # Очищаем статусы удаленных прокси
        new_statuses = {p: s for p, s in proxy_statuses.items() if p in working_proxies}
        settings['proxy_statuses'] = new_statuses
        
        storage_manager.save_settings(settings)
        return removed_count

# Глобальный экземпляр менеджера прокси
_proxy_manager = None

def get_proxy_manager() -> ProxyManager:
    """Получение глобального экземпляра ProxyManager"""
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager()
    return _proxy_manager