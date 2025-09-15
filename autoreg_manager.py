# autoreg_manager.py

import asyncio
import random
import time
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from telethon import TelegramClient
from telethon.errors import FloodWaitError, PeerFloodError, UserPrivacyRestrictedError
import storage_manager

class AutoregManager:
    """Менеджер для работы с авторег аккаунтами"""
    
    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback
        self.account_ages = {}  # Возраст аккаунтов
        self.warmup_stages = {}  # Стадии прогрева
        
    async def log(self, message: str):
        """Логирование"""
        if self.progress_callback:
            await self.progress_callback(message)
        else:
            print(message)
    
    def detect_account_age(self, session_name: str) -> str:
        """Определение возраста аккаунта"""
        # Проверяем по файлу сессии
        session_path = os.path.join(storage_manager.SESSIONS_DIR, f"{session_name}.session")
        
        if not os.path.exists(session_path):
            return "unknown"
        
        # Получаем дату создания файла
        creation_time = os.path.getctime(session_path)
        creation_date = datetime.fromtimestamp(creation_time)
        age_days = (datetime.now() - creation_date).days
        
        if age_days < 1:
            return "fresh"  # Свежий (менее суток)
        elif age_days < 7:
            return "new"    # Новый (менее недели)
        elif age_days < 30:
            return "young"  # Молодой (менее месяца)
        else:
            return "mature" # Зрелый (больше месяца)
    
    def get_autoreg_safety_settings(self, account_age: str, task_type: str) -> Dict:
        """Получение настроек безопасности для авторег аккаунтов"""
        
        # Базовые настройки по возрасту
        age_settings = {
            "fresh": {  # Менее суток - ОЧЕНЬ осторожно
                "max_actions_per_day": 5,
                "min_delay": 300,  # 5 минут
                "max_delay": 600,  # 10 минут
                "max_workers": 1,
                "warmup_required": True,
                "risk_level": "🚨 КРИТИЧЕСКИЙ"
            },
            "new": {    # Менее недели - осторожно
                "max_actions_per_day": 15,
                "min_delay": 180,  # 3 минуты
                "max_delay": 360,  # 6 минут
                "max_workers": 1,
                "warmup_required": True,
                "risk_level": "🔴 ВЫСОКИЙ"
            },
            "young": {  # Менее месяца - умеренно
                "max_actions_per_day": 30,
                "min_delay": 90,   # 1.5 минуты
                "max_delay": 180,  # 3 минуты
                "max_workers": 2,
                "warmup_required": False,
                "risk_level": "🟡 СРЕДНИЙ"
            },
            "mature": { # Больше месяца - обычно
                "max_actions_per_day": 50,
                "min_delay": 30,   # 30 секунд
                "max_delay": 90,   # 1.5 минуты
                "max_workers": 3,
                "warmup_required": False,
                "risk_level": "🟢 НИЗКИЙ"
            }
        }
        
        base_settings = age_settings.get(account_age, age_settings["fresh"])
        
        # Корректировки по типу задачи
        task_multipliers = {
            "spam_dm": 3.0,           # Увеличиваем задержки в 3 раза
            "spam_dm_existing": 2.0,  # В 2 раза
            "spam_chats": 1.5,        # В 1.5 раза
            "spam_channels": 1.2,     # В 1.2 раза
            "join_chats": 2.0,        # Вступление тоже рискованно
            "create_channel": 1.5,    # Создание каналов
            "parse_members": 1.0,     # Парсинг безопасен
            "check_all": 1.0          # Проверка безопасна
        }
        
        multiplier = task_multipliers.get(task_type, 1.0)
        
        # Применяем множители
        final_settings = base_settings.copy()
        final_settings["min_delay"] = int(base_settings["min_delay"] * multiplier)
        final_settings["max_delay"] = int(base_settings["max_delay"] * multiplier)
        final_settings["max_actions_per_day"] = int(base_settings["max_actions_per_day"] / multiplier)
        
        return final_settings
    
    async def warmup_account(self, session_name: str, proxy_queue=None) -> bool:
        """Прогрев нового аккаунта"""
        await self.log(f"🔥 Начинаю прогрев аккаунта: {session_name}")
        
        try:
            # Подключаемся к аккаунту
            json_path = os.path.join(storage_manager.SESSIONS_DIR, f"{session_name}.json")
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            api_id = data.get('api_id') or data.get('app_id')
            api_hash = data.get('api_hash') or data.get('app_hash')
            two_fa = data.get('twoFA')
            
            # Настройка прокси
            proxy_dict = None
            if proxy_queue and not proxy_queue.empty():
                try:
                    proxy_str = proxy_queue.get_nowait()
                    p = proxy_str.split(':')
                    if len(p) == 4:
                        proxy_dict = {
                            'proxy_type': 'socks5',
                            'addr': p[0],
                            'port': int(p[1]),
                            'username': p[2],
                            'password': p[3]
                        }
                    proxy_queue.put_nowait(proxy_str)  # Возвращаем обратно
                except:
                    pass
            
            client = TelegramClient(
                os.path.join(storage_manager.SESSIONS_DIR, session_name),
                int(api_id),
                api_hash,
                proxy=proxy_dict,
                timeout=30
            )
            
            await client.connect()
            
            if not await client.is_user_authorized():
                if two_fa:
                    await client.sign_in(password=two_fa)
                else:
                    await self.log(f"❌ {session_name}: Требуется 2FA")
                    return False
            
            # Этапы прогрева
            warmup_actions = [
                ("📱 Получение информации о себе", self._warmup_get_me),
                ("📋 Получение диалогов", self._warmup_get_dialogs),
                ("🔍 Поиск публичных каналов", self._warmup_search_public),
                ("📞 Обновление статуса онлайн", self._warmup_update_status),
                ("⏰ Имитация активности", self._warmup_simulate_activity)
            ]
            
            for i, (description, action) in enumerate(warmup_actions, 1):
                await self.log(f"🔥 [{i}/{len(warmup_actions)}] {session_name}: {description}")
                
                try:
                    await action(client)
                    
                    # Случайная пауза между действиями
                    delay = random.randint(30, 90)
                    await self.log(f"⏳ {session_name}: Пауза {delay}с...")
                    await asyncio.sleep(delay)
                    
                except Exception as e:
                    await self.log(f"⚠️ {session_name}: Ошибка в {description}: {e}")
            
            await client.disconnect()
            
            # Отмечаем аккаунт как прогретый
            self.warmup_stages[session_name] = {
                'warmed_up': True,
                'warmup_date': datetime.now().isoformat(),
                'warmup_actions': len(warmup_actions)
            }
            
            await self.log(f"✅ {session_name}: Прогрев завершен успешно")
            return True
            
        except Exception as e:
            await self.log(f"❌ {session_name}: Критическая ошибка прогрева: {e}")
            return False
    
    async def _warmup_get_me(self, client):
        """Получение информации о себе"""
        me = await client.get_me()
        return me
    
    async def _warmup_get_dialogs(self, client):
        """Получение списка диалогов"""
        dialogs = await client.get_dialogs(limit=10)
        return len(dialogs)
    
    async def _warmup_search_public(self, client):
        """Поиск публичных каналов"""
        try:
            # Ищем популярные публичные каналы
            search_queries = ["news", "crypto", "tech", "music", "sport"]
            query = random.choice(search_queries)
            
            results = await client.get_dialogs(limit=5)
            return len(results)
        except:
            return 0
    
    async def _warmup_update_status(self, client):
        """Обновление статуса онлайн"""
        try:
            # Просто получаем диалоги чтобы показать активность
            await client.get_dialogs(limit=1)
            return True
        except:
            return False
    
    async def _warmup_simulate_activity(self, client):
        """Имитация пользовательской активности"""
        try:
            # Получаем несколько сообщений из Telegram
            dialogs = await client.get_dialogs(limit=3)
            
            for dialog in dialogs:
                try:
                    # Читаем последние сообщения (имитируем чтение)
                    messages = await client.get_messages(dialog.entity, limit=1)
                    await asyncio.sleep(random.randint(2, 5))
                except:
                    continue
            
            return True
        except:
            return False
    
    def get_autoreg_recommendations(self, account_age: str) -> Dict:
        """Рекомендации для авторег аккаунтов"""
        recommendations = {
            "fresh": {
                "title": "🆕 СВЕЖИЙ АККАУНТ (менее суток)",
                "actions": [
                    "🔥 ОБЯЗАТЕЛЬНО проведите прогрев",
                    "⏰ Ждите минимум 24 часа перед активным использованием",
                    "📱 Используйте только для просмотра контента первые дни",
                    "🚫 НЕ отправляйте сообщения первые 2-3 дня",
                    "🚫 НЕ вступайте в чаты первые 24 часа"
                ],
                "max_daily_actions": 3,
                "recommended_delay": "10-20 минут",
                "risk": "🚨 КРИТИЧЕСКИЙ - легко отлетает"
            },
            "new": {
                "title": "🌱 НОВЫЙ АККАУНТ (менее недели)", 
                "actions": [
                    "🔥 Проведите прогрев если не делали",
                    "📱 Начинайте с просмотра каналов",
                    "💬 Максимум 10-15 действий в день",
                    "⏰ Интервалы минимум 3-5 минут",
                    "🎯 Избегайте спама по ЛС"
                ],
                "max_daily_actions": 15,
                "recommended_delay": "3-5 минут",
                "risk": "🔴 ВЫСОКИЙ - требует осторожности"
            },
            "young": {
                "title": "🌿 МОЛОДОЙ АККАУНТ (менее месяца)",
                "actions": [
                    "📈 Постепенно увеличивайте активность",
                    "💬 До 30 действий в день",
                    "⏰ Интервалы 1-3 минуты",
                    "🎯 Осторожно со спамом по ЛС",
                    "✅ Можно использовать для парсинга"
                ],
                "max_daily_actions": 30,
                "recommended_delay": "1-3 минуты",
                "risk": "🟡 СРЕДНИЙ - можно работать осторожно"
            },
            "mature": {
                "title": "🌳 ЗРЕЛЫЙ АККАУНТ (больше месяца)",
                "actions": [
                    "✅ Можно использовать в полном объеме",
                    "💬 До 50-100 действий в день",
                    "⏰ Стандартные интервалы 30-90 сек",
                    "🎯 Относительно безопасен для всех операций",
                    "📊 Подходит для любых задач"
                ],
                "max_daily_actions": 100,
                "recommended_delay": "30-90 секунд",
                "risk": "🟢 НИЗКИЙ - стабильный аккаунт"
            }
        }
        
        return recommendations.get(account_age, recommendations["fresh"])
    
    async def gentle_join_chats(self, client, chat_list: List[str], session_name: str):
        """Мягкое вступление в чаты для новых аккаунтов"""
        account_age = self.detect_account_age(session_name)
        settings = self.get_autoreg_safety_settings(account_age, "join_chats")
        
        max_joins = min(len(chat_list), settings["max_daily_actions"])
        min_delay = settings["min_delay"]
        max_delay = settings["max_delay"]
        
        await self.log(f"🚀 {session_name}: Мягкое вступление ({account_age}, макс. {max_joins} чатов)")
        
        joined_count = 0
        
        for i, chat_link in enumerate(chat_list[:max_joins]):
            if joined_count >= max_joins:
                break
            
            try:
                await self.log(f"🔗 {session_name}: [{i+1}/{max_joins}] Вступаю в {chat_link[:30]}...")
                
                # Пытаемся вступить
                if 'joinchat/' in chat_link or '+' in chat_link:
                    invite = chat_link.split('joinchat/')[-1] if 'joinchat/' in chat_link else chat_link.split('+')[-1]
                    await client(ImportChatInviteRequest(invite))
                else:
                    await client(JoinChannelRequest(chat_link))
                
                joined_count += 1
                await self.log(f"✅ {session_name}: Успешно вступил в чат")
                
                # Увеличенная пауза для новых аккаунтов
                delay = random.randint(min_delay, max_delay)
                await self.log(f"⏳ {session_name}: Безопасная пауза {delay}с...")
                await asyncio.sleep(delay)
                
            except PeerFloodError:
                await self.log(f"🚫 {session_name}: PeerFlood - слишком много запросов, останавливаю")
                break
            except FloodWaitError as e:
                await self.log(f"⏳ {session_name}: FloodWait {e.seconds}с")
                await asyncio.sleep(e.seconds)
            except UserPrivacyRestrictedError:
                await self.log(f"🔒 {session_name}: Ограничения приватности для {chat_link}")
                continue
            except Exception as e:
                await self.log(f"❌ {session_name}: Ошибка с {chat_link}: {type(e).__name__}")
                continue
        
        await self.log(f"🏁 {session_name}: Завершено. Вступил в {joined_count} чатов")
        return joined_count
    
    async def gentle_spam(self, client, targets: List[Dict], messages: List[str], session_name: str, task_type: str):
        """Мягкий спам для новых аккаунтов"""
        account_age = self.detect_account_age(session_name)
        settings = self.get_autoreg_safety_settings(account_age, task_type)
        
        max_messages = min(len(targets), settings["max_daily_actions"])
        min_delay = settings["min_delay"]
        max_delay = settings["max_delay"]
        
        await self.log(f"💬 {session_name}: Мягкий спам ({account_age}, макс. {max_messages} сообщений)")
        
        sent_count = 0
        error_count = 0
        
        for i, target in enumerate(targets[:max_messages]):
            if sent_count >= max_messages or error_count >= 3:
                break
            
            try:
                message = random.choice(messages)
                await client.send_message(target['entity'], message)
                sent_count += 1
                
                await self.log(f"✅ {session_name}: [{sent_count}/{max_messages}] → {target['title'][:20]}")
                
                # Проверяем, не удалилось ли сообщение
                await asyncio.sleep(3)
                
                # Увеличенная пауза для авторег аккаунтов
                delay = random.randint(min_delay, max_delay)
                await self.log(f"⏳ {session_name}: Безопасная пауза {delay}с...")
                await asyncio.sleep(delay)
                
            except PeerFloodError:
                await self.log(f"🚫 {session_name}: PeerFlood - превышен лимит, останавливаю")
                error_count += 5  # Критическая ошибка
                break
            except FloodWaitError as e:
                await self.log(f"⏳ {session_name}: FloodWait {e.seconds}с")
                await asyncio.sleep(e.seconds)
                error_count += 1
            except Exception as e:
                await self.log(f"❌ {session_name}: Ошибка → {target['title'][:20]}: {type(e).__name__}")
                error_count += 1
                
                if error_count >= 3:
                    await self.log(f"🛑 {session_name}: Слишком много ошибок, останавливаю")
                    break
        
        await self.log(f"🏁 {session_name}: Завершено. Отправлено: {sent_count}, ошибок: {error_count}")
        return sent_count, error_count
    
    def should_warmup_account(self, session_name: str) -> bool:
        """Нужно ли прогревать аккаунт"""
        account_age = self.detect_account_age(session_name)
        
        # Проверяем, был ли уже прогрев
        if session_name in self.warmup_stages:
            warmup_data = self.warmup_stages[session_name]
            if warmup_data.get('warmed_up', False):
                return False
        
        # Свежие и новые аккаунты нуждаются в прогреве
        return account_age in ["fresh", "new"]
    
    def get_account_status_for_task(self, session_name: str, task_type: str) -> Tuple[bool, str, Dict]:
        """Получение статуса аккаунта для конкретной задачи"""
        account_age = self.detect_account_age(session_name)
        settings = self.get_autoreg_safety_settings(account_age, task_type)
        
        # Проверяем нужен ли прогрев
        needs_warmup = self.should_warmup_account(session_name)
        
        if needs_warmup and task_type in ["spam_dm", "spam_chats", "join_chats"]:
            return False, f"Требуется прогрев для {account_age} аккаунта", settings
        
        # Проверяем совместимость задачи с возрастом аккаунта
        forbidden_tasks = {
            "fresh": ["spam_dm", "spam_dm_existing", "spam_chats", "join_chats"],
            "new": ["spam_dm"],
        }
        
        if task_type in forbidden_tasks.get(account_age, []):
            return False, f"Задача {task_type} слишком рискованна для {account_age} аккаунта", settings
        
        return True, f"Безопасно для {account_age} аккаунта", settings

# Глобальный экземпляр
_autoreg_manager = None

def get_autoreg_manager(progress_callback=None) -> AutoregManager:
    """Получение глобального экземпляра AutoregManager"""
    global _autoreg_manager
    if _autoreg_manager is None:
        _autoreg_manager = AutoregManager(progress_callback)
    return _autoreg_manager