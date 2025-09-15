# keyboards.py

import html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import storage_manager

ACCOUNTS_PER_PAGE = 20
PROXIES_PER_PAGE = 10

TASK_STATUS_EMOJI = {
    'running': '▶️',
    'stopped': '⏹️'
}

TASK_TYPE_NAMES = {
    'check_all': '✅ Проверка аккаунтов',
    # Авторег специальные задачи
    'autoreg_warmup': '🔥 Прогрев новых аккаунтов',
    'autoreg_gentle_join': '🌱 Мягкое вступление (авторег)',
    'autoreg_gentle_spam': '🌿 Мягкий спам (авторег)',
    'autoreg_setup_profile': '👤 Настройка профиля (авторег)',
    # Обычные задачи смены профиля
    'change_profile:name': '👤 Смена имен',
    'change_profile:lastname': '📜 Смена фамилий',
    'change_profile:avatar': '🖼 Смена аватаров',
    'change_profile:bio': '📝 Смена описания профиля',
    'change_profile:name_last': '👤+📜 Имена и Фамилии',
    'change_profile:name_avatar': '👤+🖼 Имена и Аватары',
    'change_profile:last_avatar': '📜+🖼 Фамилии и Аватары',
    'change_profile:all': '👤+📜+🖼+📝 Всё вместе',
    # Каналы
    'create_channel': '➕ Создание каналов',
    'update_channel_design': '🎨 Смена оформления каналов',
    # Стандартные операции
    'join_chats': '🚀 Вступление в чаты',
    'start_broadcast': '📣 Рассылка (устаревшая)',
    # Спам система
    'spam_chats': '💬 Спам по чатам',
    'spam_channels': '📢 Спам по каналам', 
    'spam_both': '💬📢 Спам по чатам + каналам',
    'spam_dm': '📨 Спам по личкам (⚠️ РИСК СЛЁТА)',
    'spam_dm_existing': '📬 Спам по существующим ЛС',
    # Техническое
    'delete_avatars': '🗑️ Удаление аватаров',
    'delete_lastnames': '🗑️ Удаление фамилий',
    'set_2fa': '🔐 Установить 2FA',
    'remove_2fa': '🔓 Удалить 2FA',
    'terminate_sessions': '💨 Выкинуть сессии',
    'reauthorize': '🔄 Переавторизация',
    'clean_account': '🧹 Полная зачистка аккаунта'
}

ACCOUNT_STATUS_EMOJI = {
    'valid': '✅',
    'frozen': '💀',
    'invalid': '❌',
    'unknown': '❔',
    'busy': '⚙️',
    'spamblock_temporary': '🥶',
    'spamblock_permanent': '🥶'
}

def get_main_menu():
    text = "🤖 <b>Главное меню</b>"
    keyboard = [
        [InlineKeyboardButton("💻 Аккаунты", callback_data='menu_accounts'), InlineKeyboardButton("⚙️ Глобальные настройки", callback_data='menu_settings')],
        [InlineKeyboardButton("▶️ Задачи", callback_data='menu_tasks')]
    ]
    return text, InlineKeyboardMarkup(keyboard)

def get_accounts_menu():
    accounts_count = len(storage_manager.list_accounts())
    text = f"В базе: {accounts_count} аккаунтов."
    keyboard = [
        [InlineKeyboardButton("➕ Добавить (ZIP)", callback_data='accounts_add_zip')],
        [InlineKeyboardButton("📋 Мои аккаунты", callback_data='accounts_list_all')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='menu_main')]
    ]
    return text, InlineKeyboardMarkup(keyboard)

def get_accounts_list_menu(accounts, statuses, active_accounts, page=1):
    total_accounts = len(accounts)
    if not accounts:
        return "Нет добавленных аккаунтов.", InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Назад", callback_data='menu_accounts')]
        ])

    total_pages = (total_accounts + ACCOUNTS_PER_PAGE - 1) // ACCOUNTS_PER_PAGE
    page = max(1, min(page, total_pages))
    start_index = (page - 1) * ACCOUNTS_PER_PAGE
    end_index = start_index + ACCOUNTS_PER_PAGE
    accounts_on_page = accounts[start_index:end_index]
    
    keyboard = []
    for acc_name in accounts_on_page:
        if acc_name in active_accounts:
            emoji = ACCOUNT_STATUS_EMOJI['busy']
        else:
            status_key = statuses.get(acc_name, 'unknown')
            emoji = ACCOUNT_STATUS_EMOJI.get(status_key, '❔')
        
        keyboard.append([InlineKeyboardButton(f"{emoji} {acc_name}", callback_data=f'accounts_delete:{acc_name}')])
    
    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(InlineKeyboardButton("⬅️", callback_data=f'accounts_list_page:{page-1}'))
    pagination_buttons.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data='none'))
    if page < total_pages:
        pagination_buttons.append(InlineKeyboardButton("➡️", callback_data=f'accounts_list_page:{page+1}'))
    
    if pagination_buttons:
        keyboard.append(pagination_buttons)
    
    keyboard.append([
        InlineKeyboardButton("🗑️ Удалить временный спамблок", callback_data='accounts_delete_by_status_prompt:spamblock_temporary'),
    ])
    keyboard.append([
        InlineKeyboardButton("🗑️ Удалить вечный спамблок", callback_data='accounts_delete_by_status_prompt:spamblock_permanent'),
    ])
    keyboard.append([
        InlineKeyboardButton("🗑️ Удалить все спамблоки", callback_data='accounts_delete_by_status_prompt:all_spamblock'),
    ])
    
    keyboard.append([InlineKeyboardButton("💀 Удалить забаненные (ToS) / невалидные", callback_data='accounts_delete_by_status_prompt:frozen_invalid')])
    keyboard.append([InlineKeyboardButton("🗑️ Удалить все аккаунты", callback_data='accounts_delete_all_prompt')])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='menu_accounts')])
    
    text = (
        f"<b>Всего аккаунтов: {total_accounts} | Стр. {page}/{total_pages}</b>\n"
        f"Нажмите на аккаунт, чтобы удалить его.\n\n"
        f"<b>Легенда статусов:</b>\n"
        f"<b>{ACCOUNT_STATUS_EMOJI['valid']}</b> - Валидный\n"
        f"<b>{ACCOUNT_STATUS_EMOJI['spamblock_temporary']}</b> - Спамблок (врем./вечн.)\n"
        f"<b>{ACCOUNT_STATUS_EMOJI['frozen']}</b> - Забанен (ToS)\n"
        f"<b>{ACCOUNT_STATUS_EMOJI['invalid']}</b> - Невалидный (ошибка авторизации)\n"
        f"<b>{ACCOUNT_STATUS_EMOJI['busy']}</b> - Занят в задаче"
    )
    return text, InlineKeyboardMarkup(keyboard)

def get_delete_all_confirmation_menu():
    text = "❓ <b>Вы уверены, что хотите удалить ВСЕ аккаунты?</b>\n\nЭто действие необратимо."
    keyboard = [
        [InlineKeyboardButton("✅ Да, удалить все", callback_data='accounts_delete_all_confirm')],
        [InlineKeyboardButton("⬅️ Нет, вернуться назад", callback_data='accounts_list_all')]
    ]
    return text, InlineKeyboardMarkup(keyboard)

def get_delete_by_status_confirmation_menu(status_key):
    status_map = {
        'spamblock_temporary': "<b>временным спам-блоком</b>",
        'spamblock_permanent': "<b>вечным спам-блоком</b>",
        'all_spamblock': "со <b>всеми видами спам-блока</b>",
        'frozen_invalid': "<b>забаненные (ToS)</b> и <b>невалидные</b>"
    }
    text_part = status_map.get(status_key, "выбранные")
    text = f"❓ <b>Вы уверены, что хотите удалить ВСЕ аккаунты с {text_part} статусом?</b>"
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, удалить", callback_data=f'accounts_delete_by_status_confirm:{status_key}')],
        [InlineKeyboardButton("⬅️ Нет, вернуться назад", callback_data='accounts_list_all')]
    ]
    return text, InlineKeyboardMarkup(keyboard)

def get_settings_menu():
    settings = storage_manager.load_settings()
    proxies_count = len(settings.get('proxies', []))
    blacklist_count = len(settings.get('blacklist', []))
    text = (
        "Здесь собраны <b>глобальные</b> настройки, общие для всех задач.\n\n"
        f"🌐 <b>Прокси в базе:</b> {proxies_count}\n"
        f"🚫 <b>Чатов в черном списке:</b> {blacklist_count}"
    )
    keyboard = [
        [InlineKeyboardButton("🌐 Прокси", callback_data='proxy_menu')],
        [InlineKeyboardButton("🚫 Очистить ЧС", callback_data='clear_file:blacklist')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='menu_main')]
    ]
    return text, InlineKeyboardMarkup(keyboard)

def get_proxy_menu():
    proxies = storage_manager.load_settings().get('proxies', [])
    text = f"В базе {len(proxies)} прокси.\nФормат: <code>host:port:user:pass</code>"
    keyboard = [
        [InlineKeyboardButton("➕ Добавить (текстом)", callback_data='proxy_add_text')],
        [InlineKeyboardButton("📂 Загрузить из файла (.txt)", callback_data='proxy_add_file')],
        [InlineKeyboardButton("📋 Список прокси", callback_data='proxy_list_page:1')],
        [InlineKeyboardButton("🗑️ Очистить все прокси", callback_data='proxy_clear_all')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='menu_settings')]
    ]
    return text, InlineKeyboardMarkup(keyboard)

def get_proxy_list_menu(proxies, page=1, checked_proxies=None):
    total_proxies = len(proxies)
    text = f"<b>Всего прокси: {total_proxies}</b>\n"
    if checked_proxies is None:
        checked_proxies = {}
    if not proxies:
        return "Список прокси пуст.", InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Назад", callback_data='proxy_menu')]
        ])
    total_pages = (total_proxies + PROXIES_PER_PAGE - 1) // PROXIES_PER_PAGE
    page = max(1, min(page, total_pages))
    start_index = (page - 1) * PROXIES_PER_PAGE
    end_index = start_index + PROXIES_PER_PAGE
    proxies_on_page = proxies[start_index:end_index]
    keyboard = []
    for i, proxy_str in enumerate(proxies_on_page):
        current_index = start_index + i
        status_info = ""
        if proxy_str in checked_proxies:
            status = checked_proxies[proxy_str]['status']
            country = checked_proxies[proxy_str]['country']
            if status == 'working':
                status_info = f"✅ {country}"
            else:
                status_info = "❌ Не работает"
        keyboard.append([
            InlineKeyboardButton(f"{proxy_str}", callback_data='none'),
            InlineKeyboardButton(f"{status_info}", callback_data='none'),
            InlineKeyboardButton("🗑️", callback_data=f'proxy_delete:{current_index}')
        ])
    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(InlineKeyboardButton("⬅️", callback_data=f'proxy_list_page:{page-1}'))
    pagination_buttons.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data='none'))
    if page < total_pages:
        pagination_buttons.append(InlineKeyboardButton("➡️", callback_data=f'proxy_list_page:{page+1}'))
    if pagination_buttons:
        keyboard.append(pagination_buttons)
    action_buttons = [InlineKeyboardButton("🔎 Проверить все", callback_data='proxy_check_all')]
    if checked_proxies:
        action_buttons.append(InlineKeyboardButton("🗑️ Удалить нерабочие", callback_data='proxy_delete_nonworking'))
    keyboard.append(action_buttons)
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='proxy_menu')])
    return text, InlineKeyboardMarkup(keyboard)

def get_proxy_check_running_menu():
    text = "🔎 <b>Прокси проверяются...</b>\n\nПожалуйста, подождите."
    keyboard = [[InlineKeyboardButton("🛑 Остановить проверку", callback_data='proxy_check_stop')]]
    return text, InlineKeyboardMarkup(keyboard)


def get_tasks_menu():
    text = "Здесь вы можете создавать и управлять задачами."
    keyboard = [
        [InlineKeyboardButton("➕ Создать новую задачу", callback_data='tasks_create')],
        [InlineKeyboardButton("📋 Список задач", callback_data='tasks_list')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='menu_main')]
    ]
    return text, InlineKeyboardMarkup(keyboard)

def get_task_list_menu(tasks, active_task_names):
    if not tasks:
        return "У вас еще нет созданных задач.", InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Создать первую задачу", callback_data='tasks_create')],
            [InlineKeyboardButton("⬅️ Назад", callback_data='menu_tasks')]
        ])

    text = "<b>Список ваших задач:</b>\nНажмите на задачу для управления."
    keyboard = []
    for name, data in sorted(tasks.items()):
        status = 'running' if name in active_task_names else data.get('status', 'stopped')
        emoji = TASK_STATUS_EMOJI.get(status, '❓')
        keyboard.append([InlineKeyboardButton(f"{emoji} {name}", callback_data=f'task_manage:{name}')])

    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='menu_tasks')])
    return text, InlineKeyboardMarkup(keyboard)

def get_task_manage_menu(task_name, task_data, is_running):
    status = 'running' if is_running else task_data.get('status', 'stopped')
    emoji = TASK_STATUS_EMOJI.get(status, '❓')
    task_type = task_data.get('type')
    task_type_name = TASK_TYPE_NAMES.get(task_type, "Не выбрано")
    accounts_count = len(task_data.get('accounts', []))
    has_report = bool(task_data.get('report'))

    text = (f"<b>Управление задачей:</b> <code>{html.escape(task_name)}</code>\n\n"
            f"<b>Статус:</b> {emoji} {status.capitalize()}\n"
            f"<b>Действие:</b> {task_type_name}\n"
            f"<b>Подключено аккаунтов:</b> {accounts_count}")

    keyboard = []
    if is_running:
        keyboard.append([
            InlineKeyboardButton("📝 Текущий отчет", callback_data=f'task_report:{task_name}'),
            InlineKeyboardButton("🛑 Остановить", callback_data=f'task_stop:{task_name}')
        ])
    else:
        keyboard.append([InlineKeyboardButton("▶️ Запустить", callback_data=f'task_start:{task_name}')])
        
        keyboard.append([
            InlineKeyboardButton("⚙️ Настройки задачи", callback_data=f'task_settings_menu:{task_name}'),
            InlineKeyboardButton("🗂 Файлы задачи", callback_data=f'task_files_menu:{task_name}')
        ])

        keyboard.append([
            InlineKeyboardButton("👥 Аккаунты", callback_data=f'task_accounts:{task_name}:1'),
            InlineKeyboardButton("🎯 Действие", callback_data=f'task_action:{task_name}')
        ])

        action_row = []
        if has_report:
            action_row.append(InlineKeyboardButton("📝 Финальный отчет", callback_data=f'task_show_saved_report:{task_name}'))
        action_row.append(InlineKeyboardButton("🗑️ Удалить", callback_data=f'task_delete_prompt:{task_name}'))
        keyboard.append(action_row)

    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='tasks_list')])
    return text, InlineKeyboardMarkup(keyboard)

def get_task_settings_menu(task_name, task_settings):
    interval = task_settings.get('broadcast_interval', ['N/A', 'N/A'])
    fwd_link_safe = html.escape(task_settings.get('forward_post_link', 'Не задана'))
    target_map = {'chats': 'Только чаты', 'comments': 'Только комментарии', 'both': 'Чаты и комментарии'}
    current_target = target_map.get(task_settings.get('broadcast_target'), 'Неизвестно')
    workers_limit = task_settings.get('concurrent_workers', 5)
    password = task_settings.get('two_fa_password', '')
    password_display = f'<code>{html.escape(password)}</code>' if password else 'не задан'
    
    reply_in_pm_status = "✅ Включено" if task_settings.get('reply_in_pm') else "❌ Выключено"
    reply_in_pm_button_text = "🤖 Отвечать в ЛС"

    text = (f"<b>Настройки для задачи:</b> <code>{html.escape(task_name)}</code>\n\n"
            f"🤖 <b>Отвечать в ЛС:</b> {reply_in_pm_status}\n"
            f"🔑 <b>Пароль 2FA:</b> {password_display}\n"
            f"🚀 <b>Лимит воркеров:</b> {workers_limit} акк.\n"
            f"⏱ <b>Интервал:</b> От {interval[0]} до {interval[1]} сек.\n"
            f"🔗 <b>Пост для пересылки:</b> <code>{fwd_link_safe}</code>\n"
            f"🎯 <b>Цель рассылки:</b> {current_target}")
    keyboard = [
        [InlineKeyboardButton(reply_in_pm_button_text, callback_data=f'task_toggle_setting:reply_in_pm:{task_name}')],
        [InlineKeyboardButton("🔑 Пароль 2FA", callback_data=f'task_set:2fa_password:{task_name}')],
        [InlineKeyboardButton("🚀 Лимит воркеров", callback_data=f'task_set:workers:{task_name}')],
        [InlineKeyboardButton("⏱ Интервал", callback_data=f'task_set:interval:{task_name}'),
         InlineKeyboardButton("🎯 Куда писать", callback_data=f'task_set_target_menu:{task_name}')],
        [InlineKeyboardButton("🔗 Пост для пересылки", callback_data=f'task_set:fwd_post:{task_name}')],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f'task_manage:{task_name}')]
    ]
    return text, InlineKeyboardMarkup(keyboard)

def get_task_broadcast_target_menu(task_name, current_target):
    def button_text(target, text):
        return f"✅ {text}" if current_target == target else text
    keyboard = [
        [InlineKeyboardButton(button_text('chats', "Только по чатам"), callback_data=f'task_set_target:chats:{task_name}')],
        [InlineKeyboardButton(button_text('comments', "Только по комментариям"), callback_data=f'task_set_target:comments:{task_name}')],
        [InlineKeyboardButton(button_text('both', "По чатам и комментариям"), callback_data=f'task_set_target:both:{task_name}')],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f'task_settings_menu:{task_name}')]
    ]
    return f"Выберите цель рассылки для задачи `{html.escape(task_name)}`:", InlineKeyboardMarkup(keyboard)

def get_task_files_menu(task_name):
    stats = storage_manager.get_task_stats(task_name)
    text = (f"<b>Файлы для задачи:</b> <code>{html.escape(task_name)}</code>\n\n"
            f"✉️ Сообщения для рассылки: {stats.get('messages', 0)}\n"
            f"🤖 Ответы в ЛС: {stats.get('pm_replies', 0)}\n"
            f"👥 Чаты: {stats.get('chats', 0)}\n"
            f"--- Профили ---\n"
            f"👤 Имена: {stats.get('names', 0)}\n"
            f"📜 Фамилии: {stats.get('lastnames', 0)}\n"
            f"📝 Описания профилей: {stats.get('bios', 0)}\n"
            f"🖼 Аватарки профилей: {stats.get('avatars', 0)}\n"
            f"--- Спам ---\n"
            f"🎯 Цели спама: {stats.get('spam_targets', 0)}\n"
            f"🔗 Пересылаемые сообщения: {stats.get('forward_messages', 0)}\n"
            f"😄 Стикеры: {stats.get('stickers', 0)}\n"
            f"--- Каналы ---\n"
            f"📝 Имена каналов: {stats.get('channel_names', 0)}\n"
            f"ℹ️ Описания каналов: {stats.get('channel_descriptions', 0)}\n"
            f"🖼️ Аватарки каналов: {stats.get('channel_avatars', 0)}\n\n"
            "Выберите категорию для загрузки или очистки:")
    keyboard = [
        [InlineKeyboardButton("✉️ Сообщения", callback_data=f'task_upload:messages:{task_name}'), InlineKeyboardButton("🗑️", callback_data=f'task_clear:messages:{task_name}')],
        [InlineKeyboardButton("🤖 Ответы в ЛС", callback_data=f'task_upload:pm_replies:{task_name}'), InlineKeyboardButton("🗑️", callback_data=f'task_clear:pm_replies:{task_name}')],
        [InlineKeyboardButton("👥 Чаты", callback_data=f'task_upload:chats:{task_name}'), InlineKeyboardButton("🗑️", callback_data=f'task_clear:chats:{task_name}')],
        [InlineKeyboardButton("👤 Имена", callback_data=f'task_upload:names:{task_name}'), InlineKeyboardButton("🗑️", callback_data=f'task_clear:names:{task_name}')],
        [InlineKeyboardButton("📜 Фамилии", callback_data=f'task_upload:lastnames:{task_name}'), InlineKeyboardButton("🗑️", callback_data=f'task_clear:lastnames:{task_name}')],
        [InlineKeyboardButton("📝 Описания профилей", callback_data=f'task_upload:bios:{task_name}'), InlineKeyboardButton("🗑️", callback_data=f'task_clear:bios:{task_name}')],
        [InlineKeyboardButton("🖼 Аватарки профилей", callback_data=f'task_upload:avatars:{task_name}'), InlineKeyboardButton("🗑️", callback_data=f'task_clear:avatars:{task_name}')],
        [InlineKeyboardButton("🎯 Цели спама", callback_data=f'task_upload:spam_targets:{task_name}'), InlineKeyboardButton("🗑️", callback_data=f'task_clear:spam_targets:{task_name}')],
        [InlineKeyboardButton("🔗 Пересылаемые сообщения", callback_data=f'task_upload:forward_messages:{task_name}'), InlineKeyboardButton("🗑️", callback_data=f'task_clear:forward_messages:{task_name}')],
        [InlineKeyboardButton("😄 Стикеры", callback_data=f'task_upload:stickers:{task_name}'), InlineKeyboardButton("🗑️", callback_data=f'task_clear:stickers:{task_name}')],
        [InlineKeyboardButton("📝 Имена каналов", callback_data=f'task_upload:channel_names:{task_name}'), InlineKeyboardButton("🗑️", callback_data=f'task_clear:channel_names:{task_name}')],
        [InlineKeyboardButton("ℹ️ Описания каналов", callback_data=f'task_upload:channel_descriptions:{task_name}'), InlineKeyboardButton("🗑️", callback_data=f'task_clear:channel_descriptions:{task_name}')],
        [InlineKeyboardButton("🖼️ Аватарки каналов", callback_data=f'task_upload:channel_avatars:{task_name}'), InlineKeyboardButton("🗑️", callback_data=f'task_clear:channel_avatars:{task_name}')],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f'task_manage:{task_name}')]
    ]
    return text, InlineKeyboardMarkup(keyboard)

def get_task_action_menu(task_name):
    text = "Выберите действие, которое будет выполнять эта задача:"
    keyboard = []
    row = []
    for type_key, name in TASK_TYPE_NAMES.items():
        row.append(InlineKeyboardButton(name, callback_data=f'task_set_action:{task_name}:{type_key}'))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data=f'task_manage:{task_name}')])
    return text, InlineKeyboardMarkup(keyboard)

def get_task_accounts_menu(task_name, task_data, all_accounts, all_statuses, globally_assigned_accounts, page=1, filter_by_valid_status=False):
    assigned_to_this_task = set(task_data.get('accounts', []))
    
    available_accounts = [acc for acc in all_accounts if acc not in globally_assigned_accounts]
    
    if filter_by_valid_status:
        final_list = [acc for acc in available_accounts if all_statuses.get(acc) == 'valid']
        prompt = "Показаны только <b>свободные и валидные (✅)</b> аккаунты."
    else:
        final_list = available_accounts
        prompt = "Аккаунты, занятые в других задачах, скрыты."

    if not final_list:
        return "Нет свободных аккаунтов для этой задачи.", InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Назад", callback_data=f'task_manage:{task_name}')]
        ])

    text = f"<b>Привязка аккаунтов к задаче:</b> <code>{html.escape(task_name)}</code>\n{prompt}"
    
    total_pages = (len(final_list) + ACCOUNTS_PER_PAGE - 1) // ACCOUNTS_PER_PAGE
    page = max(1, min(page, total_pages))
    start_index = (page - 1) * ACCOUNTS_PER_PAGE
    end_index = start_index + ACCOUNTS_PER_PAGE
    accounts_on_page = final_list[start_index:end_index]

    keyboard = []
    for acc_name in accounts_on_page:
        is_assigned = acc_name in assigned_to_this_task
        status_key = all_statuses.get(acc_name, 'unknown')
        status_emoji = ACCOUNT_STATUS_EMOJI.get(status_key, '❔')
        toggle_emoji = "✅" if is_assigned else "➕"
        
        callback = f'task_toggle_account:{acc_name}:{page}'
        keyboard.append([InlineKeyboardButton(f"{toggle_emoji} {status_emoji} {acc_name}", callback_data=callback)])

    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(InlineKeyboardButton("⬅️", callback_data=f'task_accounts:{task_name}:{page-1}'))
    pagination_buttons.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data='none'))
    if page < total_pages:
        pagination_buttons.append(InlineKeyboardButton("➡️", callback_data=f'task_accounts:{task_name}:{page+1}'))
    
    keyboard.append([
        InlineKeyboardButton("✅ Выбрать всех", callback_data=f'task_toggle_all:select'),
        InlineKeyboardButton("❌ Снять выбор", callback_data=f'task_toggle_all:deselect')
    ])
    
    if pagination_buttons:
        keyboard.append(pagination_buttons)
        
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data=f'task_manage:{task_name}')])
    return text, InlineKeyboardMarkup(keyboard)

def get_task_delete_confirmation_menu(task_name):
    text = f"❓ <b>Вы уверены, что хотите удалить задачу <code>{html.escape(task_name)}</code>?</b>\n\nЭто действие необратимо."
    keyboard = [
        [InlineKeyboardButton("✅ Да, удалить", callback_data=f'task_delete_confirm:{task_name}')],
        [InlineKeyboardButton("⬅️ Нет, назад", callback_data=f'task_manage:{task_name}')]
    ]
    return text, InlineKeyboardMarkup(keyboard)

def get_back_button(callback_data='menu_main'):
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=callback_data)]])

def get_close_keyboard():
    keyboard = [[InlineKeyboardButton("❌ Закрыть", callback_data='close_message')]]
    return InlineKeyboardMarkup(keyboard)

def get_task_completion_keyboard(task_name):
    keyboard = [[
        InlineKeyboardButton("📝 Показать финальный отчет", callback_data=f'task_show_saved_report:{task_name}'),
        InlineKeyboardButton("❌ Закрыть", callback_data='close_message')
    ]]
    return InlineKeyboardMarkup(keyboard)