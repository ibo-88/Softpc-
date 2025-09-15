# gui_app.py

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
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
        
        # Инициализация core manager
        self.core_manager = core_manager.get_core_manager(self.log)
        
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
        top_frame = ttk.LabelFrame(parser_frame, text="Настройки парсинга", padding=10)
        top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Выбор аккаунта для парсинга
        ttk.Label(top_frame, text="Аккаунт для парсинга:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.parser_account_var = tk.StringVar()
        self.parser_account_combo = ttk.Combobox(top_frame, textvariable=self.parser_account_var, width=30)
        self.parser_account_combo.grid(row=0, column=1, padx=(0, 20))
        
        # Тип парсинга
        ttk.Label(top_frame, text="Тип парсинга:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.parse_type_var = tk.StringVar(value="usernames")
        parse_type_combo = ttk.Combobox(top_frame, textvariable=self.parse_type_var, 
                                      values=["usernames", "members", "multiple_usernames", "messages", "dialogs"], 
                                      width=18, state="readonly")
        parse_type_combo.grid(row=0, column=3)
        
        # Привязываем событие изменения типа парсинга
        parse_type_combo.bind('<<ComboboxSelected>>', self.on_parse_type_changed)
        
        # Цель парсинга
        self.parse_target_label = ttk.Label(top_frame, text="Цель (ссылка/username):")
        self.parse_target_label.grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        self.parse_target_var = tk.StringVar()
        self.parse_target_entry = ttk.Entry(top_frame, textvariable=self.parse_target_var, width=50)
        self.parse_target_entry.grid(row=1, column=1, columnspan=2, sticky=tk.W, pady=(10, 0), padx=(0, 20))
        
        # Текстовое поле для множественного парсинга (скрыто по умолчанию)
        self.parse_target_text = tk.Text(top_frame, height=4, width=50)
        self.parse_target_text.grid(row=2, column=1, columnspan=2, sticky=tk.W, pady=(5, 0), padx=(0, 20))
        self.parse_target_text.grid_remove()  # Скрываем изначально
        
        # Лимит
        self.parse_limit_label = ttk.Label(top_frame, text="Лимит:")
        self.parse_limit_label.grid(row=1, column=2, sticky=tk.W, pady=(10, 0), padx=(20, 10))
        self.parse_limit_var = tk.StringVar(value="10000")
        self.parse_limit_entry = ttk.Entry(top_frame, textvariable=self.parse_limit_var, width=10)
        self.parse_limit_entry.grid(row=1, column=3, pady=(10, 0))
        
        # Формат экспорта
        ttk.Label(top_frame, text="Формат экспорта:").grid(row=3, column=0, sticky=tk.W, pady=(10, 0))
        self.export_format_var = tk.StringVar(value="txt")
        format_combo = ttk.Combobox(top_frame, textvariable=self.export_format_var, 
                                  values=["txt", "csv", "json"], width=10, state="readonly")
        format_combo.grid(row=3, column=1, sticky=tk.W, pady=(10, 0))
        
        # Кнопка запуска
        ttk.Button(top_frame, text="🚀 Начать парсинг", 
                  command=self.start_parsing).grid(row=3, column=3, pady=(10, 0))
        
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
            "check_all", "change_profile:name", "change_profile:avatar",
            "create_channel", "join_chats", "start_broadcast",
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
        
        # Настройки прокси
        proxy_frame = ttk.LabelFrame(settings_frame, text="Прокси", padding=10)
        proxy_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Список прокси
        proxy_list_frame = ttk.Frame(proxy_frame)
        proxy_list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.proxy_listbox = tk.Listbox(proxy_list_frame, bg='#404040', fg='white', 
                                       selectbackground='#606060', height=15)
        proxy_scrollbar = ttk.Scrollbar(proxy_list_frame, orient=tk.VERTICAL, command=self.proxy_listbox.yview)
        self.proxy_listbox.configure(yscrollcommand=proxy_scrollbar.set)
        
        self.proxy_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        proxy_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Кнопки управления прокси
        proxy_buttons_frame = ttk.Frame(proxy_frame)
        proxy_buttons_frame.pack(fill=tk.X)
        
        ttk.Button(proxy_buttons_frame, text="Добавить прокси", 
                  command=self.add_proxy).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(proxy_buttons_frame, text="Загрузить из файла", 
                  command=self.load_proxy_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(proxy_buttons_frame, text="Проверить все", 
                  command=self.check_proxies).pack(side=tk.LEFT, padx=5)
        ttk.Button(proxy_buttons_frame, text="Удалить выбранные", 
                  command=self.delete_proxy).pack(side=tk.LEFT, padx=5)
    
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
        
        # Получение информации
        statuses = storage_manager.load_account_statuses()
        status = statuses.get(account_name, 'unknown')
        
        info_text = f"Аккаунт: {account_name}\n"
        info_text += f"Статус: {status}\n"
        info_text += f"Файл сессии: {account_name}.session\n"
        info_text += f"Конфигурация: {account_name}.json\n"
        
        # Проверка файлов
        session_path = os.path.join(storage_manager.SESSIONS_DIR, f"{account_name}.session")
        json_path = os.path.join(storage_manager.SESSIONS_DIR, f"{account_name}.json")
        
        info_text += f"Файл сессии существует: {'Да' if os.path.exists(session_path) else 'Нет'}\n"
        info_text += f"JSON конфиг существует: {'Да' if os.path.exists(json_path) else 'Нет'}\n"
        
        # Информация о задачах
        tasks_using_account = [name for name, data in self.tasks.items() 
                             if account_name in data.get('accounts', [])]
        info_text += f"Используется в задачах: {', '.join(tasks_using_account) if tasks_using_account else 'Нет'}\n"
        
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
        """Загрузка сессий из ZIP файла"""
        filename = filedialog.askopenfilename(
            title="Выберите ZIP архив с сессиями",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")]
        )
        if filename:
            try:
                storage_manager.unpack_zip(filename, storage_manager.SESSIONS_DIR)
                self.refresh_accounts()
                self.log(f"Сессии загружены из: {filename}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить сессии: {e}")
    
    def check_selected_account(self):
        """Проверка выбранного аккаунта"""
        if not self.current_account:
            messagebox.showwarning("Предупреждение", "Выберите аккаунт для проверки")
            return
        
        self.log(f"Начинаю проверку аккаунта: {self.current_account}")
        self.core_manager.check_account_async(self.current_account)
    
    def check_all_accounts(self):
        """Проверка всех аккаунтов"""
        if not self.accounts:
            messagebox.showwarning("Предупреждение", "Нет аккаунтов для проверки")
            return
        
        self.log("Начинаю проверку всех аккаунтов...")
        self.core_manager.check_all_accounts_async(self.accounts)
    
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
            # Показываем текстовое поле для списка чатов
            self.parse_target_entry.grid_remove()
            self.parse_target_text.grid()
            self.parse_target_label.config(text="Список чатов (по одному на строку):")
            self.parse_limit_label.config(text="Лимит на чат:")
            self.parse_limit_var.set("5000")
            
            # Добавляем подсказку в текстовое поле
            self.parse_target_text.delete(1.0, tk.END)
            self.parse_target_text.insert(1.0, "@chat1\n@chat2\nhttps://t.me/chat3\n...")
        else:
            # Показываем обычное поле ввода
            self.parse_target_text.grid_remove()
            self.parse_target_entry.grid()
            
            if parse_type == "usernames":
                self.parse_target_label.config(text="Чат/канал для парсинга никнеймов:")
                self.parse_limit_label.config(text="Лимит:")
                self.parse_limit_var.set("10000")
            elif parse_type == "members":
                self.parse_target_label.config(text="Чат/канал для парсинга участников:")
                self.parse_limit_label.config(text="Лимит:")
                self.parse_limit_var.set("10000")
            elif parse_type == "messages":
                self.parse_target_label.config(text="Чат для парсинга сообщений:")
                self.parse_limit_label.config(text="Лимит:")
                self.parse_limit_var.set("1000")
            elif parse_type == "dialogs":
                self.parse_target_label.config(text="Аккаунт (игнорируется):")
                self.parse_limit_label.config(text="Лимит:")
                self.parse_limit_var.set("1000")
    
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
        
        if storage_manager.create_task(task_name):
            # Установка типа задачи
            tasks = storage_manager.load_tasks()
            tasks[task_name]['type'] = task_type
            storage_manager.save_tasks(tasks)
            
            self.log(f"Создана задача: {task_name} ({task_type})")
            self.refresh_tasks()
            self.task_name_var.set("")
            self.task_type_var.set("")
        else:
            messagebox.showerror("Ошибка", "Задача с таким именем уже существует")
    
    def start_task(self):
        """Запуск задачи"""
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
        
        self.log(f"Запускаю задачу: {task_name}")
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
        
        # TODO: Открыть окно настроек задачи
        self.log(f"Открываю настройки задачи: {task_name}")
    
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
        self.proxy_listbox.delete(0, tk.END)
        
        settings = storage_manager.load_settings()
        proxies = settings.get('proxies', [])
        
        for proxy in proxies:
            self.proxy_listbox.insert(tk.END, proxy)
    
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
        """Проверка прокси"""
        self.log("Начинаю проверку прокси...")
        # TODO: Реализовать проверку прокси
    
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