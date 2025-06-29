#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Version: 1.0.0
Author: @OxenFxc
Copyright: https://github.com/OxenFxc
License: MIT License
Description: B站多账号扫码登录系统 - 自动私信回复功能
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
from typing import Optional

from ..core import AccountManager
from ..utils import Config, format_time, show_message, confirm_dialog, center_window, ask_string
from .login_window import LoginWindow
from .account_window import AccountWindow
from .message_window import MessageWindow


class MainWindow:
    def __init__(self):
        """初始化主窗口"""
        self.config = Config()
        self.account_manager = AccountManager(self.config.get_accounts_file())
        
        # 窗口实例管理
        self.message_windows = {}  # {uid: MessageWindow实例}
        
        # 创建主窗口
        self.root = tk.Tk()
        self.root.title("B站多账号登录管理器")
        self.root.iconname("BiliLogin")
        
        # 设置窗口配置
        window_config = self.config.get_window_config()
        self.root.minsize(window_config.get('min_width', 600), window_config.get('min_height', 400))
        
        if window_config.get('center_on_screen', True):
            center_window(self.root, window_config.get('width', 800), window_config.get('height', 600))
        
        # 初始化UI
        self.init_ui()
        
        # 绑定事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 启动时刷新账号列表
        self.refresh_accounts()
    
    def init_ui(self):
        """初始化用户界面"""
        # 设置样式
        style = ttk.Style()
        style.theme_use('clam')  # 使用现代主题
        
        # 自定义样式
        style.configure('Title.TLabel', font=('微软雅黑', 16, 'bold'), foreground='#2c3e50')
        style.configure('Subtitle.TLabel', font=('微软雅黑', 10), foreground='#7f8c8d')
        style.configure('Header.TLabel', font=('微软雅黑', 12, 'bold'), foreground='#34495e')
        style.configure('Status.TLabel', font=('微软雅黑', 9), background='#ecf0f1', relief='sunken', padding=(10, 5))
        style.configure('Action.TButton', font=('微软雅黑', 9, 'bold'), padding=(10, 5))
        
        # 主容器
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 标题区域
        header_frame = ttk.Frame(main_container)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        # 应用图标和标题
        title_container = ttk.Frame(header_frame)
        title_container.pack(anchor='w')
        
        app_title = ttk.Label(title_container, text="🎬 B站多账号管理系统", style='Title.TLabel')
        app_title.pack(anchor='w')
        
        subtitle = ttk.Label(title_container, text="Multi-Account Management & Auto-Reply System", style='Subtitle.TLabel')
        subtitle.pack(anchor='w', pady=(2, 0))
        
        # 主要内容区域
        content_frame = ttk.Frame(main_container)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # 配置网格权重
        content_frame.columnconfigure(1, weight=2)
        content_frame.columnconfigure(2, weight=1)
        content_frame.rowconfigure(0, weight=1)
        
        # 左侧控制面板
        self.create_control_panel(content_frame)
        
        # 中间账号列表区域
        self.create_account_list_panel(content_frame)
        
        # 右侧信息面板
        self.create_info_panel(content_frame)
        
        # 底部状态栏
        self.create_status_bar(main_container)
    
    def create_control_panel(self, parent):
        """创建左侧控制面板"""
        control_frame = ttk.LabelFrame(parent, text="🎛️ 操作面板", padding="15")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        # 账号管理组
        account_group = ttk.LabelFrame(control_frame, text="账号管理", padding="10")
        account_group.pack(fill=tk.X, pady=(0, 15))
        
        # 账号管理按钮
        buttons_config = [
            ("➕ 新增账号", self.add_account, "#27ae60", "添加新的B站账号"),
            ("🔄 刷新状态", self.refresh_accounts, "#3498db", "刷新所有账号状态"),
            ("🗑️ 删除账号", self.delete_account, "#e74c3c", "删除选中的账号"),
            ("✏️ 重命名", self.rename_account, "#f39c12", "修改账号显示名称")
        ]
        
        for i, (text, command, color, tooltip) in enumerate(buttons_config):
            btn = ttk.Button(account_group, text=text, command=command, width=15)
            btn.pack(fill=tk.X, pady=2)
            # 这里可以添加tooltip功能
        
        # 功能管理组
        function_group = ttk.LabelFrame(control_frame, text="功能管理", padding="10")
        function_group.pack(fill=tk.X, pady=(0, 15))
        
        function_buttons = [
            ("🔐 切换登录", self.switch_account, "切换当前使用的账号"),
            ("📝 账号详情", self.show_account_details, "查看账号详细信息"),
            ("💬 私信管理", self.show_message_window, "管理私信和自动回复"),
            ("⚙️ 系统设置", self.show_settings, "应用程序设置")
        ]
        
        for text, command, tooltip in function_buttons:
            btn = ttk.Button(function_group, text=text, command=command, width=15)
            btn.pack(fill=tk.X, pady=2)
        
        # 统计信息组
        stats_group = ttk.LabelFrame(control_frame, text="统计信息", padding="10")
        stats_group.pack(fill=tk.X, pady=(0, 15))
        
        # 统计标签
        self.stats_total_label = ttk.Label(stats_group, text="📊 总账号: 0", font=('微软雅黑', 9))
        self.stats_total_label.pack(anchor='w', pady=1)
        
        self.stats_active_label = ttk.Label(stats_group, text="✅ 有效账号: 0", font=('微软雅黑', 9), foreground='green')
        self.stats_active_label.pack(anchor='w', pady=1)
        
        self.stats_invalid_label = ttk.Label(stats_group, text="❌ 失效账号: 0", font=('微软雅黑', 9), foreground='red')
        self.stats_invalid_label.pack(anchor='w', pady=1)
        
        # 快捷操作组
        quick_group = ttk.LabelFrame(control_frame, text="快捷操作", padding="10")
        quick_group.pack(fill=tk.X)
        
        ttk.Button(quick_group, text="🚀 快速登录", command=self.quick_login, width=15).pack(fill=tk.X, pady=2)
        ttk.Button(quick_group, text="📊 查看日志", command=self.show_logs, width=15).pack(fill=tk.X, pady=2)
        ttk.Button(quick_group, text="🆘 帮助", command=self.show_help, width=15).pack(fill=tk.X, pady=2)
    
    def create_account_list_panel(self, parent):
        """创建中间账号列表面板"""
        list_frame = ttk.LabelFrame(parent, text="📋 账号列表", padding="10")
        list_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(1, weight=1)
        
        # 工具栏
        toolbar_frame = ttk.Frame(list_frame)
        toolbar_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 搜索框
        search_frame = ttk.Frame(toolbar_frame)
        search_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(search_frame, text="🔍").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30, font=('微软雅黑', 9))
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        search_entry.bind('<KeyRelease>', self.on_search)
        
        # 视图切换按钮
        view_frame = ttk.Frame(toolbar_frame)
        view_frame.pack(side=tk.RIGHT)
        
        self.view_mode = tk.StringVar(value="detailed")
        ttk.Radiobutton(view_frame, text="详细", variable=self.view_mode, 
                       value="detailed", command=self.change_view_mode).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(view_frame, text="简洁", variable=self.view_mode, 
                       value="simple", command=self.change_view_mode).pack(side=tk.LEFT)
        
        # 账号列表
        list_container = ttk.Frame(list_frame)
        list_container.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        list_container.columnconfigure(0, weight=1)
        list_container.rowconfigure(0, weight=1)
        
        # 创建Treeview
        columns = ('status', 'name', 'uid', 'login_time', 'auto_reply')
        self.tree = ttk.Treeview(list_container, columns=columns, show='headings', height=15)
        
        # 设置列标题和样式
        headers = {
            'status': ('状态', 80, 'center'),
            'name': ('账号名称', 200, 'w'),
            'uid': ('用户ID', 120, 'center'),
            'login_time': ('登录时间', 150, 'center'),
            'auto_reply': ('自动回复', 100, 'center')
        }
        
        for col, (text, width, anchor) in headers.items():
            self.tree.heading(col, text=text, command=lambda c=col: self.sort_column(c))
            self.tree.column(col, width=width, anchor=anchor, minwidth=50)
        
        # 添加滚动条
        v_scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(list_container, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # 布局
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # 绑定事件
        self.tree.bind('<Double-1>', self.on_account_double_click)
        self.tree.bind('<Button-3>', self.show_context_menu)
        self.tree.bind('<ButtonRelease-1>', self.on_account_select)
        
        # 创建右键菜单
        self.create_context_menu()
    
    def create_info_panel(self, parent):
        """创建右侧信息面板"""
        info_frame = ttk.LabelFrame(parent, text="ℹ️ 账号信息", padding="10")
        info_frame.grid(row=0, column=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 0))
        info_frame.columnconfigure(0, weight=1)
        info_frame.rowconfigure(1, weight=1)
        
        # 快速信息栏
        quick_info_frame = ttk.Frame(info_frame)
        quick_info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 当前账号状态卡片
        self.current_account_card = ttk.LabelFrame(quick_info_frame, text="当前账号", padding="10")
        self.current_account_card.pack(fill=tk.X, pady=(0, 10))
        
        self.current_account_name = ttk.Label(self.current_account_card, text="未选择", 
                                            font=('微软雅黑', 10, 'bold'), foreground='#2c3e50')
        self.current_account_name.pack(anchor='w')
        
        self.current_account_status = ttk.Label(self.current_account_card, text="状态: 未知", 
                                              font=('微软雅黑', 9), foreground='#7f8c8d')
        self.current_account_status.pack(anchor='w')
        
        # 自动回复状态卡片
        self.auto_reply_card = ttk.LabelFrame(quick_info_frame, text="自动回复", padding="10")
        self.auto_reply_card.pack(fill=tk.X)
        
        self.auto_reply_status = ttk.Label(self.auto_reply_card, text="未启用", 
                                         font=('微软雅黑', 9), foreground='#e74c3c')
        self.auto_reply_status.pack(anchor='w')
        
        self.auto_reply_count = ttk.Label(self.auto_reply_card, text="今日回复: 0", 
                                        font=('微软雅黑', 8), foreground='#7f8c8d')
        self.auto_reply_count.pack(anchor='w')
        
        # 详细信息区域
        details_container = ttk.Frame(info_frame)
        details_container.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        details_container.columnconfigure(0, weight=1)
        details_container.rowconfigure(0, weight=1)
        
        # 详细信息文本框
        self.current_info = scrolledtext.ScrolledText(
            details_container, 
            wrap=tk.WORD, 
            state=tk.DISABLED,
            font=('微软雅黑', 9),
            bg='#f8f9fa',
            relief='solid',
            borderwidth=1,
            padx=10,
            pady=10
        )
        self.current_info.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 操作按钮组
        action_frame = ttk.Frame(info_frame)
        action_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        ttk.Button(action_frame, text="🔄 刷新信息", command=self.refresh_current_info,
                  width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_frame, text="📋 复制信息", command=self.copy_account_info,
                  width=12).pack(side=tk.LEFT)
    
    def create_status_bar(self, parent):
        """创建底部状态栏"""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 状态栏背景
        status_bg = ttk.Frame(status_frame, relief='sunken', borderwidth=1)
        status_bg.pack(fill=tk.X)
        
        # 左侧状态信息
        left_status = ttk.Frame(status_bg)
        left_status.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=2)
        
        self.status_var = tk.StringVar()
        self.status_var.set("🟢 就绪")
        self.status_label = ttk.Label(left_status, textvariable=self.status_var, 
                                    font=('微软雅黑', 9))
        self.status_label.pack(side=tk.LEFT)
        
        # 右侧时间和版本信息
        right_status = ttk.Frame(status_bg)
        right_status.pack(side=tk.RIGHT, padx=5, pady=2)
        
        # 实时时间
        self.time_var = tk.StringVar()
        self.time_label = ttk.Label(right_status, textvariable=self.time_var, 
                                  font=('微软雅黑', 8), foreground='#7f8c8d')
        self.time_label.pack(side=tk.RIGHT, padx=(10, 0))
        
        # 版本信息
        version_label = ttk.Label(right_status, text="v1.0.0", 
                                font=('微软雅黑', 8), foreground='#7f8c8d')
        version_label.pack(side=tk.RIGHT)
        
        # 启动时间更新
        self.update_time()
    
    def create_context_menu(self):
        """创建右键菜单"""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="🔐 切换到此账号", command=self.switch_account)
        self.context_menu.add_command(label="📝 查看详情", command=self.show_account_details)
        self.context_menu.add_command(label="💬 私信管理", command=self.show_message_window)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="✏️ 重命名", command=self.rename_account)
        self.context_menu.add_command(label="🔄 刷新状态", command=self.refresh_single_account)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🗑️ 删除账号", command=self.delete_account)
    
    # 新增的辅助方法
    def update_time(self):
        """更新时间显示"""
        import time
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        self.time_var.set(current_time)
        self.root.after(1000, self.update_time)
    
    def on_search(self, event=None):
        """搜索功能"""
        search_text = self.search_var.get().lower()
        # 实现搜索逻辑
        self.filter_accounts(search_text)
    
    def change_view_mode(self):
        """切换视图模式"""
        # 实现视图模式切换
        pass
    
    def sort_column(self, col):
        """排序列"""
        # 实现列排序功能
        pass
    
    def show_context_menu(self, event):
        """显示右键菜单"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()
    
    def on_account_select(self, event):
        """账号选择事件"""
        selection = self.tree.selection()
        if selection:
            self.update_current_account_info()
    
    def quick_login(self):
        """快速登录"""
        self.add_account()
    
    def show_logs(self):
        """显示日志"""
        show_message("日志", "日志查看功能开发中...", "info", self.root)
    
    def show_help(self):
        """显示帮助"""
        help_text = """🎬 B站多账号管理系统使用指南

📌 基本功能：
• 新增账号：点击"新增账号"按钮进行扫码登录
• 账号管理：重命名、删除、切换账号
• 私信管理：自动回复、消息管理

🎯 自动回复：
• 支持多种匹配模式：精确、包含、正则等
• 可设置优先级和回复延迟
• 实时统计回复数据

⚙️ 快捷操作：
• 双击账号查看详情
• 右键菜单快速操作
• 实时搜索和筛选

🆘 技术支持：
GitHub: https://github.com/OxenFxc
版本: v1.0.0"""
        
        show_message("帮助", help_text, "info", self.root)
    
    def refresh_single_account(self):
        """刷新单个账号状态"""
        selection = self.tree.selection()
        if selection:
            # 实现单个账号刷新逻辑
            self.refresh_accounts()
    
    def refresh_current_info(self):
        """刷新当前信息"""
        self.update_current_account_info()
    
    def copy_account_info(self):
        """复制账号信息到剪贴板"""
        info_text = self.current_info.get(1.0, tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(info_text)
        self.status_var.set("📋 账号信息已复制到剪贴板")
        self.root.after(3000, lambda: self.status_var.set("🟢 就绪"))
    
    def filter_accounts(self, search_text):
        """根据搜索文本过滤账号"""
        # 这里可以实现更复杂的过滤逻辑
        pass
    
    def refresh_accounts(self):
        """刷新账号列表"""
        self.status_var.set("🔄 正在刷新账号列表...")
        
        # 清空现有项目
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        try:
            # 获取账号列表
            accounts = self.account_manager.list_accounts()
            
            valid_count = 0
            invalid_count = 0
            
            for account in accounts:
                is_valid = account['is_valid']
                status_icon = "✅ 正常" if is_valid else "❌ 失效"
                login_time = format_time(account['login_time'], "%m-%d %H:%M")
                uid = str(account['uid'])  # 确保UID是字符串类型
                
                # 检查自动回复状态（这里需要实际实现检查逻辑）
                auto_reply_status = "🔴 未启用"  # 默认状态
                try:
                    # 这里可以检查该账号的自动回复状态
                    # auto_reply_enabled = self.check_auto_reply_status(uid)
                    # auto_reply_status = "🟢 运行中" if auto_reply_enabled else "🔴 未启用"
                    pass
                except:
                    pass
                
                # 插入到树形视图
                item_id = self.tree.insert('', tk.END, values=(
                    status_icon,
                    account['display_name'],
                    uid,
                    login_time,
                    auto_reply_status
                ))
                
                # 根据状态设置行颜色
                if is_valid:
                    valid_count += 1
                    if uid == str(self.account_manager.current_account):
                        # 当前账号使用特殊标记
                        self.tree.set(item_id, 'status', "⭐ 当前")
                        self.tree.selection_set(item_id)
                else:
                    invalid_count += 1
            
            # 更新统计信息
            self.update_stats_display(len(accounts), valid_count, invalid_count)
            
            self.status_var.set(f"✅ 已加载 {len(accounts)} 个账号")
            
            # 更新当前账号信息
            self.update_current_account_info()
            
        except Exception as e:
            show_message("错误", f"刷新账号列表失败: {str(e)}", "error", self.root)
            self.status_var.set("❌ 刷新失败")
    
    def update_stats_display(self, total, valid, invalid):
        """更新统计信息显示"""
        self.stats_total_label.config(text=f"📊 总账号: {total}")
        self.stats_active_label.config(text=f"✅ 有效账号: {valid}")
        self.stats_invalid_label.config(text=f"❌ 失效账号: {invalid}")
    
    def update_current_account_info(self):
        """更新当前账号信息显示"""
        self.current_info.config(state=tk.NORMAL)
        self.current_info.delete(1.0, tk.END)
        
        # 获取选中的账号信息
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            values = self.tree.item(item, 'values')
            if len(values) >= 3:
                uid = values[2]  # UID列
                account_info = self.account_manager.get_account_info(uid)
                if account_info:
                    self.display_account_details(account_info)
                    self.update_account_cards(account_info)
                    return
        
        # 如果没有选中账号，显示当前账号信息
        current_account = self.account_manager.get_current_account()
        
        if current_account:
            self.display_account_details(current_account)
            self.update_account_cards(current_account)
        else:
            self.current_info.insert(1.0, "📝 暂无账号信息\n\n点击'新增账号'开始使用")
            self.current_account_name.config(text="未选择") 
            self.current_account_status.config(text="状态: 未知")
            self.auto_reply_status.config(text="未启用")
            self.auto_reply_count.config(text="今日回复: 0")
        
        self.current_info.config(state=tk.DISABLED)
    
    def display_account_details(self, account_info):
        """显示账号详细信息"""
        user_info = account_info.get('user_info', {})
        display_name = account_info.get('display_name', '未知')
        
        info_text = f"""🎬 账号详细信息

📝 基本信息：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 显示名称: {display_name}
• 用户名: {user_info.get('uname', '未知')}
• 用户ID: {user_info.get('mid', '未知')}
• 等级：Lv{user_info.get('level_info', {}).get('current_level', 0)}
• 经验值：{user_info.get('level_info', {}).get('current_exp', 0)}

💰 资产信息：
• 硬币：{user_info.get('money', 0)}
• 节操值：{user_info.get('moral', 0)}

👑 会员信息："""
        
        if user_info.get('vipStatus'):
            vip_label = user_info.get('vip_label', {})
            info_text += f"\n• 会员类型：{vip_label.get('text', '大会员')}"
            
            vip_due = user_info.get('vipDueDate', 0)
            if vip_due > 0:
                due_date = format_time(vip_due / 1000, "%Y-%m-%d")
                info_text += f"\n• 到期时间：{due_date}"
        else:
            info_text += "\n• 会员状态：非会员"
        
        # 认证信息
        official = user_info.get('official', {})
        if official.get('type') != -1:
            info_text += f"\n\n🎖️ 认证信息：\n• {official.get('title', '已认证')}"
        
        info_text += f"\n\n⏰ 时间信息："
        info_text += f"\n• 登录时间：{format_time(account_info.get('login_time', 0))}"
        info_text += f"\n• 最后验证：{format_time(account_info.get('last_verify', 0))}"
        
        self.current_info.insert(1.0, info_text)
    
    def update_account_cards(self, account_info):
        """更新账号状态卡片"""
        display_name = account_info.get('display_name', '未知')
        is_valid = account_info.get('is_valid', False)
        
        self.current_account_name.config(text=display_name)
        
        if is_valid:
            self.current_account_status.config(text="状态: ✅ 正常", foreground='green')
        else:
            self.current_account_status.config(text="状态: ❌ 失效", foreground='red')
        
        # 这里可以添加自动回复状态检查
        # auto_reply_enabled = self.check_auto_reply_status(account_info.get('uid'))
        # if auto_reply_enabled:
        #     self.auto_reply_status.config(text="🟢 运行中", foreground='green')
        #     self.auto_reply_count.config(text="今日回复: X")
        # else:
        #     self.auto_reply_status.config(text="🔴 未启用", foreground='red')
        #     self.auto_reply_count.config(text="今日回复: 0")
    
    def add_account(self):
        """添加新账号"""
        login_window = LoginWindow(self.root, self.account_manager, self.config)
        login_window.show()
        
        # 登录完成后刷新列表
        self.root.after(1000, self.refresh_accounts)
    
    def delete_account(self):
        """删除选中的账号"""
        selection = self.tree.selection()
        if not selection:
            show_message("提示", "请先选择要删除的账号", "warning", self.root)
            return
        
        # 获取选中账号的UID
        item = selection[0]
        values = self.tree.item(item)['values']
        uid = str(values[2])  # 确保UID是字符串类型
        account_name = values[1]
        
        # 确认删除
        if confirm_dialog("确认删除", f"确定要删除账号 '{account_name}' 吗？\n此操作不可撤销！", self.root):
            success, message = self.account_manager.remove_account(uid)
            if success:
                show_message("成功", message, "info", self.root)
                self.refresh_accounts()
            else:
                show_message("错误", message, "error", self.root)
    
    def rename_account(self):
        """重命名选中的账号"""
        selection = self.tree.selection()
        if not selection:
            show_message("提示", "请先选择要重命名的账号", "warning", self.root)
            return
        
        # 获取选中账号的信息
        item = selection[0]
        values = self.tree.item(item)['values']
        uid = str(values[2])  # 确保UID是字符串类型
        current_name = values[1]
        
        # 输入新名称
        new_name = ask_string("重命名账号", f"请输入新的账号名称：", self.root, current_name)
        
        if new_name and new_name != current_name:
            success, message = self.account_manager.update_account_name(uid, new_name)
            if success:
                show_message("成功", message, "info", self.root)
                self.refresh_accounts()
            else:
                show_message("错误", message, "error", self.root)
    
    def switch_account(self):
        """切换到选中的账号"""
        selection = self.tree.selection()
        if not selection:
            show_message("提示", "请先选择要切换的账号", "warning", self.root)
            return
        
        # 获取选中账号的UID
        item = selection[0]
        values = self.tree.item(item)['values']
        uid = str(values[2])  # 确保UID是字符串类型
        
        self.status_var.set("正在切换账号...")
        
        try:
            success, message = self.account_manager.switch_account(uid)
            if success:
                show_message("成功", message, "info", self.root)
                self.refresh_accounts()
            else:
                show_message("错误", message, "error", self.root)
        except Exception as e:
            show_message("错误", f"切换账号失败: {str(e)}", "error", self.root)
        finally:
            self.status_var.set("就绪")
    
    def show_account_details(self):
        """显示账号详细信息"""
        selection = self.tree.selection()
        if not selection:
            show_message("提示", "请先选择要查看的账号", "warning", self.root)
            return
        
        # 获取选中账号的UID
        item = selection[0]
        values = self.tree.item(item)['values']
        uid = str(values[2])  # 确保UID是字符串类型
        
        account_window = AccountWindow(self.root, self.account_manager, uid)
        account_window.show()
    
    def show_message_window(self):
        """显示私信管理窗口"""
        selection = self.tree.selection()
        if not selection:
            show_message("提示", "请先选择要管理私信的账号", "warning", self.root)
            return
        
        # 获取选中账号的UID
        item = selection[0]
        values = self.tree.item(item)['values']
        uid = str(values[2])  # 确保UID是字符串类型
        
        # 检查账号是否有效
        account_info = self.account_manager.get_account_info(uid)
        if not account_info:
            show_message("错误", "账号信息不存在", "error", self.root)
            return
        
        # 验证账号登录状态
        from ..core.login import BilibiliLogin
        login_handler = BilibiliLogin()
        is_valid, _ = login_handler.verify_login(account_info.get('cookies', {}))
        
        if not is_valid:
            show_message("错误", "账号登录状态已失效，请重新登录", "error", self.root)
            return
        
        # 检查是否已有该账号的私信窗口
        if uid in self.message_windows:
            existing_window = self.message_windows[uid]
            # 检查窗口是否还存在且可见
            try:
                if existing_window.window.winfo_exists():
                    # 窗口存在，将其置于前台
                    existing_window.window.lift()
                    existing_window.window.focus()
                    show_message("提示", "该账号的私信管理窗口已打开", "info", self.root)
                    return
                else:
                    # 窗口已关闭，清理引用
                    del self.message_windows[uid]
            except:
                # 窗口对象无效，清理引用
                del self.message_windows[uid]
        
        # 创建新的私信管理窗口
        message_window = MessageWindow(self.root, self.account_manager, uid, 
                                     on_close_callback=lambda: self._on_message_window_close(uid))
        self.message_windows[uid] = message_window
        message_window.show()
    
    def _on_message_window_close(self, uid):
        """私信管理窗口关闭回调"""
        if uid in self.message_windows:
            del self.message_windows[uid]
            print(f"✅ 账号 {uid} 的私信管理窗口已关闭并清理")
    
    def show_settings(self):
        """显示设置窗口"""
        # 简单的设置对话框
        settings_window = tk.Toplevel(self.root)
        settings_window.title("设置")
        settings_window.geometry("400x300")
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        # 居中显示
        center_window(settings_window, 400, 300)
        
        ttk.Label(settings_window, text="设置功能开发中...", 
                 font=('微软雅黑', 12)).pack(pady=50)
        
        ttk.Button(settings_window, text="关闭", 
                  command=settings_window.destroy).pack(pady=20)
    
    def on_account_double_click(self, event):
        """账号列表双击事件"""
        self.switch_account()
    
    def on_closing(self):
        """窗口关闭事件"""
        if confirm_dialog("确认退出", "确定要退出程序吗？", self.root):
            self.root.destroy()
    
    def run(self):
        """运行主窗口"""
        self.root.mainloop() 