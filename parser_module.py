# parser_module.py

import asyncio
import os
import csv
import json
import datetime
from typing import List, Dict, Optional, Union
from telethon import TelegramClient
from telethon.tl.types import User, Chat, Channel, PeerUser, PeerChat, PeerChannel
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import ChannelParticipantsSearch, InputPeerEmpty
from telethon.errors import FloodWaitError, ChannelPrivateError, ChatAdminRequiredError
import storage_manager

class TelegramParser:
    def __init__(self, session_name: str, progress_callback=None):
        self.session_name = session_name
        self.client: Optional[TelegramClient] = None
        self.progress_callback = progress_callback
        self.is_connected = False
        
    async def log(self, message: str):
        """Логирование с callback"""
        if self.progress_callback:
            await self.progress_callback(f"{self.session_name}: {message}")
        else:
            print(f"{self.session_name}: {message}")
    
    async def connect(self) -> bool:
        """Подключение к Telegram"""
        try:
            await self.log("🔌 Подключение к Telegram...")
            
            json_path = os.path.join(storage_manager.SESSIONS_DIR, f"{self.session_name}.json")
            if not os.path.exists(json_path):
                await self.log("❌ Файл .json не найден")
                return False
                
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            api_id = data.get('api_id') or data.get('app_id')
            api_hash = data.get('api_hash') or data.get('app_hash')
            
            if not api_id or not api_hash:
                await self.log("❌ Отсутствуют API данные в .json файле")
                return False
            
            self.client = TelegramClient(
                os.path.join(storage_manager.SESSIONS_DIR, self.session_name),
                int(api_id),
                api_hash,
                timeout=30
            )
            
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                two_fa = data.get('twoFA')
                if two_fa:
                    await self.client.sign_in(password=two_fa)
                else:
                    await self.log("❌ Аккаунт не авторизован")
                    return False
            
            self.is_connected = True
            await self.log("✅ Успешное подключение")
            return True
            
        except Exception as e:
            await self.log(f"❌ Ошибка подключения: {e}")
            return False
    
    async def disconnect(self):
        """Отключение от Telegram"""
        if self.client and self.client.is_connected():
            await self.client.disconnect()
            self.is_connected = False
            await self.log("🔌 Отключен")
    
    async def parse_group_members(self, group_identifier: str, limit: int = 10000) -> List[Dict]:
        """Парсинг участников группы/канала"""
        if not self.is_connected:
            await self.log("❌ Нет подключения к Telegram")
            return []
        
        try:
            await self.log(f"👥 Начинаю парсинг участников: {group_identifier}")
            
            # Получаем объект группы/канала
            entity = await self.client.get_entity(group_identifier)
            await self.log(f"📍 Найден: {entity.title}")
            
            participants = []
            offset = 0
            batch_size = 200
            
            while len(participants) < limit:
                try:
                    batch = await self.client(GetParticipantsRequest(
                        entity,
                        ChannelParticipantsSearch(''),
                        offset,
                        batch_size,
                        hash=0
                    ))
                    
                    if not batch.users:
                        break
                    
                    for user in batch.users:
                        if len(participants) >= limit:
                            break
                            
                        participant_data = {
                            'id': user.id,
                            'username': user.username or '',
                            'first_name': user.first_name or '',
                            'last_name': user.last_name or '',
                            'phone': user.phone or '',
                            'is_bot': user.bot,
                            'is_verified': user.verified,
                            'is_premium': getattr(user, 'premium', False),
                            'status': str(user.status) if user.status else '',
                            'parsed_at': datetime.datetime.now().isoformat()
                        }
                        participants.append(participant_data)
                    
                    offset += len(batch.users)
                    await self.log(f"📊 Спарсено: {len(participants)} участников")
                    
                    # Небольшая пауза между запросами
                    await asyncio.sleep(1)
                    
                except FloodWaitError as e:
                    await self.log(f"⏳ Флуд контроль: ожидание {e.seconds} секунд")
                    await asyncio.sleep(e.seconds)
                    continue
                except Exception as e:
                    await self.log(f"⚠️ Ошибка в батче: {e}")
                    break
            
            await self.log(f"✅ Парсинг завершен. Получено: {len(participants)} участников")
            return participants
            
        except ChannelPrivateError:
            await self.log("❌ Группа/канал приватные или недоступны")
            return []
        except ChatAdminRequiredError:
            await self.log("❌ Требуются права администратора")
            return []
        except Exception as e:
            await self.log(f"❌ Ошибка парсинга: {e}")
            return []
    
    async def parse_chat_messages(self, chat_identifier: str, limit: int = 1000) -> List[Dict]:
        """Парсинг сообщений из чата"""
        if not self.is_connected:
            await self.log("❌ Нет подключения к Telegram")
            return []
        
        try:
            await self.log(f"💬 Начинаю парсинг сообщений: {chat_identifier}")
            
            entity = await self.client.get_entity(chat_identifier)
            await self.log(f"📍 Найден чат: {entity.title if hasattr(entity, 'title') else 'Личный чат'}")
            
            messages_data = []
            offset_id = 0
            
            while len(messages_data) < limit:
                try:
                    messages = await self.client.get_messages(
                        entity,
                        limit=min(100, limit - len(messages_data)),
                        offset_id=offset_id
                    )
                    
                    if not messages:
                        break
                    
                    for message in messages:
                        if message.message:  # Только текстовые сообщения
                            sender_info = {}
                            if message.sender:
                                sender_info = {
                                    'sender_id': message.sender.id,
                                    'sender_username': getattr(message.sender, 'username', ''),
                                    'sender_first_name': getattr(message.sender, 'first_name', ''),
                                    'sender_last_name': getattr(message.sender, 'last_name', ''),
                                }
                            
                            message_data = {
                                'id': message.id,
                                'date': message.date.isoformat(),
                                'message': message.message,
                                'views': getattr(message, 'views', 0),
                                'forwards': getattr(message, 'forwards', 0),
                                'replies_count': getattr(message.replies, 'replies', 0) if message.replies else 0,
                                **sender_info,
                                'parsed_at': datetime.datetime.now().isoformat()
                            }
                            messages_data.append(message_data)
                    
                    if messages:
                        offset_id = messages[-1].id
                    
                    await self.log(f"📊 Спарсено сообщений: {len(messages_data)}")
                    await asyncio.sleep(1)  # Пауза между запросами
                    
                except FloodWaitError as e:
                    await self.log(f"⏳ Флуд контроль: ожидание {e.seconds} секунд")
                    await asyncio.sleep(e.seconds)
                    continue
                except Exception as e:
                    await self.log(f"⚠️ Ошибка получения сообщений: {e}")
                    break
            
            await self.log(f"✅ Парсинг сообщений завершен. Получено: {len(messages_data)}")
            return messages_data
            
        except Exception as e:
            await self.log(f"❌ Ошибка парсинга сообщений: {e}")
            return []
    
    async def get_user_dialogs(self) -> List[Dict]:
        """Получение списка диалогов пользователя"""
        if not self.is_connected:
            await self.log("❌ Нет подключения к Telegram")
            return []
        
        try:
            await self.log("📋 Получаю список диалогов...")
            
            dialogs = await self.client.get_dialogs()
            dialogs_data = []
            
            for dialog in dialogs:
                dialog_info = {
                    'id': dialog.entity.id,
                    'title': dialog.title,
                    'type': 'user' if isinstance(dialog.entity, User) else 
                            'chat' if isinstance(dialog.entity, Chat) else 'channel',
                    'username': getattr(dialog.entity, 'username', ''),
                    'participants_count': getattr(dialog.entity, 'participants_count', 0),
                    'unread_count': dialog.unread_count,
                    'is_pinned': dialog.pinned,
                    'parsed_at': datetime.datetime.now().isoformat()
                }
                dialogs_data.append(dialog_info)
            
            await self.log(f"✅ Получено диалогов: {len(dialogs_data)}")
            return dialogs_data
            
        except Exception as e:
            await self.log(f"❌ Ошибка получения диалогов: {e}")
            return []
    
    async def export_to_csv(self, data: List[Dict], filename: str) -> bool:
        """Экспорт данных в CSV"""
        try:
            if not data:
                await self.log("⚠️ Нет данных для экспорта")
                return False
            
            # Создаем папку для экспорта если её нет
            export_dir = os.path.join(storage_manager.DATA_DIR, "exports")
            os.makedirs(export_dir, exist_ok=True)
            
            filepath = os.path.join(export_dir, filename)
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                if data:
                    fieldnames = data[0].keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(data)
            
            await self.log(f"✅ Данные экспортированы в: {filepath}")
            return True
            
        except Exception as e:
            await self.log(f"❌ Ошибка экспорта: {e}")
            return False
    
    async def export_to_json(self, data: List[Dict], filename: str) -> bool:
        """Экспорт данных в JSON"""
        try:
            if not data:
                await self.log("⚠️ Нет данных для экспорта")
                return False
            
            export_dir = os.path.join(storage_manager.DATA_DIR, "exports")
            os.makedirs(export_dir, exist_ok=True)
            
            filepath = os.path.join(export_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as jsonfile:
                json.dump(data, jsonfile, ensure_ascii=False, indent=2)
            
            await self.log(f"✅ Данные экспортированы в: {filepath}")
            return True
            
        except Exception as e:
            await self.log(f"❌ Ошибка экспорта: {e}")
            return False

# Функции для интеграции с существующей системой
async def create_parser_task(session_name: str, task_type: str, target: str, options: Dict):
    """Создание задачи парсинга"""
    parser = TelegramParser(session_name)
    
    if not await parser.connect():
        return False
    
    try:
        if task_type == "parse_members":
            limit = options.get('limit', 10000)
            data = await parser.parse_group_members(target, limit)
            
            if data and options.get('export_format'):
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"members_{target}_{timestamp}"
                
                if options['export_format'] == 'csv':
                    await parser.export_to_csv(data, f"{filename}.csv")
                elif options['export_format'] == 'json':
                    await parser.export_to_json(data, f"{filename}.json")
        
        elif task_type == "parse_messages":
            limit = options.get('limit', 1000)
            data = await parser.parse_chat_messages(target, limit)
            
            if data and options.get('export_format'):
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"messages_{target}_{timestamp}"
                
                if options['export_format'] == 'csv':
                    await parser.export_to_csv(data, f"{filename}.csv")
                elif options['export_format'] == 'json':
                    await parser.export_to_json(data, f"{filename}.json")
        
        elif task_type == "get_dialogs":
            data = await parser.get_user_dialogs()
            
            if data and options.get('export_format'):
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"dialogs_{session_name}_{timestamp}"
                
                if options['export_format'] == 'csv':
                    await parser.export_to_csv(data, f"{filename}.csv")
                elif options['export_format'] == 'json':
                    await parser.export_to_json(data, f"{filename}.json")
        
        return True
        
    except Exception as e:
        await parser.log(f"❌ Ошибка выполнения задачи: {e}")
        return False
    finally:
        await parser.disconnect()