# bot.py

import asyncio
import logging
import os
import shutil
import html
import random
import re
import io
import aiohttp
from aiohttp_proxy import ProxyConnector
from telegram import Update, InputMediaDocument, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode
import config
import keyboards
import storage_manager
from telegram_worker import TelethonWorker

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

AWAIT_TASK_NAME, AWAIT_GLOBAL_INPUT, AWAIT_TASK_INPUT = range(3)
active_tasks = {}
SETTINGS_LOCK = asyncio.Lock()


async def is_admin(update: Update) -> bool:
    user = update.effective_user
    if user.id not in config.ADMIN_IDS:
        logger.warning(f"Несанкционированный доступ от {user.id} ({user.username})")
        return False
    return True

async def run_proxy_checker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    cancel_event = asyncio.Event()
    active_tasks['proxy_checker'] = {'cancel_event': cancel_event}
    
    text, markup = keyboards.get_proxy_check_running_menu()
    try:
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    except BadRequest:
        pass

    settings = storage_manager.load_settings()
    all_proxies = settings.get('proxies', [])
    final_statuses = {}

    if not all_proxies:
        active_tasks.pop('proxy_checker', None)
        text, markup = keyboards.get_proxy_list_menu([], 1, {})
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        return

    semaphore = asyncio.Semaphore(20)

    async def check_single_proxy(proxy_str):
        async with semaphore:
            if cancel_event.is_set(): return
            try:
                p = proxy_str.split(':')
                if len(p) != 4:
                    final_statuses[proxy_str] = {'status': 'not_working', 'country': 'FormatErr'}
                    return
                
                connector = ProxyConnector.from_url(f'socks5://{p[2]}:{p[3]}@{p[0]}:{p[1]}')
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.get('http://ip-api.com/json/?fields=countryCode', timeout=15) as response:
                        if response.status == 200:
                            data = await response.json()
                            country = data.get('countryCode', 'N/A')
                            final_statuses[proxy_str] = {'status': 'working', 'country': country}
                        else:
                            final_statuses[proxy_str] = {'status': 'not_working', 'country': 'N/A'}
            except Exception as e:
                logger.warning(f"Proxy check failed for {proxy_str}: {type(e).__name__}")
                final_statuses[proxy_str] = {'status': 'not_working', 'country': 'N/A'}

    tasks = [check_single_proxy(p) for p in all_proxies]
    await asyncio.gather(*tasks)

    storage_manager.save_proxy_statuses(final_statuses)
    active_tasks.pop('proxy_checker', None)
    
    try:
        text, markup = keyboards.get_proxy_list_menu(all_proxies, 1, final_statuses)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    except BadRequest as e:
        if "message is not modified" not in str(e).lower():
            logger.error(f"Final proxy check update failed: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_admin(update): return
    context.user_data.clear()
    text, markup = keyboards.get_main_menu()
    await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, markup):
    query = update.callback_query
    try:
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except BadRequest as e:
        if "message is not modified" in str(e).lower():
            await query.answer()
        else:
            logger.error(f"Ошибка в main_menu_handler: {e.message}")
            try:
                await query.message.delete()
                await context.bot.send_message(
                    chat_id=query.message.chat_id, text=text, reply_markup=markup, parse_mode=ParseMode.HTML, disable_web_page_preview=True
                )
            except Exception as ex:
                logger.error(f"Не удалось отправить новое меню или удалить старое: {ex.message}")

async def go_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    text, markup = keyboards.get_main_menu()
    try:
        await query.message.delete()
    except Exception: pass
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=markup, parse_mode=ParseMode.HTML)

async def request_input_from_user(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt_text: str, state_key: str, back_button_cb: str, new_state: int, task_name: str = None):
    query = update.callback_query
    context.user_data['message_to_edit'] = query.message.message_id
    context.user_data['input_type'] = state_key
    
    if new_state == AWAIT_TASK_INPUT and task_name:
        context.user_data['menu_task_name'] = task_name

    await query.edit_message_text(prompt_text, reply_markup=keyboards.get_back_button(back_button_cb), parse_mode=ParseMode.HTML)
    return new_state

async def button_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await is_admin(update): return ConversationHandler.END
    query = update.callback_query
    route = query.data
    parts = route.split(':')

    active_user_tasks = {name: data for name, data in active_tasks.items() if name != 'proxy_checker'}

    if active_user_tasks:
        BLOCKED_DURING_TASKS = [
            'accounts_delete_all_prompt', 
            'accounts_delete_by_status_prompt', 
            'clear_file:blacklist'
        ]
        if any(blocked_part in route for blocked_part in BLOCKED_DURING_TASKS):
            await query.answer(
                "❌ Есть активные задачи. Массовое удаление ограничено до их остановки.",
                show_alert=True
            )
            return ConversationHandler.END
    
    try:
        await query.answer()
    except BadRequest as e:
        if "Query is too old" in str(e):
            pass
        else:
            logger.error(f"Ошибка в button_router при query.answer(): {e}")
            return ConversationHandler.END
    
    if 'input_type' in context.user_data:
        context.user_data['input_type'] = None

    if route == 'menu_accounts': await main_menu_handler(update, context, *keyboards.get_accounts_menu())
    elif route == 'menu_settings': await main_menu_handler(update, context, *keyboards.get_settings_menu())

    elif route == 'accounts_add_zip':
        return await request_input_from_user(update, context, "Пожалуйста, отправьте мне <code>.zip</code> архив с файлами <code>.session</code> и (опционально) <code>.json</code>.", 'sessions_zip', 'menu_accounts', AWAIT_GLOBAL_INPUT)

    elif route == 'accounts_list_all' or route.startswith('accounts_list_page:'):
        page = int(parts[1]) if len(parts) > 1 else 1
        accounts = storage_manager.list_accounts()
        statuses = storage_manager.load_account_statuses()
        
        active_account_names = set()
        if active_user_tasks:
            all_tasks = storage_manager.load_tasks()
            for task_name in active_user_tasks.keys():
                if task_name in all_tasks:
                    active_account_names.update(all_tasks[task_name].get('accounts', []))

        await main_menu_handler(update, context, *keyboards.get_accounts_list_menu(accounts, statuses, active_account_names, page=page))

    elif route.startswith('accounts_delete:'):
        active_account_names = set()
        if active_user_tasks:
            all_tasks = storage_manager.load_tasks()
            for task_name in active_user_tasks.keys():
                if task_name in all_tasks:
                    active_account_names.update(all_tasks[task_name].get('accounts', []))
        
        acc_to_delete = parts[1]
        
        if acc_to_delete in active_account_names:
            await query.answer("❌ Этот аккаунт сейчас занят в задаче и не может быть удален.", show_alert=True)
            return ConversationHandler.END

        if not storage_manager.delete_account(acc_to_delete):
            await query.answer("❌ Не удалось удалить аккаунт. Файл сессии используется другим процессом.", show_alert=True)
            return ConversationHandler.END
        
        accounts = storage_manager.list_accounts()
        statuses = storage_manager.load_account_statuses()
        await main_menu_handler(update, context, *keyboards.get_accounts_list_menu(accounts, statuses, active_account_names, page=1))

    elif route == 'accounts_delete_all_prompt': await main_menu_handler(update, context, *keyboards.get_delete_all_confirmation_menu())
    
    elif route.startswith('accounts_delete_by_status_prompt'):
        status_key = route.split(':')[1] if len(route.split(':')) > 1 else 'frozen_invalid'
        await main_menu_handler(update, context, *keyboards.get_delete_by_status_confirmation_menu(status_key))
    
    elif route == 'accounts_delete_all_confirm':
        accounts = storage_manager.list_accounts()
        for acc in accounts: storage_manager.delete_account(acc)
        await main_menu_handler(update, context, *keyboards.get_accounts_menu())

    elif route.startswith('accounts_delete_by_status_confirm'):
        status_key = route.split(':')[1]
        
        statuses_to_delete = []
        if status_key == 'spamblock_temporary':
            statuses_to_delete = ['spamblock_temporary']
        elif status_key == 'spamblock_permanent':
            statuses_to_delete = ['spamblock_permanent']
        elif status_key == 'all_spamblock':
            statuses_to_delete = ['spamblock_temporary', 'spamblock_permanent']
        elif status_key == 'frozen_invalid':
             statuses_to_delete = ['invalid', 'frozen']

        if statuses_to_delete:
            deleted_count = storage_manager.delete_accounts_by_status(statuses_to_delete)
            await query.answer(f"🗑️ Удалено {deleted_count} аккаунтов.", show_alert=True)
        
        accounts = storage_manager.list_accounts()
        statuses = storage_manager.load_account_statuses()
        active_account_names = set()
        await main_menu_handler(update, context, *keyboards.get_accounts_list_menu(accounts, statuses, active_account_names, page=1))

    elif route == 'clear_file:blacklist':
        storage_manager.clear_blacklist()
        await main_menu_handler(update, context, *keyboards.get_settings_menu())

    elif route == 'proxy_menu': await main_menu_handler(update, context, *keyboards.get_proxy_menu())
    elif route == 'proxy_add_text': return await request_input_from_user(update, context, "Отправьте список прокси текстом.", 'proxy_text', 'proxy_menu', AWAIT_GLOBAL_INPUT)
    elif route == 'proxy_add_file': return await request_input_from_user(update, context, "Отправьте .txt файл с прокси.", 'proxy_file', 'proxy_menu', AWAIT_GLOBAL_INPUT)
    elif route.startswith('proxy_list_page:'):
        page = int(parts[1])
        proxies = storage_manager.load_settings().get('proxies', [])
        await main_menu_handler(update, context, *keyboards.get_proxy_list_menu(proxies, page, storage_manager.load_proxy_statuses()))
    
    elif route.startswith('proxy_delete:') or route == 'proxy_delete_nonworking' or route == 'proxy_clear_all':
        if active_user_tasks:
            await query.answer("❌ Нельзя изменять список прокси, пока есть активные задачи.", show_alert=True)
            return ConversationHandler.END
        
        settings = storage_manager.load_settings()
        proxies = settings.get('proxies', [])
        statuses = settings.get('proxy_statuses', {})

        if route.startswith('proxy_delete:'):
            index_to_delete = int(parts[1])
            if 0 <= index_to_delete < len(proxies):
                deleted_proxy = proxies.pop(index_to_delete)
                if deleted_proxy in statuses:
                    del statuses[deleted_proxy]
        elif route == 'proxy_delete_nonworking':
            working_proxies = [p for p in proxies if statuses.get(p, {}).get('status') == 'working']
            deleted_count = len(proxies) - len(working_proxies)
            proxies = working_proxies
            statuses = {p: s for p, s in statuses.items() if p in working_proxies}
            await query.answer(f"🗑️ Удалено {deleted_count} нерабочих прокси.", show_alert=True)
        elif route == 'proxy_clear_all':
            proxies = []
            statuses = {}

        settings['proxies'] = proxies
        settings['proxy_statuses'] = statuses
        storage_manager.save_settings(settings)
        
        text, markup = keyboards.get_proxy_list_menu(proxies, 1, statuses)
        await main_menu_handler(update, context, text, markup)

    elif route == 'proxy_check_all':
        if 'proxy_checker' in active_tasks and active_tasks.get('proxy_checker'):
            await query.answer("❌ Проверка прокси уже запущена!", show_alert=True)
            return ConversationHandler.END
        asyncio.create_task(run_proxy_checker(update, context))
    
    elif route == 'proxy_check_stop':
        if 'proxy_checker' in active_tasks and active_tasks.get('proxy_checker'):
            active_tasks['proxy_checker']['cancel_event'].set()
            await query.answer("🛑 Останавливаю проверку...")

    elif route == 'menu_tasks': await main_menu_handler(update, context, *keyboards.get_tasks_menu())
    elif route == 'tasks_list': await main_menu_handler(update, context, *keyboards.get_task_list_menu(storage_manager.load_tasks(), active_user_tasks.keys()))

    elif route == 'tasks_create':
        context.user_data['message_to_edit'] = query.message.message_id
        await query.edit_message_text("Введите название для новой задачи. Или нажмите кнопку, чтобы сгенерировать случайное.",
            reply_markup=InlineKeyboardMarkup([[keyboards.InlineKeyboardButton("🎲 Сгенерировать", callback_data='tasks_create_generate')],
                                               [keyboards.InlineKeyboardButton("⬅️ Назад", callback_data='menu_tasks')]]))
        return AWAIT_TASK_NAME

    elif route == 'tasks_create_generate':
        task_name = f"Задача-{random.randint(1000, 9999)}"
        while storage_manager.get_task(task_name):
            task_name = f"Задача-{random.randint(1000, 9999)}"
        storage_manager.create_task(task_name)
        await main_menu_handler(update, context, *keyboards.get_task_list_menu(storage_manager.load_tasks(), active_user_tasks.keys()))

    elif route.startswith('task_manage:'):
        task_name = parts[1]
        task_data = storage_manager.get_task(task_name)
        if task_data:
            await main_menu_handler(update, context, *keyboards.get_task_manage_menu(task_name, task_data, task_name in active_tasks))

    elif route.startswith('task_settings_menu:'):
        task_name = parts[1]
        task_data = storage_manager.get_task(task_name)
        if task_data:
            await main_menu_handler(update, context, *keyboards.get_task_settings_menu(task_name, task_data.get('settings', {})))

    elif route.startswith('task_toggle_setting:'):
        _, setting_key, task_name = parts
        tasks = storage_manager.load_tasks()
        task_data = tasks.get(task_name)
        if not task_data: return ConversationHandler.END

        current_value = task_data['settings'].get(setting_key, False)
        
        if setting_key == 'reply_in_pm' and not current_value:
            pm_replies = storage_manager.read_task_multiline_messages(task_name, 'pm_replies')
            if not pm_replies:
                await query.answer("❌ Сначала добавьте сообщения для ответов в ЛС через меню 'Файлы задачи'!", show_alert=True)
                return ConversationHandler.END

        task_data['settings'][setting_key] = not current_value
        storage_manager.save_tasks(tasks)
        await main_menu_handler(update, context, *keyboards.get_task_settings_menu(task_name, task_data['settings']))

    elif route.startswith('task_files_menu:'):
        task_name = parts[1]
        await main_menu_handler(update, context, *keyboards.get_task_files_menu(task_name))
    
    elif route.startswith('task_set:2fa_password:'):
        task_name = parts[2]
        prompt = f"Введите пароль 2FA для задачи `{html.escape(task_name)}`. Он будет сохранен и использован для установки/снятия 2FA."
        return await request_input_from_user(update, context, prompt, f'task_setting:2fa_password', f'task_settings_menu:{task_name}', AWAIT_TASK_INPUT, task_name=task_name)

    elif route.startswith('task_set:workers:'):
        task_name = parts[2]
        prompt = f"Введите лимит воркеров для задачи `{html.escape(task_name)}`. Помните об общей нагрузке на сервер!"
        return await request_input_from_user(update, context, prompt, f'task_setting:workers', f'task_settings_menu:{task_name}', AWAIT_TASK_INPUT, task_name=task_name)

    elif route.startswith('task_set:interval:'):
        task_name = parts[2]
        prompt = f"Введите интервал для задачи `{html.escape(task_name)}` в формате ОТ-ДО (например, `30-90`)."
        return await request_input_from_user(update, context, prompt, f'task_setting:interval', f'task_settings_menu:{task_name}', AWAIT_TASK_INPUT, task_name=task_name)

    elif route.startswith('task_set:fwd_post:'):
        task_name = parts[2]
        prompt = f"Отправьте ссылку на пост для задачи `{html.escape(task_name)}`."
        return await request_input_from_user(update, context, prompt, f'task_setting:fwd_post', f'task_settings_menu:{task_name}', AWAIT_TASK_INPUT, task_name=task_name)
    
    elif route.startswith('task_set_target_menu:'):
        task_name = parts[1]
        task_data = storage_manager.get_task(task_name)
        if task_data:
            await main_menu_handler(update, context, *keyboards.get_task_broadcast_target_menu(task_name, task_data.get('settings', {}).get('broadcast_target')))

    elif route.startswith('task_set_target:'):
        _, target, task_name = parts
        tasks = storage_manager.load_tasks()
        if task_name in tasks:
            tasks[task_name]['settings']['broadcast_target'] = target
            storage_manager.save_tasks(tasks)
            await main_menu_handler(update, context, *keyboards.get_task_settings_menu(task_name, tasks[task_name]['settings']))

    elif route.startswith('task_upload:'):
        _, file_key, task_name = parts
        prompt = f"Пришлите `.txt` файл для `{file_key}` задачи `{html.escape(task_name)}`."
        if file_key in ['avatars', 'channel_avatars']:
            prompt = f"Пришлите `.zip` архив с аватарками для `{file_key}` задачи `{html.escape(task_name)}`."
        return await request_input_from_user(update, context, prompt, f'task_file:{file_key}', f'task_files_menu:{task_name}', AWAIT_TASK_INPUT, task_name=task_name)

    elif route.startswith('task_clear:'):
        _, file_key, task_name = parts
        storage_manager.clear_task_file_or_dir(task_name, file_key)
        await main_menu_handler(update, context, *keyboards.get_task_files_menu(task_name))
        
    elif route.startswith('task_action:'):
        task_name = parts[1]
        await main_menu_handler(update, context, *keyboards.get_task_action_menu(task_name))

    elif route.startswith('task_set_action:'):
        _, task_name, action_type = route.split(':', 2)
        tasks = storage_manager.load_tasks()
        if task_name in tasks:
            tasks[task_name]['type'] = action_type
            storage_manager.save_tasks(tasks)
            await main_menu_handler(update, context, *keyboards.get_task_manage_menu(task_name, tasks[task_name], False))

    elif route.startswith('task_accounts:'):
        _, task_name, page = parts
        task_data = storage_manager.get_task(task_name)
        context.user_data['menu_task_name'] = task_name
        
        all_tasks = storage_manager.load_tasks()
        globally_assigned_accounts = set()
        for name, data in all_tasks.items():
            if name != task_name:
                globally_assigned_accounts.update(data.get('accounts', []))
        
        filter_needed = task_data.get('type') not in ['check_all', 'clean_account']
        await main_menu_handler(update, context, *keyboards.get_task_accounts_menu(
            task_name, task_data, storage_manager.list_accounts(), storage_manager.load_account_statuses(), globally_assigned_accounts, int(page), filter_needed))

    elif route.startswith('task_toggle_account:'):
        task_name = context.user_data.get('menu_task_name')
        if not task_name: return ConversationHandler.END
        
        _, acc_name, page = parts
        tasks = storage_manager.load_tasks()
        assigned_accounts = tasks[task_name].get('accounts', [])
        if acc_name in assigned_accounts:
            assigned_accounts.remove(acc_name)
        else:
            assigned_accounts.append(acc_name)
        tasks[task_name]['accounts'] = assigned_accounts
        storage_manager.save_tasks(tasks)
        
        all_tasks = storage_manager.load_tasks()
        globally_assigned_accounts = set()
        for name, data in all_tasks.items():
            if name != task_name:
                globally_assigned_accounts.update(data.get('accounts', []))
        filter_needed = task_data.get('type') not in ['check_all', 'clean_account']
        await main_menu_handler(update, context, *keyboards.get_task_accounts_menu(
            task_name, tasks[task_name], storage_manager.list_accounts(), storage_manager.load_account_statuses(), globally_assigned_accounts, int(page), filter_needed))

    elif route.startswith('task_toggle_all:'):
        task_name = context.user_data.get('menu_task_name')
        if not task_name: return ConversationHandler.END

        action = parts[1]
        tasks = storage_manager.load_tasks()
        task_data = tasks.get(task_name)
        
        all_tasks = storage_manager.load_tasks()
        globally_assigned_accounts = set()
        for name, data in all_tasks.items():
            if name != task_name:
                globally_assigned_accounts.update(data.get('accounts', []))
        
        available_accounts = {acc for acc in storage_manager.list_accounts() if acc not in globally_assigned_accounts}
        
        if task_data.get('type') not in ['check_all', 'clean_account']:
            statuses = storage_manager.load_account_statuses()
            target_accounts = {acc for acc in available_accounts if statuses.get(acc) == 'valid'}
        else:
            target_accounts = available_accounts
        
        current_accounts = set(task_data.get('accounts', []))
        if action == 'select':
            updated_accounts = list(current_accounts.union(target_accounts))
        else:
            updated_accounts = list(current_accounts.difference(target_accounts))
        tasks[task_name]['accounts'] = updated_accounts
        storage_manager.save_tasks(tasks)
        
        filter_needed = task_data.get('type') not in ['check_all', 'clean_account']
        await main_menu_handler(update, context, *keyboards.get_task_accounts_menu(
            task_name, tasks[task_name], storage_manager.list_accounts(), storage_manager.load_account_statuses(), globally_assigned_accounts, 1, filter_needed))
        
    elif route.startswith('task_delete_prompt:'):
        task_name = parts[1]
        await main_menu_handler(update, context, *keyboards.get_task_delete_confirmation_menu(task_name))
        
    elif route.startswith('task_delete_confirm:'):
        task_name = parts[1]
        if storage_manager.delete_task(task_name):
            await main_menu_handler(update, context, *keyboards.get_task_list_menu(storage_manager.load_tasks(), active_user_tasks.keys()))

    elif route.startswith('task_start:'):
        task_name = parts[1]
        task_data = storage_manager.get_task(task_name)

        if not task_data.get('type'):
            await query.answer("❌ Не выбрано действие для задачи!", show_alert=True)
            return ConversationHandler.END
        if not task_data.get('accounts'):
            await query.answer("❌ К задаче не привязано ни одного аккаунта!", show_alert=True)
            return ConversationHandler.END
        
        password = task_data.get('settings', {}).get('two_fa_password')
        if task_data['type'] in ['set_2fa', 'remove_2fa'] and not password:
            await query.answer("❌ Пароль 2FA не задан в настройках задачи!", show_alert=True)
            return ConversationHandler.END

        asyncio.create_task(execute_task(update, context, task_name, task_data, password=password))
        await main_menu_handler(update, context, *keyboards.get_task_manage_menu(task_name, task_data, True))

    elif route.startswith('task_stop:'):
        task_name = parts[1]
        if task_name in active_tasks:
            active_tasks[task_name]['cancel_event'].set()
        task_data = storage_manager.get_task(task_name)
        if task_data:
            await main_menu_handler(update, context, *keyboards.get_task_manage_menu(task_name, task_data, False))

    elif route.startswith('task_report:'):
        await show_task_report(update, context, parts[1])
        
    elif route.startswith('task_show_saved_report:'):
        task_name = parts[1]
        task_data = storage_manager.get_task(task_name)
        if task_data and task_data.get('report'):
            report_file = io.BytesIO(task_data['report'].encode('utf-8'))
            report_file.name = f'final_report_{html.escape(task_name)}.txt'
            await context.bot.send_document(chat_id=query.message.chat_id, document=report_file, caption=f"Сохраненный отчет по задаче '<code>{html.escape(task_name)}</code>'", parse_mode=ParseMode.HTML, reply_markup=keyboards.get_close_keyboard())
        else:
            await query.answer("❌ Сохраненный отчет не найден.", show_alert=True)

    elif route == 'close_message':
        await close_message_handler(update, context)

    return ConversationHandler.END

async def handle_task_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    task_name = update.message.text.strip()
    if not task_name:
        await update.message.reply_text("Название не может быть пустым.")
        return AWAIT_TASK_NAME
    if storage_manager.get_task(task_name):
        await update.message.reply_text("Задача с таким именем уже существует.")
        return AWAIT_TASK_NAME

    storage_manager.create_task(task_name)
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except: pass
    
    message_id_to_edit = context.user_data.get('message_to_edit')
    if message_id_to_edit:
        text, markup = keyboards.get_task_list_menu(storage_manager.load_tasks(), active_tasks.keys())
        await context.bot.edit_message_text(text, chat_id=update.effective_chat.id, message_id=message_id_to_edit, reply_markup=markup, parse_mode=ParseMode.HTML)
    
    context.user_data.clear()
    return ConversationHandler.END

async def global_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    input_type = context.user_data.get('input_type')
    if not input_type: return ConversationHandler.END

    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except: pass
    
    settings = storage_manager.load_settings()
    
    if update.message.text:
        user_text = update.message.text.strip()
        if input_type == 'proxy_text':
            proxies = [p.strip() for p in user_text.splitlines() if p.strip()]
            settings.setdefault('proxies', []).extend(proxies)
            settings['proxies'] = sorted(list(set(settings['proxies'])))

    elif update.message.document:
        file = await update.message.document.get_file()
        filename = update.message.document.file_name
        temp_filepath = os.path.join(storage_manager.BACKUP_DIR, filename)
        await file.download_to_drive(temp_filepath)
        
        if input_type == 'sessions_zip':
            storage_manager.unpack_zip(temp_filepath, storage_manager.SESSIONS_DIR)
        elif input_type == 'proxy_file':
            with open(temp_filepath, 'r', encoding='utf-8') as f:
                proxies = [line.strip() for line in f if line.strip()]
            settings.setdefault('proxies', []).extend(proxies)
            settings['proxies'] = sorted(list(set(settings['proxies'])))
    
    storage_manager.save_settings(settings)
    
    message_id_to_edit = context.user_data.get('message_to_edit')
    if message_id_to_edit:
        if input_type.startswith('proxy'): 
            text, markup = keyboards.get_proxy_menu()
        else: 
            text, markup = keyboards.get_accounts_menu()
        try:
            await context.bot.edit_message_text(text, chat_id=update.effective_chat.id, message_id=message_id_to_edit, reply_markup=markup, parse_mode=ParseMode.HTML)
        except: pass

    context.user_data.clear()
    return ConversationHandler.END

async def task_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    input_type = context.user_data.get('input_type')
    task_name = context.user_data.get('menu_task_name')
    if not input_type or not task_name: return ConversationHandler.END

    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except: pass
    
    tasks = storage_manager.load_tasks()
    task_data = tasks.get(task_name)
    if not task_data: return ConversationHandler.END

    input_class, key = input_type.split(':', 1)

    if input_class == 'task_setting' and update.message.text:
        user_text = update.message.text.strip()
        if key == '2fa_password':
            task_data['settings']['two_fa_password'] = user_text
        elif key == 'workers':
            try:
                task_data['settings']['concurrent_workers'] = int(user_text)
            except: pass
        elif key == 'interval':
            try:
                from_val, to_val = map(int, user_text.split('-'))
                task_data['settings']['broadcast_interval'] = [from_val, to_val]
            except: pass
        elif key == 'fwd_post':
            task_data['settings']['forward_post_link'] = user_text
    
    elif input_class == 'task_file' and update.message.document:
        file = await update.message.document.get_file()
        temp_filepath = os.path.join(storage_manager.BACKUP_DIR, update.message.document.file_name)
        await file.download_to_drive(temp_filepath)
        
        target_path = storage_manager.get_task_file_path(task_name, key)
        if key in ['avatars', 'channel_avatars']:
            storage_manager.unpack_zip(temp_filepath, target_path)
        elif target_path:
            shutil.copy(temp_filepath, target_path)

    storage_manager.save_tasks(tasks)

    message_id_to_edit = context.user_data.get('message_to_edit')
    if message_id_to_edit:
        if input_class == 'task_setting':
            text, markup = keyboards.get_task_settings_menu(task_name, task_data['settings'])
        else:
            text, markup = keyboards.get_task_files_menu(task_name)
        try:
            await context.bot.edit_message_text(text, chat_id=update.effective_chat.id, message_id=message_id_to_edit, reply_markup=markup, parse_mode=ParseMode.HTML)
        except: pass

    context.user_data.clear()
    return ConversationHandler.END

async def execute_task(update: Update, context: ContextTypes.DEFAULT_TYPE, task_name: str, task_data: dict, password: str = None):
    query = update.callback_query or update
    task_type = task_data['type']
    accounts = task_data['accounts']
    task_name_safe = html.escape(task_name)
    
    tasks = storage_manager.load_tasks()
    tasks[task_name]['status'] = 'running'
    storage_manager.save_tasks(tasks)

    global_settings = storage_manager.load_settings()
    proxies = global_settings.get('proxies', [])
    random.shuffle(proxies)
    proxy_queue = asyncio.Queue()
    for p in proxies: proxy_queue.put_nowait(p)
    file_lock = asyncio.Lock()
    cancel_event = asyncio.Event()
    
    task_worker_limit = task_data.get('settings', {}).get('concurrent_workers', 5)
    task_semaphore = asyncio.Semaphore(task_worker_limit)
    
    active_tasks[task_name] = {
        "cancel_event": cancel_event, "tasks": [], "progress_log": {acc: "в очереди..." for acc in accounts},
    }
    
    shared_work_queue = asyncio.Queue()
    if task_type == 'join_chats':
        all_chats = storage_manager.read_task_text_file_lines(task_name, 'chats')
        for chat in all_chats: await shared_work_queue.put(chat)

    async def progress_callback(text):
        if task_name not in active_tasks: return
        session_name = text.split(':')[0]
        if session_name in active_tasks[task_name]['progress_log']:
            status = text.split(':', 1)[1] if ':' in text else text
            active_tasks[task_name]['progress_log'][session_name] = status.strip()
    
    task_futures = []
    for acc_name in accounts:
        worker = TelethonWorker(acc_name, proxy_queue, file_lock, SETTINGS_LOCK, progress_callback, cancel_event, task_semaphore, task_name, task_data)
        task_parts = task_type.split(':')
        base_task = task_parts[0]
        coro_to_run = None
        
        if base_task == 'check_all': 
            coro_to_run = worker.run_task(worker.task_check_account, change_name=False, change_avatar=False, change_lastname=False, perform_spam_check=True)
        elif base_task == 'change_profile':
            change = task_parts[1]
            coro_to_run = worker.run_task(worker.task_check_account, 
                                          change_name=(change in ['name', 'name_last', 'name_avatar', 'all']),
                                          change_lastname=(change in ['lastname', 'name_last', 'last_avatar', 'all']),
                                          change_avatar=(change in ['avatar', 'name_avatar', 'last_avatar', 'all']),
                                          perform_spam_check=False)
        elif base_task == 'create_channel': coro_to_run = worker.run_task(worker.task_create_channel)
        elif base_task == 'join_chats': coro_to_run = worker.run_task(worker.task_join_chats, work_queue=shared_work_queue)
        elif base_task == 'start_broadcast': coro_to_run = worker.run_task(worker.task_autobroadcast)
        elif base_task == 'delete_avatars': coro_to_run = worker.run_task(worker.task_delete_avatars)
        elif base_task == 'delete_lastnames': coro_to_run = worker.run_task(worker.task_delete_lastnames)
        elif base_task == 'set_2fa': coro_to_run = worker.run_task(worker.task_set_2fa, password=password)
        elif base_task == 'remove_2fa': coro_to_run = worker.run_task(worker.task_remove_2fa, password=password)
        elif base_task == 'terminate_sessions': coro_to_run = worker.run_task(worker.task_terminate_sessions)
        elif base_task == 'reauthorize': coro_to_run = worker.run_task(worker.task_reauthorize_account)
        elif base_task == 'clean_account': coro_to_run = worker.run_task(worker.task_clean_account)

        if coro_to_run: task_futures.append(asyncio.create_task(coro_to_run))
        
    active_tasks[task_name]["tasks"] = task_futures
    if task_futures:
        await asyncio.gather(*task_futures, return_exceptions=True)

    final_log_for_file = "\n".join([f"{acc}: {status}" for acc, status in active_tasks[task_name]['progress_log'].items()])
    
    if task_type == 'check_all':
        current_statuses = storage_manager.load_account_statuses()
        for acc_name, result_string in active_tasks[task_name]['progress_log'].items():
            if result_string.startswith("✅ Валиден"):
                current_statuses[acc_name] = 'valid'
            elif "Спам-блок (до" in result_string:
                current_statuses[acc_name] = 'spamblock_temporary'
            elif "Спам-блок (постоянный)" in result_string:
                current_statuses[acc_name] = 'spamblock_permanent'
            elif "Заморожен (ToS)" in result_string:
                current_statuses[acc_name] = 'frozen'
            else:
                current_statuses[acc_name] = 'invalid'
        storage_manager.save_account_statuses(current_statuses)
        logger.info(f"Статусы аккаунтов для задачи '{task_name}' обновлены.")
    
    tasks = storage_manager.load_tasks()
    if task_name in tasks:
        tasks[task_name]['status'] = 'stopped'
        tasks[task_name]['report'] = final_log_for_file
        storage_manager.save_tasks(tasks)
    
    is_finite_task = task_type != 'start_broadcast'
    caption_text = ""
    if cancel_event.is_set(): caption_text = f"🛑 <b>Задача '<code>{task_name_safe}</code>' была остановлена.</b>"
    elif is_finite_task: caption_text = f"✅ <b>Задача '<code>{task_name_safe}</code>' завершила работу.</b>"
    
    if caption_text and hasattr(query, 'message'):
        await context.bot.send_message(chat_id=query.message.chat_id, text=caption_text, parse_mode=ParseMode.HTML, reply_markup=keyboards.get_task_completion_keyboard(task_name))
    
    active_tasks.pop(task_name, None)

async def show_task_report(update: Update, context: ContextTypes.DEFAULT_TYPE, task_name: str):
    task_info = active_tasks.get(task_name)
    if not task_info:
        await update.callback_query.answer("Задача не активна. Отчет недоступен.", show_alert=True)
        return
    log_text = f"⚙️ Текущий отчет по задаче: {html.escape(task_name)}\n\n" + "\n".join([f"{a}: {s}" for a, s in task_info['progress_log'].items()])
    report_file = io.BytesIO(log_text.encode('utf-8'))
    report_file.name = f'realtime_report_{html.escape(task_name)}.txt'
    await context.bot.send_document(chat_id=update.effective_chat.id, document=report_file, caption=f"Текущий отчет по задаче '<code>{html.escape(task_name)}</code>'.", parse_mode=ParseMode.HTML, reply_markup=keyboards.get_close_keyboard())

async def close_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.callback_query.message.delete()
    except Exception:
        await update.callback_query.answer()

def main() -> None:
    storage_manager.initialize_storage()
    
    tasks = storage_manager.load_tasks()
    updated = False
    for task_name, task_data in tasks.items():
        if task_data.get('status') == 'running':
            tasks[task_name]['status'] = 'stopped'
            updated = True
    if updated:
        storage_manager.save_tasks(tasks)

    application = Application.builder().token(config.BOT_TOKEN).build()
    
    task_creation_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_router, pattern="^tasks_create$")],
        states={AWAIT_TASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_task_name_input)]},
        fallbacks=[CallbackQueryHandler(go_to_main_menu, pattern="^menu_main$")], per_message=False)
    
    global_input_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_router, pattern="^(proxy_add|accounts_add_zip)")],
        states={AWAIT_GLOBAL_INPUT: [MessageHandler(filters.TEXT | filters.Document.ALL, global_input_handler)]},
        fallbacks=[CallbackQueryHandler(go_to_main_menu, pattern="^menu_main$")], per_message=False)

    task_input_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_router, pattern="^(task_set:|task_upload:|task_toggle_setting:)")],
        states={AWAIT_TASK_INPUT: [MessageHandler(filters.TEXT | filters.Document.ALL, task_input_handler)]},
        fallbacks=[CallbackQueryHandler(go_to_main_menu, pattern="^menu_main$")], per_message=False)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(go_to_main_menu, pattern="^menu_main$"))
    
    application.add_handler(task_creation_conv)
    application.add_handler(global_input_conv)
    application.add_handler(task_input_conv)
    
    application.add_handler(CallbackQueryHandler(button_router))
    
    logger.info("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()