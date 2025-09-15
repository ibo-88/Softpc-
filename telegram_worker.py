# telegram_worker.py

import asyncio
import os
import json
import random
import re
import string
from telethon import TelegramClient, events
from telethon.tl import functions
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.functions.account import UpdateProfileRequest, UpdatePersonalChannelRequest
from telethon.tl.functions.channels import CreateChannelRequest, UpdateUsernameRequest, EditPhotoRequest, JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors import SessionPasswordNeededError, FloodWaitError, RPCError
from telethon.errors.rpcerrorlist import (
    UserDeactivatedBanError, AuthKeyUnregisteredError, PasswordHashInvalidError,
    UsernameOccupiedError, ChannelPrivateError, UserAlreadyParticipantError,
    InviteHashExpiredError, InviteHashInvalidError, InviteRequestSentError,
    ChatWriteForbiddenError, UserBannedInChannelError, SlowModeWaitError, MsgIdInvalidError,
    ChatGuestSendForbiddenError
)
from telethon.tl.types import Chat, Channel
import storage_manager

async def cancellable_sleep(seconds, cancel_event):
    try:
        await asyncio.wait_for(cancel_event.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        pass

def random_string(length=12):
    first_char = random.choice(string.ascii_lowercase)
    other_chars = string.ascii_lowercase + string.digits
    rest = ''.join(random.choice(other_chars) for _ in range(length - 1))
    return first_char + rest

async def _check_spamblock(client: TelegramClient):
    try:
        await client.send_message('spambot', '/start')
        await asyncio.sleep(3)
        messages = await client.get_messages('spambot', limit=1)
        if not messages:
            return "⚠️ Не удалось получить ответ от @spambot."
        
        reply_text = messages[0].message

        if "Good news, no limits are currently applied" in reply_text:
            return None
        
        elif "Your account was blocked for violations of the Telegram Terms of Service" in reply_text:
            return "💀 Заморожен (ToS)"
            
        elif "your account is now limited until" in reply_text:
            match = re.search(r'limited until (.*?)\.', reply_text)
            date_str = match.group(1) if match else "неизвестной даты"
            return f"🥶 Спам-блок (до {date_str})"
            
        elif "I’m very sorry that you had to contact me" in reply_text or "some actions can trigger a harsh response" in reply_text:
            return "🥶 Спам-блок (постоянный)"
        
        else:
            return f"❔ Неизвестный ответ от @spambot: {reply_text[:50]}..."

    except Exception as e:
        return f"⚠️ Ошибка проверки спам-блока: {type(e).__name__}"

class TelethonWorker:
    def __init__(self, session_name, proxy_queue, file_lock, settings_lock, callback, cancel_event, semaphore, task_name, task_data):
        self.session_name = session_name
        self.proxy_queue = proxy_queue
        self.file_lock = file_lock
        self.settings_lock = settings_lock
        self.callback = callback
        self.cancel_event = cancel_event
        self.client: TelegramClient = None
        self.semaphore = semaphore
        
        self.task_name = task_name
        self.task_data = task_data
        self.task_settings = task_data.get('settings', {})

    async def _connect(self):
        await self.callback(f"{self.session_name}:🔌 Подключение...")
        json_path = os.path.join(storage_manager.SESSIONS_DIR, f"{self.session_name}.json")
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            await self.callback(f"{self.session_name}:❌ Файлы сессии (.json) не найдены.")
            return False
        
        api_id_val = data.get('api_id') or data.get('app_id')
        api_hash = data.get('api_hash') or data.get('app_hash')
        
        try:
            api_id = int(api_id_val)
        except (ValueError, TypeError):
            await self.callback(f"{self.session_name}:❌ В .json файле отсутствует или имеет неверный формат 'api_id'/'app_id'.")
            return False
            
        two_fa = data.get('twoFA')
        device_model = data.get('device_model') or data.get('device') or 'PC'
        system_version = data.get('system_version') or data.get('sdk') or 'Windows 10'
        app_version = data.get('app_version', '4.8.1 x64')
        lang_code = data.get('lang_code') or data.get('lang_pack') or 'en'
        system_lang_code = data.get('system_lang_code') or data.get('system_lang_pack') or 'en-US'

        if self.task_data.get('type') == 'check_all':
            lang_code = 'en'
            system_lang_code = 'en-US'
            await self.callback(f"{self.session_name}:ℹ️ Установлен английский язык для проверки спам-блока.")

        if not api_id or not api_hash:
            await self.callback(f"{self.session_name}:❌ В .json файле отсутствуют 'api_id'/'app_id' или 'api_hash'/'app_hash'.")
            return False

        proxy_str = "без прокси"
        proxy_dict = None
        proxy_from_queue = None
        
        if not self.proxy_queue.empty():
            try:
                proxy_from_queue = self.proxy_queue.get_nowait()
                p = proxy_from_queue.split(':')
                if len(p) == 4:
                    proxy_dict = {'proxy_type': 'socks5', 'addr': p[0], 'port': int(p[1]), 'username': p[2], 'password': p[3]}
                    proxy_str = f"{p[0]}:{p[1]} (из пула)"
            except asyncio.QueueEmpty:
                pass

        await self.callback(f"{self.session_name}:🔌 Подкл. через {proxy_str}")

        try:
            self.client = TelegramClient(
                os.path.join(storage_manager.SESSIONS_DIR, self.session_name),
                api_id,
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
            await self.client.connect()

            if not await self.client.is_user_authorized():
                await self.client.sign_in(password=two_fa)

            if proxy_from_queue: self.proxy_queue.put_nowait(proxy_from_queue)
            return True
        
        except (asyncio.TimeoutError, OSError) as e:
            await self.callback(f"{self.session_name}:⚠️ Прокси {proxy_str} не работает ({type(e).__name__}).")
            return False
        except Exception as e:
            error_map = {
                UserDeactivatedBanError: "❌ Забанен или удален.", AuthKeyUnregisteredError: "❌ Забанен или удален.",
                SessionPasswordNeededError: "❌ Требуется 2FA пароль (проверь поле twoFA в .json).", 
                PasswordHashInvalidError: "❌ Неверный 2FA пароль."
            }
            error_message = error_map.get(type(e), f"❌ Критическая ошибка: {e}")
            await self.callback(f"{self.session_name}:{error_message}")
            if self.client and self.client.is_connected():
                await self.client.disconnect()
            return False

    async def run_task(self, task_coroutine, *args, **kwargs):
        if await self._connect():
            reply_setting_enabled = self.task_settings.get('reply_in_pm', False)
            pm_reply_messages = storage_manager.read_task_multiline_messages(self.task_name, 'pm_replies')

            if reply_setting_enabled and pm_reply_messages:
                async def private_message_handler(event):
                    if event.is_private and not (await event.get_sender()).bot:
                        await asyncio.sleep(random.randint(5, 15))
                        reply_text = random.choice(pm_reply_messages)
                        await event.respond(reply_text)
                        await self.callback(f"{self.session_name}: 📨 Ответил в ЛС пользователю {event.sender_id}")

                self.client.add_event_handler(private_message_handler, events.NewMessage(incoming=True))
                await self.callback(f"{self.session_name}: 🤖 Автоответчик в ЛС включен.")

            try:
                await task_coroutine(*args, **kwargs)
            except asyncio.CancelledError:
                pass
            except (OSError, asyncio.TimeoutError, RPCError) as e:
                await self.callback(f"{self.session_name}:📡 Сбой сети: {type(e).__name__}. Завершаю.")
            except Exception as e:
                await self.callback(f"{self.session_name}:❌ Критическая ошибка в задаче: {e}")
            finally:
                if self.client and self.client.is_connected():
                    await self.client.disconnect()
        else:
            pass

    async def task_check_account(self, change_name, change_avatar, change_lastname, perform_spam_check: bool = False):
        async with self.semaphore:
            if self.cancel_event.is_set(): return
            
            if perform_spam_check:
                block_status = await _check_spamblock(self.client)
                if block_status:
                    await self.callback(f"{self.session_name}: {block_status}")
                    return

            me = await self.client.get_me()
            status = f"✅ Валиден ({me.first_name} {me.last_name or ''})".strip()
            await self.callback(f"{self.session_name}:{status}")
            
            if change_avatar:
                if self.cancel_event.is_set(): return
                avatars_dir = storage_manager.get_task_file_path(self.task_name, 'avatars')
                images = [f for f in os.listdir(avatars_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))] if os.path.exists(avatars_dir) else []

                if images:
                    try:
                        photo_path = os.path.join(avatars_dir, random.choice(images))
                        await self.client(UploadProfilePhotoRequest(file=await self.client.upload_file(photo_path)))
                        status += " | 🖼️ Аватар изменен"
                    except Exception as e: status += f" | ❌ Ошибка смены аватара: {e}"
                else: status += " | ⚠️ Нет аватаров для этой задачи"
                await self.callback(f"{self.session_name}:{status}")
            
            if change_name:
                if self.cancel_event.is_set(): return
                names = storage_manager.read_task_text_file_lines(self.task_name, 'names')
                if names:
                    try:
                        new_name = random.choice(names)
                        await self.client(UpdateProfileRequest(first_name=new_name))
                        status += f" | 👤 Имя -> '{new_name}'"
                    except Exception as e: status += f" | ❌ Ошибка смены имени: {e}"
                else: status += f" | ⚠️ Файл names.txt для задачи пуст"
                await self.callback(f"{self.session_name}:{status}")
            
            if change_lastname:
                if self.cancel_event.is_set(): return
                lastnames = storage_manager.read_task_text_file_lines(self.task_name, 'lastnames')
                if lastnames:
                    try:
                        new_lastname = random.choice(lastnames)
                        await self.client(UpdateProfileRequest(last_name=new_lastname))
                        status += f" | 📜 Фамилия -> '{new_lastname}'"
                    except Exception as e: status += f" | ❌ Ошибка смены фамилии: {e}"
                else: status += " | ⚠️ Файл lastnames.txt для задачи пуст"
                await self.callback(f"{self.session_name}:{status}")
        
    async def task_delete_lastnames(self):
        async with self.semaphore:
            if self.cancel_event.is_set(): return
            await self.callback(f"{self.session_name}: Удаление фамилии...")
            try:
                await self.client(UpdateProfileRequest(last_name=""))
                await self.callback(f"{self.session_name}: ✅ Фамилия успешно удалена.")
            except Exception as e:
                await self.callback(f"{self.session_name}: ❌ Ошибка при удалении фамилии: {e}")

    async def task_create_channel(self):
        async with self.semaphore:
            if self.cancel_event.is_set(): return
            status = "▶️ Начинаю создание канала..."
            await self.callback(f"{self.session_name}:{status}")

            channel_names = storage_manager.read_task_text_file_lines(self.task_name, 'channel_names')
            descriptions = storage_manager.read_task_text_file_lines(self.task_name, 'channel_descriptions')

            if not channel_names or not descriptions:
                await self.callback(f"{self.session_name}:❌ Файлы channelnames.txt или channel_descriptions.txt для задачи пусты.")
                return

            fwd_link = self.task_settings.get('forward_post_link')
            if not fwd_link:
                await self.callback(f"{self.session_name}:❌ Ссылка на пост для пересылки не задана в настройках задачи.")
                return

            channel_title = random.choice(channel_names)
            channel_about = random.choice(descriptions)
            try:
                created_channel_result = await self.client(CreateChannelRequest(title=channel_title, about=channel_about))
                channel = created_channel_result.chats[0]
                status += f" | ✅ Канал '{channel_title}' создан."
                await self.callback(f"{self.session_name}:{status}")
            except Exception as e:
                await self.callback(f"{self.session_name}:❌ Ошибка при создании канала: {e}")
                return

            while not self.cancel_event.is_set():
                try:
                    username = random_string()
                    await self.client(UpdateUsernameRequest(channel.id, username))
                    status += f" | @{username}"
                    await self.callback(f"{self.session_name}:{status}")
                    break
                except UsernameOccupiedError:
                    continue
                except FloodWaitError as e:
                    await self.callback(f"{self.session_name}:{status} | ⏳ Флуд, жду {e.seconds}с...")
                    await cancellable_sleep(e.seconds, self.cancel_event)
                except Exception as e:
                    status += f" | ❌ Ошибка установки юзернейма: {e}"
                    await self.callback(f"{self.session_name}:{status}")
                    break
            
            if self.cancel_event.is_set(): return

            channel_avatars_dir = storage_manager.get_task_file_path(self.task_name, 'channel_avatars')
            images = [f for f in os.listdir(channel_avatars_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))] if os.path.exists(channel_avatars_dir) else []
            if images:
                try:
                    avatar_path = os.path.join(channel_avatars_dir, random.choice(images))
                    await self.client(EditPhotoRequest(channel=channel, photo=await self.client.upload_file(avatar_path)))
                    status += " | 🖼️ Аватар установлен"
                    await self.callback(f"{self.session_name}:{status}")
                except Exception as e:
                    status += f" | ❌ Ошибка установки аватара: {e}"
                    await self.callback(f"{self.session_name}:{status}")
            else:
                status += " | ⚠️ Нет аватаров для канала в этой задаче"
                await self.callback(f"{self.session_name}:{status}")

            if self.cancel_event.is_set(): return

            try:
                await self.client(UpdatePersonalChannelRequest(channel=channel))
                status += " | 📌 В профиле"
                await self.callback(f"{self.session_name}:{status}")
            except Exception as e:
                status += f" | ❌ Ошибка установки в профиль: {e}"
                await self.callback(f"{self.session_name}:{status}")
            
            if self.cancel_event.is_set(): return

            try:
                match = re.search(r'(t\.me|telegram\.me)/(c/)?([\w\d_]+)/(\d+)', fwd_link)
                if not match:
                    raise ValueError("Формат ссылки не поддерживается.")
                
                channel_username_or_id = match.group(3)
                msg_id = int(match.group(4))
                
                try:
                    source_entity = int(f"-100{channel_username_or_id}")
                except ValueError:
                    source_entity = channel_username_or_id

                await self.client.forward_messages(entity=channel, messages=msg_id, from_peer=source_entity)
                status += " | 📨 Пост переслан"
                await self.callback(f"{self.session_name}:{status}")
            except Exception as e:
                status += f" | ❌ Ошибка пересылки поста: {e}"
                await self.callback(f"{self.session_name}:{status}")

    async def task_delete_avatars(self):
        async with self.semaphore:
            if self.cancel_event.is_set(): return
            await self.callback(f"{self.session_name}: Удаление аватаров...")
            try:
                photos_to_delete = await self.client.get_profile_photos('me')
                if not photos_to_delete:
                    await self.callback(f"{self.session_name}: ⚠️ Аватаров для удаления нет.")
                    return

                await self.client(DeletePhotosRequest(id=photos_to_delete))
                await self.callback(f"{self.session_name}: ✅ Удалено {len(photos_to_delete)} аватаров.")

            except Exception as e:
                await self.callback(f"{self.session_name}: ❌ Ошибка при удалении аватаров: {e}")
        
    async def task_join_chats(self, work_queue: asyncio.Queue):
        processed_count = 0
        chat_file_path = storage_manager.get_task_file_path(self.task_name, 'chats')
        
        while not work_queue.empty() and not self.cancel_event.is_set():
            try:
                chat_link = work_queue.get_nowait()
            except asyncio.QueueEmpty:
                break 

            flood_wait_seconds = 0
            
            async with self.semaphore:
                if self.cancel_event.is_set():
                    await work_queue.put(chat_link)
                    break
                try:
                    status_prefix = f"Вступление в {chat_link[:30]}..."
                    await self.callback(f"{self.session_name}:{status_prefix}")
                    result_symbol = ""
                    
                    clean_link = chat_link.strip().replace('https://', '').replace('http://', '')
                    if 'joinchat/' in clean_link or '+' in clean_link:
                        invite = clean_link.split('joinchat/')[-1] if 'joinchat/' in clean_link else clean_link.split('+')[-1]
                        await self.client(ImportChatInviteRequest(invite))
                    else: 
                        await self.client(JoinChannelRequest(chat_link))
                    result_symbol = "✅"
                    processed_count += 1
                    
                    if chat_file_path:
                        await storage_manager.remove_line_from_file(
                            chat_file_path,
                            chat_link, self.file_lock
                        )
                except InviteRequestSentError:
                    result_symbol = "📨"
                    processed_count += 1
                except UserAlreadyParticipantError: 
                    result_symbol = "🟡"
                    processed_count += 1
                except (InviteHashExpiredError, InviteHashInvalidError, ValueError): 
                    result_symbol = "❌"
                except FloodWaitError as e:
                    result_symbol = f"⏳({e.seconds}с)"
                    flood_wait_seconds = e.seconds
                    await work_queue.put(chat_link)
                except Exception as e: 
                    result_symbol = f"❌({type(e).__name__})"
                
                await self.callback(f"{self.session_name}:{status_prefix} -> {result_symbol}")
            
            if flood_wait_seconds > 0:
                await cancellable_sleep(flood_wait_seconds, self.cancel_event)
            else:
                cooldown_time = random.randint(30, 90)
                await cancellable_sleep(cooldown_time, self.cancel_event)
        
        await self.callback(f"{self.session_name}:🏁 Завершил работу. Вступил в {processed_count} чатов.")

    async def task_autobroadcast(self):
        messages = storage_manager.read_task_multiline_messages(self.task_name, 'messages')
        if not messages:
            await self.callback(f"{self.session_name}:❌ Файл messages.txt для этой задачи пуст.")
            return
            
        while not self.cancel_event.is_set():
            target_mode = self.task_settings.get('broadcast_target', 'chats')
            await self.callback(f"{self.session_name}:🔄 Новый цикл...")
            
            dialogs = await self.client.get_dialogs(limit=None)
            
            global_settings = storage_manager.load_settings()
            initial_blacklist = set(global_settings.get('blacklist', []))
            targets = []

            if target_mode in ['chats', 'both']:
                chats = [d for d in dialogs if isinstance(d.entity, (Chat, Channel)) and getattr(d.entity, 'megagroup', True) and d.entity.id not in initial_blacklist]
                targets.extend([{'type': 'chat', 'entity': c.entity, 'title': c.entity.title} for c in chats])
            
            if target_mode in ['comments', 'both']:
                channels = [d for d in dialogs if isinstance(d.entity, Channel) and not getattr(d.entity, 'megagroup', False) and d.entity.id not in initial_blacklist]
                for channel in channels:
                    try:
                        last_post = (await self.client.get_messages(channel.entity, limit=1))[0]
                        if last_post and last_post.replies and last_post.replies.replies > 0:
                            targets.append({'type': 'comment', 'entity': channel.entity, 'post_id': last_post.id, 'title': f"комментарии к '{channel.entity.title}'"})
                    except Exception: continue
            
            random.shuffle(targets)
            await self.callback(f"{self.session_name}:🎯 Найдено {len(targets)} целей.")

            for i, target in enumerate(targets):
                if self.cancel_event.is_set(): break
                
                status_prefix = f"Рассылка: [{i+1}/{len(targets)}] -> '{target['title']}'"
                result_symbol = ""
                sleep_duration_from_error = 0
                
                async with self.semaphore:
                    if self.cancel_event.is_set(): break
                    try:
                        async with self.settings_lock:
                            current_settings = storage_manager.load_settings()
                            is_blacklisted = target['entity'].id in current_settings.get('blacklist', [])

                        if is_blacklisted:
                            result_symbol = "⏭️ Пропуск, уже в ЧС"
                        else:
                            msg_to_send = random.choice(messages)
                            sent_msg = None
                            if target['type'] == 'chat': sent_msg = await self.client.send_message(target['entity'], msg_to_send)
                            elif target['type'] == 'comment': sent_msg = await self.client.send_message(target['entity'], msg_to_send, comment_to=target['post_id'])
                            
                            result_symbol = "✅"
                            await cancellable_sleep(15, self.cancel_event)
                            if self.cancel_event.is_set(): break

                            history = await self.client.get_messages(target['entity'], ids=[sent_msg.id])
                            if not history or history[0] is None:
                                result_symbol = "🗑️ в ЧС (удалено)"
                                entity_id = target['entity'].id
                                async with self.settings_lock:
                                    current_settings = storage_manager.load_settings()
                                    if entity_id not in current_settings.get('blacklist', []):
                                        current_settings.setdefault('blacklist', []).append(entity_id)
                                        storage_manager.save_settings(current_settings)
                    
                    except (ChatWriteForbiddenError, UserBannedInChannelError, MsgIdInvalidError, ChatGuestSendForbiddenError) as e:
                        result_symbol = f"🚫 в ЧС ({type(e).__name__})"
                        entity_id = target['entity'].id
                        async with self.settings_lock:
                            current_settings = storage_manager.load_settings()
                            if entity_id not in current_settings.get('blacklist', []):
                                current_settings.setdefault('blacklist', []).append(entity_id)
                                storage_manager.save_settings(current_settings)
                    except (SlowModeWaitError, FloodWaitError) as e:
                        result_symbol = f"⏳({e.seconds}с)"
                        sleep_duration_from_error = e.seconds
                    except Exception as e:
                        result_symbol = f"❌({type(e).__name__})"

                final_status = f"{status_prefix} -> {result_symbol}"
                await self.callback(f"{self.session_name}:{final_status}")

                if 'в ЧС' not in result_symbol and 'Пропуск' not in result_symbol and not self.cancel_event.is_set():
                    if sleep_duration_from_error > 0:
                        delay = sleep_duration_from_error
                    else:
                        delay = random.randint(self.task_settings['broadcast_interval'][0], self.task_settings['broadcast_interval'][1])
                    
                    await self.callback(f"{self.session_name}:Пауза {delay}с...")
                    await cancellable_sleep(delay, self.cancel_event)

            if not self.cancel_event.is_set():
                cycle_delay = 300
                await self.callback(f"{self.session_name}:🏁 Цикл завершен, пауза {cycle_delay // 60} мин...")
                await cancellable_sleep(cycle_delay, self.cancel_event)
                
        await self.callback(f"{self.session_name}:🛑 Авторассылка остановлена.")

    async def task_set_2fa(self, password):
        async with self.semaphore:
            if self.cancel_event.is_set(): return
            await self.callback(f"{self.session_name}:🔐 Установка 2FA...")
            try:
                password_settings = await self.client(functions.account.GetPasswordRequest())
                if password_settings.has_password:
                     await self.callback(f"{self.session_name}:⚠️ Пароль уже установлен. Используйте 'Удалить 2FA'.")
                     return

                await self.client.edit_2fa(new_password=password, hint=" ")
                await self.callback(f"{self.session_name}:✅ 2FA пароль успешно установлен.")
            except Exception as e:
                await self.callback(f"{self.session_name}:❌ Ошибка при установке 2FA: {e}")

    async def task_remove_2fa(self, password):
        async with self.semaphore:
            if self.cancel_event.is_set(): return
            await self.callback(f"{self.session_name}:🔓 Удаление 2FA...")
            try:
                await self.client.edit_2fa(current_password=password, new_password=None)
                await self.callback(f"{self.session_name}:✅ 2FA пароль успешно удален.")
            except PasswordHashInvalidError:
                await self.callback(f"{self.session_name}:❌ Неверный текущий пароль 2FA.")
            except Exception as e:
                await self.callback(f"{self.session_name}:❌ Ошибка при удалении 2FA: {e}")
                
    async def task_terminate_sessions(self):
        async with self.semaphore:
            if self.cancel_event.is_set(): return
            await self.callback(f"{self.session_name}:💨 Завершение других сессий...")
            try:
                terminated_count = 0
                authorizations = await self.client(functions.account.GetAuthorizationsRequest())
                for auth in authorizations.authorizations:
                    if not auth.current:
                        await self.client(functions.account.ResetAuthorizationRequest(hash=auth.hash))
                        terminated_count += 1
                
                await self.callback(f"{self.session_name}:✅ Завершено {terminated_count} сторонних сессий.")
            except Exception as e:
                await self.callback(f"{self.session_name}:❌ Ошибка при завершении сессий: {e}")

    async def task_reauthorize_account(self):
        await self.callback(f"{self.session_name}:🔄 Начинаю переавторизацию...")

        old_session_path = os.path.join(storage_manager.SESSIONS_DIR, self.session_name)
        new_session_name = f"{self.session_name}_reauth"
        new_session_path = os.path.join(storage_manager.SESSIONS_DIR, new_session_name)
        
        new_client = None

        try:
            if not self.client or not self.client.is_connected():
                await self.callback(f"{self.session_name}:❌ Не удалось подключиться к старой сессии.")
                return

            me = await self.client.get_me()
            if not me or not me.phone:
                await self.callback(f"{self.session_name}:❌ Не удалось получить номер телефона из старой сессии.")
                return
            
            phone_number = f"+{me.phone}"
            await self.callback(f"{self.session_name}:📞 Получен номер: {phone_number}")

            json_path = os.path.join(storage_manager.SESSIONS_DIR, f"{self.session_name}.json")
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
            except FileNotFoundError:
                await self.callback(f"{self.session_name}:❌ Не найден .json для копирования данных устройства.")
                return

            device_model = json_data.get('device_model') or json_data.get('device') or 'PC'
            system_version = json_data.get('system_version') or json_data.get('sdk') or 'Windows 10'
            app_version = json_data.get('app_version', '4.8.1 x64')
            lang_code = json_data.get('lang_pack', 'en')
            system_lang_code = json_data.get('system_lang_pack', 'en-US')
            
            api_id = self.client.api_id
            api_hash = self.client.api_hash
            new_client = TelegramClient(
                new_session_path, 
                api_id, 
                api_hash,
                device_model=device_model,
                system_version=system_version,
                app_version=app_version,
                lang_code=lang_code,
                system_lang_code=system_lang_code
            )
            await new_client.connect()

            sent_code = await new_client.send_code_request(phone_number)
            await self.callback(f"{self.session_name}:💬 Код отправлен. Жду 15 секунд...")
            await asyncio.sleep(15)

            login_code = None
            messages = await self.client.get_messages(777000, limit=5)
            for message in messages:
                if message.text and ("Login code" in message.text or "Код для входа" in message.text):
                    match = re.search(r'(\d{5})', message.text)
                    if match:
                        login_code = match.group(1)
                        await self.callback(f"{self.session_name}:👍 Код найден: {login_code}")
                        break
            
            if not login_code:
                raise Exception("Не удалось найти код входа в сообщениях.")

            try:
                await new_client.sign_in(phone_number, login_code, phone_code_hash=sent_code.phone_code_hash)
            except SessionPasswordNeededError:
                await self.callback(f"{self.session_name}:🔑 Требуется пароль 2FA...")
                two_fa_password = self.task_settings.get("two_fa_password")
                if not two_fa_password:
                    raise Exception("Пароль 2FA не задан в настройках задачи.")
                
                await new_client.sign_in(password=two_fa_password)

            await self.callback(f"{self.session_name}:✅ Вход в новую сессию выполнен успешно.")

            await self.client.log_out()
            await self.client.disconnect()
            await new_client.disconnect()
            
            if os.path.exists(f"{old_session_path}.session"):
                os.remove(f"{old_session_path}.session")
            
            os.rename(f"{new_session_path}.session", f"{old_session_path}.session")
            
            await self.callback(f"{self.session_name}:🎉 Переавторизация завершена!")

        except Exception as e:
            await self.callback(f"{self.session_name}:❌ ОШИБКА: {e}. Старая сессия сохранена.")
            if new_client and new_client.is_connected():
                await new_client.disconnect()
            if os.path.exists(f"{new_session_path}.session"):
                os.remove(f"{new_session_path}.session")

    async def task_clean_account(self):
        await self.callback(f"{self.session_name}:🧹 Начинаю полную зачистку аккаунта...")
        
        try:
            dialogs = await self.client.get_dialogs(limit=None)
            total_dialogs = len(dialogs)
            await self.callback(f"{self.session_name}:🔍 Найдено {total_dialogs} диалогов для удаления.")
            
            for i, dialog in enumerate(dialogs):
                if self.cancel_event.is_set():
                    await self.callback(f"{self.session_name}:🛑 Зачистка остановлена пользователем.")
                    return

                status_prefix = f"[{i+1}/{total_dialogs}] {dialog.name}"
                
                try:
                    await self.client.delete_dialog(dialog.entity)
                    await self.callback(f"{self.session_name}:{status_prefix} -> ✅ Удален/Вышел")
                except Exception as e:
                    await self.callback(f"{self.session_name}:{status_prefix} -> ❌ Ошибка: {type(e).__name__}")
                
                interval_settings = self.task_settings.get('broadcast_interval', [5, 15])
                delay = random.randint(interval_settings[0], interval_settings[1])
                await cancellable_sleep(delay, self.cancel_event)

            await self.callback(f"{self.session_name}:🎉 Зачистка аккаунта успешно завершена.")
        except Exception as e:
            await self.callback(f"{self.session_name}:❌ Критическая ошибка во время зачистки: {e}")