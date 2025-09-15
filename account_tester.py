# account_tester.py

import asyncio
import os
import json
from typing import Dict, List, Optional, Callable
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, AuthKeyUnregisteredError, UserDeactivatedBanError
import storage_manager

class AccountTester:
    """Класс для тестирования подключения к Telegram аккаунтам"""
    
    def __init__(self, progress_callback: Optional[Callable] = None):
        self.progress_callback = progress_callback
    
    async def log(self, message: str):
        """Логирование с callback"""
        if self.progress_callback:
            await self.progress_callback(message)
        else:
            print(message)
    
    async def test_single_account(self, session_name: str, use_proxy: bool = True) -> Dict:
        """Тестирование одного аккаунта"""
        result = {
            'session_name': session_name,
            'success': False,
            'error': None,
            'user_info': None,
            'proxy_used': None,
            'connection_time': 0
        }
        
        start_time = asyncio.get_event_loop().time()
        client = None
        
        try:
            await self.log(f"🧪 Тестирую аккаунт: {session_name}")
            
            # Получаем информацию об аккаунте
            account_info = storage_manager.get_account_info(session_name)
            
            if not account_info['has_session']:
                result['error'] = "Отсутствует файл сессии"
                return result
            
            if not account_info['json_valid']:
                result['error'] = f"Некорректный JSON: {account_info['json_error']}"
                return result
            
            # Загружаем данные JSON
            json_path = os.path.join(storage_manager.SESSIONS_DIR, f"{session_name}.json")
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            api_id = data.get('api_id') or data.get('app_id')
            api_hash = data.get('api_hash') or data.get('app_hash')
            two_fa = data.get('twoFA')
            
            # Настройка прокси
            proxy_dict = None
            if use_proxy:
                settings = storage_manager.load_settings()
                proxies = settings.get('proxies', [])
                if proxies:
                    # Берем случайный прокси
                    import random
                    proxy_str = random.choice(proxies)
                    p = proxy_str.split(':')
                    if len(p) == 4:
                        proxy_dict = {
                            'proxy_type': 'socks5',
                            'addr': p[0],
                            'port': int(p[1]),
                            'username': p[2],
                            'password': p[3]
                        }
                        result['proxy_used'] = f"{p[0]}:{p[1]}"
            
            # Параметры устройства
            device_model = data.get('device_model') or data.get('device') or 'PC'
            system_version = data.get('system_version') or data.get('sdk') or 'Windows 10'
            app_version = data.get('app_version', '4.8.1 x64')
            lang_code = data.get('lang_code') or 'en'
            system_lang_code = data.get('system_lang_code') or 'en-US'
            
            # Создаем клиент
            client = TelegramClient(
                os.path.join(storage_manager.SESSIONS_DIR, session_name),
                int(api_id),
                api_hash,
                device_model=device_model,
                system_version=system_version,
                app_version=app_version,
                lang_code=lang_code,
                system_lang_code=system_lang_code,
                proxy=proxy_dict,
                timeout=15,
                catch_up=False
            )
            
            # Подключаемся
            await client.connect()
            
            # Проверяем авторизацию
            if not await client.is_user_authorized():
                if two_fa:
                    await client.sign_in(password=two_fa)
                else:
                    result['error'] = "Требуется 2FA пароль"
                    return result
            
            # Получаем информацию о пользователе
            me = await client.get_me()
            result['user_info'] = {
                'id': me.id,
                'first_name': me.first_name or '',
                'last_name': me.last_name or '',
                'username': me.username or '',
                'phone': me.phone or '',
                'is_verified': me.verified,
                'is_premium': getattr(me, 'premium', False)
            }
            
            result['success'] = True
            result['connection_time'] = round(asyncio.get_event_loop().time() - start_time, 2)
            
            await self.log(f"✅ {session_name}: Успешно ({result['connection_time']}с)")
            
        except (UserDeactivatedBanError, AuthKeyUnregisteredError):
            result['error'] = "Аккаунт забанен или удален"
            await self.log(f"❌ {session_name}: Аккаунт забанен")
        except SessionPasswordNeededError:
            result['error'] = "Требуется 2FA пароль"
            await self.log(f"⚠️ {session_name}: Нужен 2FA")
        except (asyncio.TimeoutError, OSError):
            result['error'] = "Таймаут подключения (проблема с прокси?)"
            await self.log(f"⏰ {session_name}: Таймаут")
        except Exception as e:
            result['error'] = f"Ошибка: {type(e).__name__}: {e}"
            await self.log(f"❌ {session_name}: {result['error']}")
        finally:
            if client and client.is_connected():
                await client.disconnect()
        
        return result
    
    async def test_multiple_accounts(self, session_names: List[str], use_proxy: bool = True, 
                                   max_concurrent: int = 5) -> List[Dict]:
        """Тестирование нескольких аккаунтов параллельно"""
        await self.log(f"🚀 Начинаю тестирование {len(session_names)} аккаунтов")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def test_with_semaphore(session_name):
            async with semaphore:
                return await self.test_single_account(session_name, use_proxy)
        
        # Запускаем тестирование параллельно
        tasks = [test_with_semaphore(name) for name in session_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обрабатываем исключения
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append({
                    'session_name': session_names[i],
                    'success': False,
                    'error': f"Критическая ошибка: {result}",
                    'user_info': None,
                    'proxy_used': None,
                    'connection_time': 0
                })
            else:
                final_results.append(result)
        
        # Статистика
        successful = sum(1 for r in final_results if r['success'])
        failed = len(final_results) - successful
        
        await self.log(f"📊 Тестирование завершено: {successful} успешно, {failed} ошибок")
        
        return final_results
    
    async def test_proxy_connection(self, proxy_str: str, test_account: str = None) -> Dict:
        """Тестирование прокси с помощью тестового аккаунта"""
        result = {
            'proxy': proxy_str,
            'success': False,
            'error': None,
            'response_time': 0
        }
        
        try:
            p = proxy_str.split(':')
            if len(p) != 4:
                result['error'] = "Неверный формат прокси"
                return result
            
            # Тестируем через HTTP запрос
            import aiohttp
            from aiohttp_proxy import ProxyConnector
            
            start_time = asyncio.get_event_loop().time()
            
            connector = ProxyConnector.from_url(f'socks5://{p[2]}:{p[3]}@{p[0]}:{p[1]}')
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get('http://httpbin.org/ip', timeout=10) as response:
                    if response.status == 200:
                        result['success'] = True
                        result['response_time'] = round(asyncio.get_event_loop().time() - start_time, 2)
                        
                        # Если есть тестовый аккаунт, проверяем через Telegram
                        if test_account:
                            await self.log(f"🔍 Тестирую прокси {p[0]}:{p[1]} через Telegram...")
                            telegram_result = await self.test_single_account(test_account, use_proxy=True)
                            if not telegram_result['success']:
                                result['success'] = False
                                result['error'] = f"Прокси работает, но не с Telegram: {telegram_result['error']}"
                    else:
                        result['error'] = f"HTTP {response.status}"
        
        except asyncio.TimeoutError:
            result['error'] = "Таймаут"
        except Exception as e:
            result['error'] = f"{type(e).__name__}: {e}"
        
        return result

# Интеграция с существующей системой
async def test_account_connection(session_name: str, progress_callback=None) -> Dict:
    """Быстрая функция для тестирования одного аккаунта"""
    tester = AccountTester(progress_callback)
    return await tester.test_single_account(session_name)

async def test_all_accounts(progress_callback=None) -> List[Dict]:
    """Тестирование всех аккаунтов в системе"""
    accounts = storage_manager.list_accounts()
    if not accounts:
        if progress_callback:
            await progress_callback("❌ Нет аккаунтов для тестирования")
        return []
    
    tester = AccountTester(progress_callback)
    return await tester.test_multiple_accounts(accounts)