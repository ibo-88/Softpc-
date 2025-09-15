# storage_manager.py

import os
import json
import zipfile
import shutil
import re
import random
import string

# --- Константы путей ---
DATA_DIR = "data"
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")
TASK_DATA_DIR = os.path.join(DATA_DIR, "task_data")
BACKUP_DIR = os.path.join(DATA_DIR, "backup")
DB_FILE = os.path.join(DATA_DIR, "db.json")

# --- Структуры по умолчанию для новых задач ---
TASK_DEFAULT_FILES = {
    "messages": "messages.txt",
    "names": "names.txt",
    "lastnames": "lastnames.txt",
    "channel_names": "channelnames.txt",
    "channel_descriptions": "channel_descriptions.txt",
    "chats": "chats.txt",
    "pm_replies": "pm_replies.txt"
}
TASK_DEFAULT_DIRS = {
    "avatars": "avatars",
    "channel_avatars": "channel_avatars"
}

def initialize_storage():
    """Создает все необходимые директории при первом запуске."""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    os.makedirs(TASK_DATA_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)

# --- Настройки по умолчанию ---
DEFAULT_SETTINGS = {
    # Глобальные настройки
    "proxies": [],
    "blacklist": [],
    "proxy_statuses": {},
    "tasks": {},
    "account_statuses": {}
}

DEFAULT_TASK_SETTINGS = {
    # Настройки по умолчанию для одной задачи
    "broadcast_interval": [30, 90],
    "forward_post_link": "",
    "broadcast_target": "chats",
    "concurrent_workers": 5,
    "two_fa_password": "",
    "reply_in_pm": False
}

def load_settings():
    if not os.path.exists(DB_FILE):
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            for key in DEFAULT_SETTINGS.keys():
                if key not in settings:
                    settings[key] = DEFAULT_SETTINGS[key]
            return settings
    except (json.JSONDecodeError, FileNotFoundError):
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS

def save_settings(settings_data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings_data, f, indent=4, ensure_ascii=False)

def load_tasks():
    settings = load_settings()
    return settings.get("tasks", {})

def save_tasks(tasks_data):
    settings = load_settings()
    settings["tasks"] = tasks_data
    save_settings(settings)

def get_task(task_name):
    tasks = load_tasks()
    task_data = tasks.get(task_name)
    
    if task_data:
        updated = False
        
        if 'settings' not in task_data:
            task_data['settings'] = {}
        for key, value in DEFAULT_TASK_SETTINGS.items():
            if key not in task_data['settings']:
                task_data['settings'][key] = value
                updated = True
        
        if 'files' not in task_data:
            task_data['files'] = {}
        for key, value in TASK_DEFAULT_FILES.items():
            if key not in task_data['files']:
                task_data['files'][key] = value
                file_path = os.path.join(TASK_DATA_DIR, task_name, value)
                if not os.path.exists(file_path):
                    with open(file_path, 'a', encoding='utf-8') as f:
                        pass
                updated = True
        
        if updated:
            save_tasks(tasks)
            
    return task_data


def create_task(task_name):
    tasks = load_tasks()
    if task_name in tasks:
        return False
    
    task_dir = os.path.join(TASK_DATA_DIR, task_name)
    os.makedirs(task_dir, exist_ok=True)
    for dir_name in TASK_DEFAULT_DIRS.values():
        os.makedirs(os.path.join(task_dir, dir_name), exist_ok=True)
    for file_name in TASK_DEFAULT_FILES.values():
        with open(os.path.join(task_dir, file_name), 'a', encoding='utf-8') as f:
            pass

    tasks[task_name] = {
        'status': 'stopped',
        'type': None,
        'accounts': [],
        'report': '',
        'settings': DEFAULT_TASK_SETTINGS.copy(),
        'files': TASK_DEFAULT_FILES.copy()
    }
    save_tasks(tasks)
    return True

def delete_task(task_name):
    tasks = load_tasks()
    if task_name in tasks:
        del tasks[task_name]
        save_tasks(tasks)
        
        task_dir = os.path.join(TASK_DATA_DIR, task_name)
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir)
        return True
    return False

def load_account_statuses():
    settings = load_settings()
    return settings.get("account_statuses", {})

def save_account_statuses(statuses_dict):
    settings = load_settings()
    settings["account_statuses"] = statuses_dict
    save_settings(settings)

def load_proxy_statuses():
    settings = load_settings()
    return settings.get("proxy_statuses", {})

def save_proxy_statuses(statuses_dict):
    settings = load_settings()
    settings["proxy_statuses"] = statuses_dict
    save_settings(settings)

# --- Функции управления аккаунтами ---
def list_accounts():
    if not os.path.exists(SESSIONS_DIR):
        return []
    files = os.listdir(SESSIONS_DIR)
    sessions = {f.split('.')[0] for f in files if f.endswith('.session')}
    jsons = {f.split('.')[0] for f in files if f.endswith('.json')}
    
    sessions_without_json = sessions - jsons
    if sessions_without_json:
        for session_name in sessions_without_json:
            create_default_json_for_session(session_name)
            jsons.add(session_name)

    valid_accounts = sorted(list(sessions.intersection(jsons)))
    return valid_accounts

def create_default_json_for_session(session_name):
    part1 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    part2 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
    random_device_model = f"{part1}-{part2}"
    
    default_json_data = {
        "app_id": 2040,
        "app_hash": "b18441a1ff607e10a989891a5462e627",
        "device": random_device_model,
        "sdk": "Windows 10",
        "app_version": "6.0.1 x64",
        "system_lang_pack": "en-US",
        "system_lang_code": "en",
        "lang_pack": "tdesktop",
        "lang_code": "en",
        "twoFA": None
    }
    json_path = os.path.join(SESSIONS_DIR, f"{session_name}.json")
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(default_json_data, f, indent=4)
        return True
    except Exception as e:
        print(f"Не удалось создать {session_name}.json: {e}")
        return False

def delete_account(session_name):
    settings = load_settings()
    something_changed = False
    
    tasks = settings.get("tasks", {})
    for task_name, task_data in tasks.items():
        if session_name in task_data.get('accounts', []):
            tasks[task_name]['accounts'].remove(session_name)
            something_changed = True
            
    statuses = settings.get("account_statuses", {})
    if session_name in statuses:
        del statuses[session_name]
        something_changed = True
        
    if something_changed:
        save_settings(settings)
    
    session_file = os.path.join(SESSIONS_DIR, f"{session_name}.session")
    json_file = os.path.join(SESSIONS_DIR, f"{session_name}.json")
    
    try:
        if os.path.exists(session_file):
            os.remove(session_file)
        if os.path.exists(json_file):
            os.remove(json_file)
        return True
    except PermissionError:
        print(f"Не удалось удалить файлы для {session_name}, так как они заняты другим процессом.")
        return False

def delete_accounts_by_status(statuses_to_delete: list):
    accounts_to_delete = []
    statuses = load_account_statuses()
    for acc, status in statuses.items():
        if status in statuses_to_delete:
            accounts_to_delete.append(acc)
            
    if not accounts_to_delete:
        return 0
        
    deleted_count = 0
    for acc_name in accounts_to_delete:
        if delete_account(acc_name):
            deleted_count += 1
    return deleted_count

# --- Функции для работы с файлами конкретной ЗАДАЧИ ---
def get_task_file_path(task_name, file_key):
    task = get_task(task_name)
    if not task: return None
    
    if file_key in task.get('files', {}):
        return os.path.join(TASK_DATA_DIR, task_name, task['files'][file_key])
    elif file_key in TASK_DEFAULT_DIRS:
        return os.path.join(TASK_DATA_DIR, task_name, TASK_DEFAULT_DIRS[file_key])
    return None

def read_task_text_file_lines(task_name, file_key):
    filepath = get_task_file_path(task_name, file_key)
    if not filepath or not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def read_task_multiline_messages(task_name, file_key, delimiter=r'\s*---\s*'):
    filepath = get_task_file_path(task_name, file_key)
    if not filepath or not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    return [msg.strip() for msg in re.split(delimiter, content) if msg.strip()]

def get_task_stats(task_name):
    stats = {}
    task = get_task(task_name)
    if not task: return stats
    
    for key, filename in task.get('files', {}).items():
        filepath = get_task_file_path(task_name, key)
        if not os.path.exists(filepath):
            stats[key] = 0
            continue

        if key in ['messages', 'pm_replies']:
            stats[key] = len(read_task_multiline_messages(task_name, key))
        else:
            stats[key] = len(read_task_text_file_lines(task_name, key))
            
    for key, dirname in TASK_DEFAULT_DIRS.items():
        dir_path = os.path.join(TASK_DATA_DIR, task_name, dirname)
        if os.path.exists(dir_path):
            stats[key] = len([f for f in os.listdir(dir_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
        else:
            stats[key] = 0
            
    return stats

def clear_task_file_or_dir(task_name, key):
    path = get_task_file_path(task_name, key)
    if not path: return
    
    if os.path.isfile(path):
        with open(path, 'w') as f:
            pass
    elif os.path.isdir(path):
        shutil.rmtree(path)
        os.makedirs(path)

async def remove_line_from_file(filepath, line_to_remove, lock):
    async with lock:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            new_lines = [line for line in lines if line.strip() != line_to_remove.strip()]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Ошибка при удалении строки из файла {filepath}: {e}")

# --- Общие утилиты ---
def unpack_zip(zip_path, extract_to):
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        return "✅ Архив успешно распакован."
    except Exception as e:
        return f"❌ Ошибка при распаковке: {e}"

def clear_blacklist():
    settings = load_settings()
    settings['blacklist'] = []
    save_settings(settings)

initialize_storage()