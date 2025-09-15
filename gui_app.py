# gui_app.py

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import scrolledtext
import asyncio
import threading
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
import storage_manager
import telegram_worker
import parser_module
import core_manager
import account_tester
import safety_manager
import proxy_manager

class TelegramManagerGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Telegram Account Manager & Parser")
        self.root.geometry("1200x800")
        self.root.configure(bg='#2b2b2b')
        
        # Стиль для темной темы
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_dark_theme()
        
        # Переменные состояния
        self.active_tasks = {}
        self.current_account = None
        self.accounts = []
        self.tasks = {}
        
        # Инициализация хранилища
        storage_manager.initialize_storage()
        self.load_data()
        
        # Инициализация менеджеров
        self.core_manager = core_manager.get_core_manager(self.log)
        self.safety_manager = safety_manager.get_safety_manager()
        self.proxy_manager = proxy_manager.get_proxy_manager()
        
        # Создание интерфейса
        self.create_widgets()
        
        # Запуск основного цикла
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def configure_dark_theme(self):
        """Настройка темной темы"""
        self.style.configure('TLabel', background='#2b2b2b', foreground='white')
        self.style.configure('TFrame', background='#2b2b2b')
        self.style.configure('TButton', background='#404040', foreground='white')
        self.style.configure('TEntry', fieldbackground='#404040', foreground='white')
        self.style.configure('TCombobox', fieldbackground='#404040', foreground='white')
        self.style.configure('Treeview', background='#404040', foreground='white', fieldbackground='#404040')
        self.style.configure('Treeview.Heading', background='#505050', foreground='white')
        self.style.configure('TNotebook', background='#2b2b2b')
        self.style.configure('TNotebook.Tab', background='#404040', foreground='white')
    
    def create_widgets(self):
        """Создание основных виджетов"""
        # Главное меню
        self.create_menu()
        
        # Основной контейнер
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Создание вкладок
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Вкладки
        self.create_accounts_tab()
        self.create_parser_tab()
        self.create_tasks_tab()
        self.create_settings_tab()
        self.create_logs_tab()
        
    def create_menu(self):
        """Создание меню"""
        menubar = tk.Menu(self.root, bg='#2b2b2b', fg='white')
        self.root.config(menu=menubar)
        
        # Файл
        file_menu = tk.Menu(menubar, tearoff=0, bg='#2b2b2b', fg='white')
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Загрузить сессии", command=self.load_sessions)
        file_menu.add_command(label="Экспорт настроек", command=self.export_settings)
        file_menu.add_command(label="Импорт настроек", command=self.import_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.on_closing)
        
        # Инструменты
        tools_menu = tk.Menu(menubar, tearoff=0, bg='#2b2b2b', fg='white')
        menubar.add_cascade(label="Инструменты", menu=tools_menu)
        tools_menu.add_command(label="Проверить все аккаунты", command=self.check_all_accounts)
        tools_menu.add_command(label="Очистить логи", command=self.clear_logs)
    
    def create_accounts_tab(self):
        """Вкладка управления аккаунтами"""
        accounts_frame = ttk.Frame(self.notebook)
        self.notebook.add(accounts_frame, text="Аккаунты")
        
        # Левая панель - список аккаунтов
        left_frame = ttk.Frame(accounts_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        ttk.Label(left_frame, text="Список аккаунтов:").pack(anchor=tk.W, pady=(0, 5))
        
        # Treeview для аккаунтов
        columns = ('Имя', 'Статус', 'Прокси')
        self.accounts_tree = ttk.Treeview(left_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.accounts_tree.heading(col, text=col)
            self.accounts_tree.column(col, width=150)
        
        # Скроллбар для списка аккаунтов
        accounts_scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.accounts_tree.yview)
        self.accounts_tree.configure(yscrollcommand=accounts_scrollbar.set)
        
        self.accounts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        accounts_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Привязка событий
        self.accounts_tree.bind('<<TreeviewSelect>>', self.on_account_select)
        
        # Правая панель - управление аккаунтом
        right_frame = ttk.Frame(accounts_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        
        ttk.Label(right_frame, text="Управление аккаунтом:").pack(anchor=tk.W, pady=(0, 10))
        
        # Информация об аккаунте
        info_frame = ttk.LabelFrame(right_frame, text="Информация", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.account_info_text = tk.Text(info_frame, height=8, width=40, bg='#404040', fg='white', 
                                       font=('Consolas', 10))
        self.account_info_text.pack(fill=tk.BOTH, expand=True)
        
        # Кнопки управления
        buttons_frame = ttk.Frame(right_frame)
        buttons_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(buttons_frame, text="🧪 Тест подключения", 
                  command=self.test_selected_account).pack(fill=tk.X, pady=2)
        ttk.Button(buttons_frame, text="Проверить аккаунт", 
                  command=self.check_selected_account).pack(fill=tk.X, pady=2)
        ttk.Button(buttons_frame, text="Сменить профиль", 
                  command=self.change_profile).pack(fill=tk.X, pady=2)
        ttk.Button(buttons_frame, text="Удалить аккаунт", 
                  command=self.delete_account).pack(fill=tk.X, pady=2)
        
        # Загрузка аккаунтов
        load_frame = ttk.LabelFrame(right_frame, text="Загрузка", padding=10)
        load_frame.pack(fill=tk.X)
        
        ttk.Button(load_frame, text="Загрузить ZIP с сессиями", 
                  command=self.load_sessions).pack(fill=tk.X, pady=2)
        ttk.Button(load_frame, text="Обновить список", 
                  command=self.refresh_accounts).pack(fill=tk.X, pady=2)
    
    def create_parser_tab(self):
        """Вкладка парсера"""
        parser_frame = ttk.Frame(self.notebook)
        self.notebook.add(parser_frame, text="Парсер")
        
        # Верхняя панель - настройки парсинга
        top_frame = ttk.LabelFrame(parser_frame, text="Настройки парсинга", padding=15)
        top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Строка 1: Аккаунт и тип парсинга
        ttk.Label(top_frame, text="Аккаунт:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.parser_account_var = tk.StringVar()
        self.parser_account_combo = ttk.Combobox(top_frame, textvariable=self.parser_account_var, width=25)
        self.parser_account_combo.grid(row=0, column=1, padx=(0, 15), sticky=tk.W)
        
        ttk.Label(top_frame, text="Тип:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.parse_type_var = tk.StringVar(value="usernames")
        parse_type_combo = ttk.Combobox(top_frame, textvariable=self.parse_type_var, 
                                      values=["usernames", "members", "multiple_usernames", "messages", "dialogs"], 
                                      width=20, state="readonly")
        parse_type_combo.grid(row=0, column=3, sticky=tk.W)
        parse_type_combo.bind('<<ComboboxSelected>>', self.on_parse_type_changed)
        
        # Строка 2: Цель парсинга (обычное поле)
        self.parse_target_label = ttk.Label(top_frame, text="Цель:")
        self.parse_target_label.grid(row=1, column=0, sticky=tk.W, pady=(10, 0), padx=(0, 5))
        self.parse_target_var = tk.StringVar()
        self.parse_target_entry = ttk.Entry(top_frame, textvariable=self.parse_target_var, width=60)
        self.parse_target_entry.grid(row=1, column=1, columnspan=3, sticky=tk.W, pady=(10, 0))
        
        # Строка 3: Текстовое поле для множественного парсинга (скрыто по умолчанию)
        self.parse_target_text_label = ttk.Label(top_frame, text="Список чатов:")
        self.parse_target_text = tk.Text(top_frame, height=4, width=60, bg='#404040', fg='white')
        # Изначально скрыты
        
        # Строка 4: Лимит и формат
        ttk.Label(top_frame, text="Лимит:").grid(row=4, column=0, sticky=tk.W, pady=(10, 0), padx=(0, 5))
        self.parse_limit_var = tk.StringVar(value="10000")
        self.parse_limit_entry = ttk.Entry(top_frame, textvariable=self.parse_limit_var, width=10)
        self.parse_limit_entry.grid(row=4, column=1, sticky=tk.W, pady=(10, 0))
        
        ttk.Label(top_frame, text="Формат:").grid(row=4, column=2, sticky=tk.W, pady=(10, 0), padx=(15, 5))
        self.export_format_var = tk.StringVar(value="txt")
        format_combo = ttk.Combobox(top_frame, textvariable=self.export_format_var, 
                                  values=["txt", "csv", "json"], width=10, state="readonly")
        format_combo.grid(row=4, column=3, sticky=tk.W, pady=(10, 0))
        
        # Строка 5: Кнопки управления
        buttons_frame = ttk.Frame(top_frame)
        buttons_frame.grid(row=5, column=0, columnspan=4, pady=(15, 0), sticky=tk.W)
        
        ttk.Button(buttons_frame, text="🚀 Начать парсинг", 
                  command=self.start_parsing).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(buttons_frame, text="🛑 Остановить", 
                  command=self.stop_parsing).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(buttons_frame, text="📁 Открыть папку экспорта", 
                  command=self.open_export_folder).pack(side=tk.LEFT)
        
        # Средняя панель - прогресс
        progress_frame = ttk.LabelFrame(parser_frame, text="Прогресс парсинга", padding=10)
        progress_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.parse_progress = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.parse_progress.pack(fill=tk.X, pady=(0, 10))
        
        self.parse_status_var = tk.StringVar(value="Готов к парсингу")
        ttk.Label(progress_frame, textvariable=self.parse_status_var).pack(anchor=tk.W)
        
        # Нижняя панель - результаты
        results_frame = ttk.LabelFrame(parser_frame, text="Результаты парсинга", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Таблица результатов
        self.results_tree = ttk.Treeview(results_frame, show='headings', height=15)
        results_scrollbar_y = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        results_scrollbar_x = ttk.Scrollbar(results_frame, orient=tk.HORIZONTAL, command=self.results_tree.xview)
        
        self.results_tree.configure(yscrollcommand=results_scrollbar_y.set, xscrollcommand=results_scrollbar_x.set)
        
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        results_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        results_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
    
    def create_tasks_tab(self):
        """Вкладка задач"""
        tasks_frame = ttk.Frame(self.notebook)
        self.notebook.add(tasks_frame, text="Задачи")
        
        # Левая панель - список задач
        left_frame = ttk.Frame(tasks_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        ttk.Label(left_frame, text="Список задач:").pack(anchor=tk.W, pady=(0, 5))
        
        # Treeview для задач
        columns = ('Название', 'Тип', 'Статус', 'Аккаунтов')
        self.tasks_tree = ttk.Treeview(left_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.tasks_tree.heading(col, text=col)
            self.tasks_tree.column(col, width=120)
        
        tasks_scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.tasks_tree.yview)
        self.tasks_tree.configure(yscrollcommand=tasks_scrollbar.set)
        
        self.tasks_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tasks_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Правая панель - управление задачами
        right_frame = ttk.Frame(tasks_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        
        ttk.Label(right_frame, text="Управление задачами:").pack(anchor=tk.W, pady=(0, 10))
        
        # Создание новой задачи
        create_frame = ttk.LabelFrame(right_frame, text="Создать задачу", padding=10)
        create_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(create_frame, text="Название:").pack(anchor=tk.W)
        self.task_name_var = tk.StringVar()
        ttk.Entry(create_frame, textvariable=self.task_name_var, width=30).pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(create_frame, text="Тип задачи:").pack(anchor=tk.W)
        self.task_type_var = tk.StringVar()
        task_types = [
            "check_all", 
            "change_profile:name", "change_profile:lastname", "change_profile:avatar", "change_profile:bio",
            "change_profile:all",
            "create_channel", "update_channel_design", "join_chats", 
            "spam_chats", "spam_channels", "spam_both", "spam_dm", "spam_dm_existing",
            "set_2fa", "remove_2fa", "clean_account"
        ]
        ttk.Combobox(create_frame, textvariable=self.task_type_var, 
                    values=task_types, width=28, state="readonly").pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(create_frame, text="Создать задачу", 
                  command=self.create_task).pack(fill=tk.X)
        
        # Управление выбранной задачей
        manage_frame = ttk.LabelFrame(right_frame, text="Управление", padding=10)
        manage_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(manage_frame, text="Запустить задачу", 
                  command=self.start_task).pack(fill=tk.X, pady=2)
        ttk.Button(manage_frame, text="Остановить задачу", 
                  command=self.stop_task).pack(fill=tk.X, pady=2)
        ttk.Button(manage_frame, text="Настройки задачи", 
                  command=self.task_settings).pack(fill=tk.X, pady=2)
        ttk.Button(manage_frame, text="Удалить задачу", 
                  command=self.delete_task).pack(fill=tk.X, pady=2)
        
        # Обновление списка задач
        ttk.Button(right_frame, text="Обновить список", 
                  command=self.refresh_tasks).pack(fill=tk.X, pady=(10, 0))
    
    def create_settings_tab(self):
        """Вкладка настроек"""
        settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(settings_frame, text="Настройки")
        
        # Верхняя панель - настройки распределения
        distribution_frame = ttk.LabelFrame(settings_frame, text="Настройки распределения", padding=10)
        distribution_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(distribution_frame, text="Аккаунтов на 1 прокси:").pack(side=tk.LEFT, padx=(0, 10))
        self.accounts_per_proxy_var = tk.StringVar(value="3")
        accounts_per_proxy_spin = tk.Spinbox(distribution_frame, from_=1, to=10, width=5, 
                                           textvariable=self.accounts_per_proxy_var,
                                           command=self.update_proxy_distribution)
        accounts_per_proxy_spin.pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Button(distribution_frame, text="📊 Показать распределение", 
                  command=self.show_proxy_distribution).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(distribution_frame, text="🔄 Обновить распределение", 
                  command=self.update_proxy_distribution).pack(side=tk.LEFT)
        
        # Панель прокси
        proxy_frame = ttk.LabelFrame(settings_frame, text="Управление прокси", padding=10)
        proxy_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Левая часть - список прокси
        left_proxy_frame = ttk.Frame(proxy_frame)
        left_proxy_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Список прокси с цветовой индикацией
        columns = ('Прокси', 'Статус', 'Страна', 'Время')
        self.proxy_tree = ttk.Treeview(left_proxy_frame, columns=columns, show='headings', height=12)
        
        for col in columns:
            self.proxy_tree.heading(col, text=col)
            if col == 'Прокси':
                self.proxy_tree.column(col, width=200)
            else:
                self.proxy_tree.column(col, width=80)
        
        proxy_tree_scrollbar = ttk.Scrollbar(left_proxy_frame, orient=tk.VERTICAL, command=self.proxy_tree.yview)
        self.proxy_tree.configure(yscrollcommand=proxy_tree_scrollbar.set)
        
        self.proxy_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        proxy_tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Правая часть - управление
        right_proxy_frame = ttk.Frame(proxy_frame)
        right_proxy_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        ttk.Label(right_proxy_frame, text="Управление прокси:").pack(anchor=tk.W, pady=(0, 10))
        
        ttk.Button(right_proxy_frame, text="➕ Добавить прокси", 
                  command=self.add_proxy).pack(fill=tk.X, pady=2)
        ttk.Button(right_proxy_frame, text="📂 Загрузить из файла", 
                  command=self.load_proxy_file).pack(fill=tk.X, pady=2)
        ttk.Button(right_proxy_frame, text="🔍 Проверить все", 
                  command=self.check_proxies).pack(fill=tk.X, pady=2)
        ttk.Button(right_proxy_frame, text="🗑️ Удалить нерабочие", 
                  command=self.remove_non_working_proxies).pack(fill=tk.X, pady=2)
        ttk.Button(right_proxy_frame, text="❌ Удалить выбранные", 
                  command=self.delete_selected_proxies).pack(fill=tk.X, pady=2)
        
        # Статистика
        stats_frame = ttk.LabelFrame(right_proxy_frame, text="Статистика", padding=5)
        stats_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.proxy_stats_text = tk.Text(stats_frame, height=8, width=25, bg='#404040', fg='white', 
                                       font=('Consolas', 9))
        self.proxy_stats_text.pack(fill=tk.BOTH, expand=True)
    
    def create_logs_tab(self):
        """Вкладка логов"""
        logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(logs_frame, text="Логи")
        
        # Текстовое поле для логов
        self.logs_text = scrolledtext.ScrolledText(
            logs_frame, bg='#1e1e1e', fg='#00ff00', 
            font=('Consolas', 10), wrap=tk.WORD
        )
        self.logs_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Кнопки управления логами
        logs_buttons_frame = ttk.Frame(logs_frame)
        logs_buttons_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Button(logs_buttons_frame, text="Очистить логи", 
                  command=self.clear_logs).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(logs_buttons_frame, text="Сохранить логи", 
                  command=self.save_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(logs_buttons_frame, text="Автопрокрутка", 
                  command=self.toggle_autoscroll).pack(side=tk.RIGHT)
        
        self.autoscroll_enabled = True
    
    def load_data(self):
        """Загрузка данных из хранилища"""
        self.accounts = storage_manager.list_accounts()
        self.tasks = storage_manager.load_tasks()
        
    def refresh_accounts(self):
        """Обновление списка аккаунтов"""
        self.load_data()
        
        # Очистка дерева
        for item in self.accounts_tree.get_children():
            self.accounts_tree.delete(item)
        
        # Загрузка статусов
        statuses = storage_manager.load_account_statuses()
        
        # Заполнение дерева
        for account in self.accounts:
            status = statuses.get(account, 'unknown')
            proxy = "Да" if self.has_proxy() else "Нет"  # Упрощенная проверка
            
            self.accounts_tree.insert('', tk.END, values=(account, status, proxy))
        
        # Обновление комбобокса парсера
        self.parser_account_combo['values'] = self.accounts
        
        self.log(f"Загружено аккаунтов: {len(self.accounts)}")
    
    def refresh_tasks(self):
        """Обновление списка задач"""
        self.load_data()
        
        # Очистка дерева
        for item in self.tasks_tree.get_children():
            self.tasks_tree.delete(item)
        
        # Заполнение дерева
        for task_name, task_data in self.tasks.items():
            task_type = task_data.get('type', 'Не задан')
            # Проверяем реальный статус через core_manager
            if self.core_manager.is_task_active(task_name):
                status = 'running'
            else:
                status = task_data.get('status', 'stopped')
            accounts_count = len(task_data.get('accounts', []))
            
            self.tasks_tree.insert('', tk.END, values=(task_name, task_type, status, accounts_count))
        
        self.log(f"Загружено задач: {len(self.tasks)}")
    
    def has_proxy(self):
        """Проверка наличия прокси (упрощенная)"""
        settings = storage_manager.load_settings()
        return len(settings.get('proxies', [])) > 0
    
    def on_account_select(self, event):
        """Обработка выбора аккаунта"""
        selection = self.accounts_tree.selection()
        if selection:
            item = self.accounts_tree.item(selection[0])
            account_name = item['values'][0]
            self.current_account = account_name
            
            # Обновление информации об аккаунте
            self.update_account_info(account_name)
    
    def update_account_info(self, account_name):
        """Обновление информации об аккаунте"""
        self.account_info_text.delete(1.0, tk.END)
        
        # Получение подробной информации
        account_info = storage_manager.get_account_info(account_name)
        statuses = storage_manager.load_account_statuses()
        status = statuses.get(account_name, 'unknown')
        
        info_text = f"📱 Аккаунт: {account_name}\n"
        info_text += f"📊 Статус: {status}\n"
        info_text += f"📄 Файл сессии: {'✅' if account_info['has_session'] else '❌'}\n"
        info_text += f"⚙️ JSON конфиг: {'✅' if account_info['has_json'] else '❌'}\n"
        
        if account_info['has_json']:
            if account_info['json_valid']:
                info_text += f"✅ JSON валидный\n"
                if account_info['api_id']:
                    info_text += f"🔑 API ID: {account_info['api_id']}\n"
                info_text += f"🔐 2FA: {'✅' if account_info['has_2fa'] else '❌'}\n"
            else:
                info_text += f"❌ JSON ошибка: {account_info['json_error']}\n"
        
        # Информация о прокси
        settings = storage_manager.load_settings()
        proxies_count = len(settings.get('proxies', []))
        info_text += f"🌐 Прокси в системе: {proxies_count}\n"
        
        # Информация о задачах
        tasks_using_account = [name for name, data in self.tasks.items() 
                             if account_name in data.get('accounts', [])]
        info_text += f"🎯 Задачи: {', '.join(tasks_using_account) if tasks_using_account else 'Нет'}\n"
        
        self.account_info_text.insert(1.0, info_text)
    
    def log(self, message):
        """Добавление сообщения в лог"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        self.logs_text.insert(tk.END, log_message)
        
        if self.autoscroll_enabled:
            self.logs_text.see(tk.END)
    
    def clear_logs(self):
        """Очистка логов"""
        self.logs_text.delete(1.0, tk.END)
        self.log("Логи очищены")
    
    def save_logs(self):
        """Сохранение логов в файл"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.logs_text.get(1.0, tk.END))
                self.log(f"Логи сохранены в: {filename}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить логи: {e}")
    
    def toggle_autoscroll(self):
        """Переключение автопрокрутки"""
        self.autoscroll_enabled = not self.autoscroll_enabled
        self.log(f"Автопрокрутка: {'включена' if self.autoscroll_enabled else 'выключена'}")
    
    def load_sessions(self):
        """Загрузка сессий из ZIP файла с валидацией"""
        filename = filedialog.askopenfilename(
            title="Выберите ZIP архив с сессиями",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")]
        )
        if filename:
            try:
                self.log(f"📦 Распаковываю архив: {os.path.basename(filename)}")
                storage_manager.unpack_zip(filename, storage_manager.SESSIONS_DIR)
                
                # Валидация загруженных аккаунтов
                self.log("🔍 Валидирую загруженные аккаунты...")
                accounts = storage_manager.list_accounts()
                
                valid_count = 0
                invalid_count = 0
                missing_json_count = 0
                
                for account in accounts:
                    account_info = storage_manager.get_account_info(account)
                    
                    if not account_info['has_json']:
                        # Создаем JSON по умолчанию для сессий без JSON
                        storage_manager.create_default_json_for_session(account)
                        missing_json_count += 1
                        self.log(f"📝 Создан JSON для {account}")
                    elif not account_info['json_valid']:
                        self.log(f"⚠️ {account}: {account_info['json_error']}")
                        invalid_count += 1
                    else:
                        valid_count += 1
                
                self.refresh_accounts()
                
                # Отчет о загрузке
                report = f"📊 Загрузка завершена:\n"
                report += f"✅ Валидных аккаунтов: {valid_count}\n"
                if missing_json_count > 0:
                    report += f"📝 Создано JSON файлов: {missing_json_count}\n"
                if invalid_count > 0:
                    report += f"⚠️ Аккаунтов с ошибками: {invalid_count}\n"
                
                self.log(report)
                
                if invalid_count > 0:
                    messagebox.showwarning("Предупреждение", 
                                         f"Загружено {valid_count} аккаунтов.\n"
                                         f"{invalid_count} аккаунтов имеют ошибки в JSON конфигурации.\n\n"
                                         "Проверьте логи для подробностей.")
                else:
                    messagebox.showinfo("Успех", f"Успешно загружено {valid_count} аккаунтов!")
                
            except Exception as e:
                self.log(f"❌ Ошибка загрузки: {e}")
                messagebox.showerror("Ошибка", f"Не удалось загрузить сессии: {e}")
    
    def check_selected_account(self):
        """Проверка выбранного аккаунта"""
        if not self.current_account:
            messagebox.showwarning("Предупреждение", "Выберите аккаунт для проверки")
            return
        
        self.log(f"Начинаю проверку аккаунта: {self.current_account}")
        self.core_manager.check_account_async(self.current_account)
    
    def test_selected_account(self):
        """Тестирование подключения выбранного аккаунта"""
        if not self.current_account:
            messagebox.showwarning("Предупреждение", "Выберите аккаунт для тестирования")
            return
        
        self.log(f"🧪 Тестирую подключение аккаунта: {self.current_account}")
        
        def test_account():
            async def _test():
                try:
                    async def progress_callback(text):
                        self.log(text)
                    
                    result = await account_tester.test_account_connection(
                        self.current_account, progress_callback
                    )
                    
                    if result['success']:
                        user_info = result.get('user_info', {})
                        proxy_info = f" через {result['proxy_used']}" if result['proxy_used'] else ""
                        self.log(f"✅ {self.current_account}: Подключение успешно{proxy_info} ({result['connection_time']}с)")
                        
                        if user_info:
                            name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
                            self.log(f"👤 Пользователь: {name} (@{user_info.get('username', 'без_username')})")
                            self.log(f"📞 Телефон: {user_info.get('phone', 'скрыт')}")
                    else:
                        self.log(f"❌ {self.current_account}: {result['error']}")
                        
                except Exception as e:
                    self.log(f"❌ Критическая ошибка тестирования: {e}")
            
            # Запускаем в event loop
            future = self.core_manager.run_async_task(_test())
            if future:
                future.result()
        
        thread = threading.Thread(target=test_account)
        thread.start()
    
    def check_all_accounts(self):
        """Проверка всех аккаунтов"""
        if not self.accounts:
            messagebox.showwarning("Предупреждение", "Нет аккаунтов для проверки")
            return
        
        result = messagebox.askyesno("Подтверждение", 
                                   f"Запустить тестирование {len(self.accounts)} аккаунтов?\n\n"
                                   "Это может занять несколько минут.")
        if not result:
            return
        
        self.log("🚀 Начинаю тестирование всех аккаунтов...")
        
        def test_all():
            async def _test_all():
                try:
                    async def progress_callback(text):
                        self.log(text)
                    
                    results = await account_tester.test_all_accounts(progress_callback)
                    
                    # Обновляем статусы аккаунтов
                    statuses = storage_manager.load_account_statuses()
                    
                    for result in results:
                        session_name = result['session_name']
                        if result['success']:
                            statuses[session_name] = 'valid'
                        else:
                            if 'забанен' in result['error'].lower():
                                statuses[session_name] = 'invalid'
                            elif '2fa' in result['error'].lower():
                                statuses[session_name] = 'unknown'
                            else:
                                statuses[session_name] = 'invalid'
                    
                    storage_manager.save_account_statuses(statuses)
                    
                    # Обновляем интерфейс
                    self.root.after(0, self.refresh_accounts)
                    
                except Exception as e:
                    self.log(f"❌ Критическая ошибка массового тестирования: {e}")
            
            future = self.core_manager.run_async_task(_test_all())
            if future:
                future.result()
        
        thread = threading.Thread(target=test_all)
        thread.start()
    
    def change_profile(self):
        """Смена профиля аккаунта"""
        if not self.current_account:
            messagebox.showwarning("Предупреждение", "Выберите аккаунт")
            return
        # TODO: Реализовать смену профиля
    
    def delete_account(self):
        """Удаление аккаунта"""
        if not self.current_account:
            messagebox.showwarning("Предупреждение", "Выберите аккаунт для удаления")
            return
        
        result = messagebox.askyesno("Подтверждение", 
                                   f"Вы уверены, что хотите удалить аккаунт {self.current_account}?")
        if result:
            if storage_manager.delete_account(self.current_account):
                self.log(f"Аккаунт {self.current_account} удален")
                self.refresh_accounts()
                self.current_account = None
                self.account_info_text.delete(1.0, tk.END)
            else:
                messagebox.showerror("Ошибка", "Не удалось удалить аккаунт")
    
    def start_parsing(self):
        """Запуск парсинга"""
        account = self.parser_account_var.get()
        parse_type = self.parse_type_var.get()
        export_format = self.export_format_var.get()
        
        if not account:
            messagebox.showwarning("Предупреждение", "Выберите аккаунт для парсинга")
            return
        
        # Получаем цель парсинга в зависимости от типа
        if parse_type == "multiple_usernames":
            target = self.parse_target_text.get(1.0, tk.END).strip()
            if not target or target == "@chat1\n@chat2\nhttps://t.me/chat3\n...":
                messagebox.showwarning("Предупреждение", "Укажите список чатов для парсинга")
                return
        else:
            target = self.parse_target_var.get().strip()
            if not target:
                if parse_type != "dialogs":  # Для dialogs цель не нужна
                    messagebox.showwarning("Предупреждение", "Укажите цель парсинга")
                    return
                else:
                    target = "dialogs"  # Заглушка для dialogs
        
        # Проверка лимита
        limit_str = self.parse_limit_var.get()
        try:
            limit = int(limit_str)
            if limit <= 0:
                raise ValueError("Лимит должен быть положительным числом")
        except ValueError:
            messagebox.showerror("Ошибка", "Лимит должен быть положительным числом")
            return
        
        # Логирование начала парсинга
        if parse_type == "multiple_usernames":
            chat_count = len([line for line in target.split('\n') if line.strip()])
            self.log(f"Начинаю парсинг никнеймов из {chat_count} чатов (аккаунт: {account})")
        else:
            self.log(f"Начинаю парсинг: {parse_type} из {target} (аккаунт: {account})")
        
        self.parse_progress.start()
        self.parse_status_var.set("Выполняется парсинг...")
        
        # Опции парсинга
        options = {
            'limit': limit,
            'export_format': export_format
        }
        
        # Для множественного парсинга добавляем лимит на чат
        if parse_type == "multiple_usernames":
            options['limit_per_chat'] = limit
        
        # Запуск парсинга в отдельном потоке
        def on_parse_complete():
            self.parse_progress.stop()
            self.parse_status_var.set("Парсинг завершен")
            self.refresh_export_files()
        
        thread = self.core_manager.start_parsing_async(account, parse_type, target, options)
        
        # Мониторинг завершения в отдельном потоке
        def monitor_parsing():
            thread.join()
            self.root.after(0, on_parse_complete)
        
        threading.Thread(target=monitor_parsing, daemon=True).start()
    
    def on_parse_type_changed(self, event=None):
        """Обработчик изменения типа парсинга"""
        parse_type = self.parse_type_var.get()
        
        if parse_type == "multiple_usernames":
            # Скрываем обычное поле и показываем текстовое
            self.parse_target_entry.grid_remove()
            self.parse_target_text_label.grid(row=2, column=0, sticky=tk.NW, pady=(10, 0), padx=(0, 5))
            self.parse_target_text.grid(row=2, column=1, columnspan=3, sticky=tk.W, pady=(10, 0))
            
            self.parse_target_label.config(text="Множественный парсинг:")
            
            # Добавляем подсказку в текстовое поле
            self.parse_target_text.delete(1.0, tk.END)
            self.parse_target_text.insert(1.0, "@chat1\n@chat2\nhttps://t.me/chat3\nt.me/joinchat/abc123")
            self.parse_limit_var.set("5000")
        else:
            # Скрываем текстовое поле и показываем обычное
            self.parse_target_text_label.grid_remove()
            self.parse_target_text.grid_remove()
            self.parse_target_entry.grid()
            
            if parse_type == "usernames":
                self.parse_target_label.config(text="Чат/канал:")
                self.parse_limit_var.set("10000")
                self.parse_target_var.set("@example_chat")
            elif parse_type == "members":
                self.parse_target_label.config(text="Чат/канал:")
                self.parse_limit_var.set("10000")
                self.parse_target_var.set("@example_chat")
            elif parse_type == "messages":
                self.parse_target_label.config(text="Чат:")
                self.parse_limit_var.set("1000")
                self.parse_target_var.set("@example_chat")
            elif parse_type == "dialogs":
                self.parse_target_label.config(text="Диалоги аккаунта:")
                self.parse_limit_var.set("1000")
                self.parse_target_var.set("(автоматически)")
    
    def stop_parsing(self):
        """Остановка парсинга"""
        self.parse_progress.stop()
        self.parse_status_var.set("Парсинг остановлен")
        self.log("🛑 Парсинг остановлен пользователем")
    
    def open_export_folder(self):
        """Открытие папки с экспортированными файлами"""
        import subprocess
        import platform
        
        export_dir = os.path.join(storage_manager.DATA_DIR, "exports")
        os.makedirs(export_dir, exist_ok=True)
        
        try:
            if platform.system() == "Windows":
                subprocess.run(["explorer", export_dir])
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", export_dir])
            else:  # Linux
                subprocess.run(["xdg-open", export_dir])
            
            self.log(f"📁 Открыта папка: {export_dir}")
        except Exception as e:
            self.log(f"❌ Не удалось открыть папку: {e}")
            messagebox.showinfo("Путь к файлам", f"Файлы сохраняются в:\n{export_dir}")
    
    def create_task(self):
        """Создание новой задачи"""
        task_name = self.task_name_var.get().strip()
        task_type = self.task_type_var.get()
        
        if not task_name:
            messagebox.showwarning("Предупреждение", "Введите название задачи")
            return
        
        if not task_type:
            messagebox.showwarning("Предупреждение", "Выберите тип задачи")
            return
        
        # Предупреждение для спама по ЛС
        if task_type in ['spam_dm', 'spam_dm_existing']:
            warning_msg = ("⚠️ ВНИМАНИЕ! ВЫСОКИЙ РИСК БЛОКИРОВКИ АККАУНТОВ!\n\n"
                         "Спам по личным сообщениям может привести к:\n"
                         "• Временной блокировке аккаунта\n"
                         "• Постоянному бану\n"
                         "• Ограничениям на отправку сообщений\n\n"
                         "Рекомендуется:\n"
                         "• Использовать минимальные интервалы (60-120 сек)\n"
                         "• Тестировать на 1-2 аккаунтах\n"
                         "• Иметь запасные аккаунты\n\n"
                         "Продолжить создание задачи?")
            
            result = messagebox.askyesno("⚠️ ПРЕДУПРЕЖДЕНИЕ О РИСКАХ", warning_msg)
            if not result:
                return
        
        if storage_manager.create_task(task_name):
            # Установка типа задачи
            tasks = storage_manager.load_tasks()
            tasks[task_name]['type'] = task_type
            
            # Специальные настройки для спама по ЛС
            if task_type in ['spam_dm', 'spam_dm_existing']:
                tasks[task_name]['settings']['dm_spam_warning_accepted'] = True
                tasks[task_name]['settings']['spam_delay_min'] = 60
                tasks[task_name]['settings']['spam_delay_max'] = 120
                tasks[task_name]['settings']['use_existing_dialogs_only'] = (task_type == 'spam_dm_existing')
            
            storage_manager.save_tasks(tasks)
            
            self.log(f"Создана задача: {task_name} ({task_type})")
            self.refresh_tasks()
            self.task_name_var.set("")
            self.task_type_var.set("")
        else:
            messagebox.showerror("Ошибка", "Задача с таким именем уже существует")
    
    def start_task(self):
        """Запуск задачи с проверкой безопасности"""
        selection = self.tasks_tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите задачу для запуска")
            return
        
        item = self.tasks_tree.item(selection[0])
        task_name = item['values'][0]
        
        # Проверяем, что задача не активна
        if self.core_manager.is_task_active(task_name):
            messagebox.showwarning("Предупреждение", "Задача уже выполняется")
            return
        
        # Получаем данные задачи
        task_data = storage_manager.get_task(task_name)
        if not task_data:
            messagebox.showerror("Ошибка", "Задача не найдена")
            return
        
        # Проверка безопасности
        is_safe, safety_message = self.safety_manager.validate_task_safety(task_name, task_data)
        
        if not is_safe:
            messagebox.showerror("Ошибка безопасности", 
                               f"Задача не может быть запущена:\n\n{safety_message}")
            return
        
        # Показываем рекомендации для опасных задач
        task_type = task_data.get('type', '')
        if task_type in ['spam_dm', 'spam_dm_existing', 'spam_chats', 'spam_channels', 'spam_both']:
            recommendations = self.safety_manager.get_recommended_settings(task_type)
            warning = recommendations.get('warning', '')
            
            confirm_msg = f"Запуск задачи: {task_name}\n"
            confirm_msg += f"Тип: {task_type}\n"
            confirm_msg += f"Аккаунтов: {len(task_data.get('accounts', []))}\n\n"
            confirm_msg += f"{warning}\n\n"
            confirm_msg += "Продолжить?"
            
            result = messagebox.askyesno("Подтверждение запуска", confirm_msg)
            if not result:
                return
        
        self.log(f"🚀 Запускаю задачу: {task_name}")
        self.log(f"✅ Проверка безопасности пройдена: {safety_message}")
        
        # Обновляем распределение прокси перед запуском
        accounts = task_data.get('accounts', [])
        if accounts:
            self.proxy_manager.create_proxy_queues(accounts)
        
        self.core_manager.execute_task_async(task_name)
        
        # Обновляем список задач через секунду
        self.root.after(1000, self.refresh_tasks)
    
    def stop_task(self):
        """Остановка задачи"""
        selection = self.tasks_tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите задачу для остановки")
            return
        
        item = self.tasks_tree.item(selection[0])
        task_name = item['values'][0]
        
        if not self.core_manager.is_task_active(task_name):
            messagebox.showwarning("Предупреждение", "Задача не выполняется")
            return
        
        self.log(f"Останавливаю задачу: {task_name}")
        self.core_manager.stop_task(task_name)
        
        # Обновляем список задач через секунду
        self.root.after(1000, self.refresh_tasks)
    
    def task_settings(self):
        """Настройки задачи"""
        selection = self.tasks_tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите задачу")
            return
        
        item = self.tasks_tree.item(selection[0])
        task_name = item['values'][0]
        
        self.open_task_settings_window(task_name)
    
    def open_task_settings_window(self, task_name):
        """Открытие окна настроек задачи"""
        task_data = storage_manager.get_task(task_name)
        if not task_data:
            messagebox.showerror("Ошибка", "Задача не найдена")
            return
        
        # Создаем окно настроек
        settings_window = tk.Toplevel(self.root)
        settings_window.title(f"Настройки задачи: {task_name}")
        settings_window.geometry("600x500")
        settings_window.configure(bg='#2b2b2b')
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        # Основная информация
        info_frame = ttk.LabelFrame(settings_window, text="Информация о задаче", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=10)
        
        task_type = task_data.get('type', 'Не задан')
        task_settings = task_data.get('settings', {})
        
        info_text = f"Название: {task_name}\n"
        info_text += f"Тип: {task_type}\n"
        info_text += f"Аккаунтов: {len(task_data.get('accounts', []))}"
        
        ttk.Label(info_frame, text=info_text).pack(anchor=tk.W)
        
        # Рекомендации безопасности
        recommendations = self.safety_manager.get_recommended_settings(task_type)
        if recommendations:
            safety_frame = ttk.LabelFrame(settings_window, text="Рекомендации безопасности", padding=10)
            safety_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
            
            safety_text = f"Макс. воркеров: {recommendations.get('max_workers', 5)}\n"
            safety_text += f"Интервал: {recommendations.get('delay_min', 30)}-{recommendations.get('delay_max', 90)} сек\n"
            safety_text += f"Дневной лимит: {recommendations.get('daily_limit', 50)}\n\n"
            safety_text += f"{recommendations.get('warning', '')}"
            
            safety_label = ttk.Label(safety_frame, text=safety_text, wraplength=550)
            safety_label.pack(anchor=tk.W)
        
        # Настройки
        settings_frame = ttk.LabelFrame(settings_window, text="Настройки", padding=10)
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Воркеры
        ttk.Label(settings_frame, text="Количество воркеров:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        workers_var = tk.StringVar(value=str(task_settings.get('concurrent_workers', 5)))
        workers_entry = ttk.Entry(settings_frame, textvariable=workers_var, width=10)
        workers_entry.grid(row=0, column=1, sticky=tk.W)
        
        # Интервал
        ttk.Label(settings_frame, text="Интервал (мин-макс):").grid(row=1, column=0, sticky=tk.W, pady=(10, 0), padx=(0, 10))
        interval = task_settings.get('broadcast_interval', [30, 90])
        interval_var = tk.StringVar(value=f"{interval[0]}-{interval[1]}")
        interval_entry = ttk.Entry(settings_frame, textvariable=interval_var, width=15)
        interval_entry.grid(row=1, column=1, sticky=tk.W, pady=(10, 0))
        
        # 2FA пароль
        ttk.Label(settings_frame, text="Пароль 2FA:").grid(row=2, column=0, sticky=tk.W, pady=(10, 0), padx=(0, 10))
        twofa_var = tk.StringVar(value=task_settings.get('two_fa_password', ''))
        twofa_entry = ttk.Entry(settings_frame, textvariable=twofa_var, width=20, show='*')
        twofa_entry.grid(row=2, column=1, sticky=tk.W, pady=(10, 0))
        
        # Кнопки
        buttons_frame = ttk.Frame(settings_window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def save_settings():
            try:
                # Сохраняем настройки
                workers = int(workers_var.get())
                interval_str = interval_var.get()
                min_val, max_val = map(int, interval_str.split('-'))
                
                tasks = storage_manager.load_tasks()
                if task_name in tasks:
                    tasks[task_name]['settings']['concurrent_workers'] = workers
                    tasks[task_name]['settings']['broadcast_interval'] = [min_val, max_val]
                    tasks[task_name]['settings']['two_fa_password'] = twofa_var.get()
                    storage_manager.save_tasks(tasks)
                    
                    self.log(f"💾 Настройки задачи {task_name} сохранены")
                    self.refresh_tasks()
                    settings_window.destroy()
                
            except ValueError:
                messagebox.showerror("Ошибка", "Проверьте правильность введенных данных")
        
        ttk.Button(buttons_frame, text="💾 Сохранить", command=save_settings).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(buttons_frame, text="❌ Отмена", command=settings_window.destroy).pack(side=tk.LEFT)
    
    def delete_task(self):
        """Удаление задачи"""
        selection = self.tasks_tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите задачу для удаления")
            return
        
        item = self.tasks_tree.item(selection[0])
        task_name = item['values'][0]
        
        result = messagebox.askyesno("Подтверждение", 
                                   f"Вы уверены, что хотите удалить задачу {task_name}?")
        if result:
            if storage_manager.delete_task(task_name):
                self.log(f"Задача {task_name} удалена")
                self.refresh_tasks()
            else:
                messagebox.showerror("Ошибка", "Не удалось удалить задачу")
    
    def add_proxy(self):
        """Добавление прокси"""
        # TODO: Открыть диалог добавления прокси
        pass
    
    def load_proxy_file(self):
        """Загрузка прокси из файла"""
        filename = filedialog.askopenfilename(
            title="Выберите файл с прокси",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    proxies = [line.strip() for line in f if line.strip()]
                
                settings = storage_manager.load_settings()
                settings.setdefault('proxies', []).extend(proxies)
                settings['proxies'] = sorted(list(set(settings['proxies'])))
                storage_manager.save_settings(settings)
                
                self.log(f"Загружено прокси: {len(proxies)}")
                self.refresh_proxy_list()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить прокси: {e}")
    
    def refresh_proxy_list(self):
        """Обновление списка прокси"""
        # Очищаем дерево
        for item in self.proxy_tree.get_children():
            self.proxy_tree.delete(item)
        
        settings = storage_manager.load_settings()
        proxies = settings.get('proxies', [])
        proxy_statuses = settings.get('proxy_statuses', {})
        
        for proxy in proxies:
            status_info = proxy_statuses.get(proxy, {})
            status = status_info.get('status', 'Не проверен')
            country = status_info.get('country', 'N/A')
            response_time = status_info.get('response_time', 0)
            
            # Цветовая индикация
            tags = []
            if status == 'working':
                tags.append('working')
            elif status == 'not_working':
                tags.append('not_working')
            
            time_str = f"{response_time}s" if response_time > 0 else "N/A"
            
            self.proxy_tree.insert('', tk.END, values=(proxy, status, country, time_str), tags=tags)
        
        # Настраиваем цвета
        self.proxy_tree.tag_configure('working', background='#2d5a2d')
        self.proxy_tree.tag_configure('not_working', background='#5a2d2d')
        
        # Обновляем статистику
        self.update_proxy_stats()
    
    def update_proxy_stats(self):
        """Обновление статистики прокси"""
        stats = self.proxy_manager.get_proxy_statistics()
        
        stats_text = f"📊 Всего прокси: {stats['total_proxies']}\n"
        stats_text += f"✅ Рабочих: {stats['working_proxies']}\n"
        stats_text += f"❌ Нерабочих: {stats['not_working_proxies']}\n"
        stats_text += f"❔ Не проверено: {stats['untested_proxies']}\n\n"
        stats_text += f"⚙️ Аккаунтов на прокси: {stats['accounts_per_proxy']}\n\n"
        
        if stats['distribution']:
            stats_text += "📋 Распределение:\n"
            for proxy, accounts in list(stats['distribution'].items())[:3]:
                proxy_short = f"{proxy.split(':')[0]}:{proxy.split(':')[1]}"
                stats_text += f"{proxy_short}: {len(accounts)} акк.\n"
            if len(stats['distribution']) > 3:
                stats_text += f"... и еще {len(stats['distribution']) - 3}\n"
        
        self.proxy_stats_text.delete(1.0, tk.END)
        self.proxy_stats_text.insert(1.0, stats_text)
    
    def update_proxy_distribution(self):
        """Обновление распределения аккаунтов по прокси"""
        try:
            accounts_per_proxy = int(self.accounts_per_proxy_var.get())
            self.proxy_manager.set_accounts_per_proxy(accounts_per_proxy)
            
            # Создаем новое распределение
            accounts = storage_manager.list_accounts()
            if accounts:
                proxy_queues = self.proxy_manager.create_proxy_queues(accounts)
                self.log(f"🔄 Обновлено распределение: {accounts_per_proxy} аккаунтов на прокси")
                self.update_proxy_stats()
            
        except ValueError:
            messagebox.showerror("Ошибка", "Количество аккаунтов должно быть числом от 1 до 10")
    
    def show_proxy_distribution(self):
        """Показать подробное распределение прокси"""
        stats = self.proxy_manager.get_proxy_statistics()
        
        if not stats['distribution']:
            messagebox.showinfo("Распределение", "Нет активного распределения аккаунтов по прокси")
            return
        
        distribution_text = "📊 Распределение аккаунтов по прокси:\n\n"
        
        for proxy, accounts in stats['distribution'].items():
            proxy_short = f"{proxy.split(':')[0]}:{proxy.split(':')[1]}"
            distribution_text += f"🌐 {proxy_short}:\n"
            for account in accounts:
                distribution_text += f"  • {account}\n"
            distribution_text += "\n"
        
        # Создаем окно для показа распределения
        distribution_window = tk.Toplevel(self.root)
        distribution_window.title("Распределение прокси")
        distribution_window.geometry("500x400")
        distribution_window.configure(bg='#2b2b2b')
        
        text_widget = scrolledtext.ScrolledText(distribution_window, bg='#404040', fg='white', 
                                              font=('Consolas', 10), wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_widget.insert(1.0, distribution_text)
        text_widget.config(state=tk.DISABLED)
    
    def add_proxy(self):
        """Добавление прокси вручную"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Добавить прокси")
        dialog.geometry("400x200")
        dialog.configure(bg='#2b2b2b')
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Формат: ip:port:username:password").pack(pady=10)
        
        entry_var = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=entry_var, width=40)
        entry.pack(pady=10)
        entry.focus()
        
        def add_proxy_action():
            proxy_str = entry_var.get().strip()
            if not proxy_str:
                return
            
            # Валидация формата
            parts = proxy_str.split(':')
            if len(parts) != 4:
                messagebox.showerror("Ошибка", "Неверный формат прокси")
                return
            
            try:
                int(parts[1])  # Проверяем порт
            except ValueError:
                messagebox.showerror("Ошибка", "Порт должен быть числом")
                return
            
            # Добавляем прокси
            settings = storage_manager.load_settings()
            if proxy_str not in settings.get('proxies', []):
                settings.setdefault('proxies', []).append(proxy_str)
                storage_manager.save_settings(settings)
                self.log(f"➕ Добавлен прокси: {parts[0]}:{parts[1]}")
                self.refresh_proxy_list()
                dialog.destroy()
            else:
                messagebox.showwarning("Предупреждение", "Такой прокси уже существует")
        
        ttk.Button(dialog, text="Добавить", command=add_proxy_action).pack(pady=10)
        ttk.Button(dialog, text="Отмена", command=dialog.destroy).pack()
        
        # Обработка Enter
        entry.bind('<Return>', lambda e: add_proxy_action())
    
    def remove_non_working_proxies(self):
        """Удаление всех нерабочих прокси"""
        removed_count = self.proxy_manager.remove_non_working_proxies()
        
        if removed_count > 0:
            self.log(f"🗑️ Удалено {removed_count} нерабочих прокси")
            self.refresh_proxy_list()
            messagebox.showinfo("Успех", f"Удалено {removed_count} нерабочих прокси")
        else:
            messagebox.showinfo("Информация", "Нет нерабочих прокси для удаления")
    
    def delete_selected_proxies(self):
        """Удаление выбранных прокси"""
        selection = self.proxy_tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите прокси для удаления")
            return
        
        proxies_to_delete = []
        for item in selection:
            values = self.proxy_tree.item(item)['values']
            proxies_to_delete.append(values[0])
        
        result = messagebox.askyesno("Подтверждение", 
                                   f"Удалить {len(proxies_to_delete)} выбранных прокси?")
        if result:
            settings = storage_manager.load_settings()
            for proxy in proxies_to_delete:
                if proxy in settings.get('proxies', []):
                    settings['proxies'].remove(proxy)
                # Удаляем статус
                if proxy in settings.get('proxy_statuses', {}):
                    del settings['proxy_statuses'][proxy]
            
            storage_manager.save_settings(settings)
            self.log(f"🗑️ Удалено {len(proxies_to_delete)} прокси")
            self.refresh_proxy_list()
    
    def refresh_export_files(self):
        """Обновление списка экспортированных файлов"""
        try:
            export_files = storage_manager.get_export_files()
            # Обновляем таблицу результатов парсинга
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            
            if export_files:
                # Настраиваем колонки для файлов
                self.results_tree['columns'] = ('Файл', 'Размер', 'Дата')
                for col in self.results_tree['columns']:
                    self.results_tree.heading(col, text=col)
                    self.results_tree.column(col, width=150)
                
                for file_info in export_files[:10]:  # Показываем последние 10 файлов
                    size_mb = round(file_info['size'] / 1024 / 1024, 2)
                    date_str = datetime.fromtimestamp(file_info['modified']).strftime("%Y-%m-%d %H:%M")
                    
                    self.results_tree.insert('', tk.END, values=(
                        file_info['filename'],
                        f"{size_mb} MB",
                        date_str
                    ))
        except Exception as e:
            self.log(f"Ошибка обновления экспортированных файлов: {e}")
    
    def check_proxies(self):
        """Проверка прокси с использованием ProxyManager"""
        settings = storage_manager.load_settings()
        proxies = settings.get('proxies', [])
        
        if not proxies:
            messagebox.showwarning("Предупреждение", "Нет прокси для проверки")
            return
        
        result = messagebox.askyesno("Подтверждение", 
                                   f"Проверить {len(proxies)} прокси?\n\n"
                                   "Это может занять несколько минут.")
        if not result:
            return
        
        self.log(f"🔍 Начинаю проверку {len(proxies)} прокси...")
        
        def check_all_proxies():
            async def _check_proxies():
                try:
                    async def progress_callback(msg):
                        await self._async_log(msg)
                    
                    # Используем новый ProxyManager
                    results = await self.proxy_manager.test_all_proxies(progress_callback)
                    
                    # Обновляем интерфейс
                    self.root.after(0, self.refresh_proxy_list)
                    
                    # Показываем результаты
                    working_count = len(results['working'])
                    not_working_count = len(results['not_working'])
                    
                    result_msg = f"📊 Проверка завершена:\n\n"
                    result_msg += f"✅ Рабочих прокси: {working_count}\n"
                    result_msg += f"❌ Нерабочих прокси: {not_working_count}\n\n"
                    
                    if not_working_count > 0:
                        result_msg += "Удалить нерабочие прокси?"
                        self.root.after(0, lambda: self._show_proxy_results(result_msg, not_working_count > 0))
                    else:
                        self.root.after(0, lambda: messagebox.showinfo("Результат", result_msg))
                    
                except Exception as e:
                    await self._async_log(f"❌ Критическая ошибка проверки прокси: {e}")
            
            future = self.core_manager.run_async_task(_check_proxies())
            if future:
                future.result()
        
        thread = threading.Thread(target=check_all_proxies)
        thread.start()
    
    def _show_proxy_results(self, message, offer_delete):
        """Показ результатов проверки прокси"""
        if offer_delete:
            result = messagebox.askyesno("Результат проверки", message)
            if result:
                self.remove_non_working_proxies()
        else:
            messagebox.showinfo("Результат проверки", message)
    
    async def _async_log(self, message):
        """Асинхронное логирование"""
        self.root.after(0, lambda: self.log(message))
    
    def delete_proxy(self):
        """Удаление выбранных прокси"""
        # TODO: Реализовать удаление прокси
        pass
    
    def export_settings(self):
        """Экспорт настроек"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                settings = storage_manager.load_settings()
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(settings, f, ensure_ascii=False, indent=2)
                self.log(f"Настройки экспортированы в: {filename}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось экспортировать настройки: {e}")
    
    def import_settings(self):
        """Импорт настроек"""
        filename = filedialog.askopenfilename(
            title="Выберите файл настроек",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                storage_manager.save_settings(settings)
                self.log(f"Настройки импортированы из: {filename}")
                self.refresh_accounts()
                self.refresh_tasks()
                self.refresh_proxy_list()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось импортировать настройки: {e}")
    
    def on_closing(self):
        """Обработка закрытия приложения"""
        # Остановка всех активных задач
        active_tasks = self.core_manager.get_active_tasks()
        if active_tasks:
            result = messagebox.askyesno("Подтверждение", 
                                       f"Есть {len(active_tasks)} активных задач. Остановить их и выйти?")
            if not result:
                return
            
            for task_name in active_tasks:
                self.core_manager.stop_task(task_name)
            
            # Ждем немного для корректного завершения
            self.root.after(2000, self._force_close)
        else:
            self._force_close()
    
    def _force_close(self):
        """Принудительное закрытие приложения"""
        self.core_manager.shutdown()
        self.root.quit()
        self.root.destroy()
    
    def run(self):
        """Запуск приложения"""
        # Первоначальная загрузка данных
        self.refresh_accounts()
        self.refresh_tasks()
        self.refresh_proxy_list()
        self.refresh_export_files()
        
        # Инициализация интерфейса парсера
        self.on_parse_type_changed()
        
        self.log("Приложение запущено")
        self.log(f"Загружено аккаунтов: {len(self.accounts)}")
        self.log(f"Загружено задач: {len(self.tasks)}")
        
        # Запуск главного цикла
        self.root.mainloop()

if __name__ == "__main__":
    app = TelegramManagerGUI()
    app.run()