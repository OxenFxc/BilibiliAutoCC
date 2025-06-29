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
import os
from typing import Dict, Optional, Any
from datetime import datetime

from ..core.message_manager import MessageManager
from ..utils import (format_time, show_message, confirm_dialog, 
                    center_window, ask_string, run_in_thread)


class MessageWindow:
    def __init__(self, parent, account_manager, uid: str, on_close_callback=None):
        """
        初始化私信管理窗口
        
        Args:
            parent: 父窗口
            account_manager: 账号管理器
            uid: 账号UID
            on_close_callback: 窗口关闭回调函数
        """
        self.parent = parent
        self.account_manager = account_manager
        self.uid = uid
        self.window = None
        self.on_close_callback = on_close_callback
        
        # 获取账号信息
        self.account_info = account_manager.get_account_info(uid)
        if not self.account_info:
            show_message("错误", "账号信息不存在", "error", parent)
            return
        
        # 初始化私信管理器
        from ..core.login import BilibiliLogin
        login_handler = BilibiliLogin()
        self.message_manager = MessageManager(login_handler, uid)
        
        # 设置cookies并验证
        cookies = self.account_info.get('cookies', {})
        if cookies:
            self.message_manager.set_cookies(cookies)
            print(f"✅ 账号 {uid} cookies已设置，包含 {len(cookies)} 个cookie")
            
            # 检查关键cookies
            if 'DedeUserID' in cookies and 'bili_jct' in cookies:
                print(f"✅ 账号 {uid} 关键cookies齐全: DedeUserID={cookies.get('DedeUserID')}")
            else:
                print(f"⚠️ 账号 {uid} 缺少关键cookies: DedeUserID={cookies.get('DedeUserID')}, bili_jct={'存在' if cookies.get('bili_jct') else '缺失'}")
        else:
            print(f"❌ 账号 {uid} 未设置cookies")
        
        # 界面状态
        self.current_session = None
        self.sessions_data = []
        self.auto_refresh_enabled = True
        self.refresh_thread = None
        
        # 组件状态标记
        self._components_created = False
        
    def show(self):
        """显示私信管理窗口"""
        if self.window:
            self.window.lift()
            return
            
        self.window = tk.Toplevel(self.parent)
        self.window.title(f"💬 私信管理 - {self.account_info.get('display_name', self.uid)}")
        # 调整为更合适的尺寸
        self.window.geometry("1200x700")
        self.window.minsize(1000, 600)  # 设置最小尺寸
        self.window.maxsize(1600, 1000)  # 设置最大尺寸
        self.window.transient(self.parent)
        
        # 居中显示
        center_window(self.window, 1200, 700)
        
        # 初始化界面
        self.init_ui()
        
        # 标记组件已创建
        self._components_created = True
        
        # 设置消息管理器的GUI日志回调
        if hasattr(self, 'message_manager') and self.message_manager:
            self.message_manager.set_gui_log_callback(self.add_log)
        
        # 绑定关闭事件
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 加载自动回复规则
        self.load_auto_reply_rules()
        
        # 启动数据刷新
        self.start_refresh_thread()
        
        # 初始加载数据
        self.refresh_sessions()
        
        # 消息列表更新定时器
        self.refresh_messages_timer()
        
        # 添加初始日志
        self.add_log("💬 私信管理系统已启动", "success")
        self.add_log(f"📱 当前账号: {self.account_info.get('display_name', self.uid)}", "info")
    
    def init_ui(self):
        """初始化用户界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.window, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 配置网格权重 - 调整列宽比例
        main_frame.columnconfigure(0, weight=1, minsize=280)   # 会话列表
        main_frame.columnconfigure(1, weight=3, minsize=400)   # 消息区域  
        main_frame.columnconfigure(2, weight=1, minsize=320)   # 自动回复面板
        main_frame.rowconfigure(0, weight=1)
        
        # 左侧会话列表
        self.create_sessions_panel(main_frame)
        
        # 中间消息显示区域
        self.create_messages_panel(main_frame)
        
        # 右侧自动回复设置
        self.create_auto_reply_panel(main_frame)
        
    def create_sessions_panel(self, parent):
        """创建会话列表面板"""
        # 会话列表框架
        sessions_frame = ttk.LabelFrame(parent, text="私信会话", padding="5")
        sessions_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        sessions_frame.columnconfigure(0, weight=1)
        sessions_frame.rowconfigure(1, weight=1)
        
        # 工具栏
        toolbar_frame = ttk.Frame(sessions_frame)
        toolbar_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Button(toolbar_frame, text="刷新", command=self.refresh_sessions, 
                  width=8).pack(side=tk.LEFT, padx=(0, 5))
        
        # 未读消息统计标签
        self.unread_label = ttk.Label(toolbar_frame, text="未读: 0", foreground="red")
        self.unread_label.pack(side=tk.RIGHT)
        
        # 会话列表
        columns = ('type', 'name', 'unread', 'last_time')
        self.sessions_tree = ttk.Treeview(sessions_frame, columns=columns, show='headings', height=15)
        
        # 设置列标题
        self.sessions_tree.heading('type', text='类型')
        self.sessions_tree.heading('name', text='会话名称')
        self.sessions_tree.heading('unread', text='未读')
        self.sessions_tree.heading('last_time', text='最后消息')
        
        # 设置列宽
        self.sessions_tree.column('type', width=60, anchor='center')
        self.sessions_tree.column('name', width=150)
        self.sessions_tree.column('unread', width=40, anchor='center')
        self.sessions_tree.column('last_time', width=100)
        
        # 添加滚动条
        sessions_scrollbar = ttk.Scrollbar(sessions_frame, orient=tk.VERTICAL, 
                                         command=self.sessions_tree.yview)
        self.sessions_tree.configure(yscrollcommand=sessions_scrollbar.set)
        
        # 布局
        self.sessions_tree.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        sessions_scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))
        
        # 绑定选择事件
        self.sessions_tree.bind('<Button-1>', self.on_session_select)
    
    def create_messages_panel(self, parent):
        """创建消息显示面板"""
        # 消息显示框架
        messages_frame = ttk.LabelFrame(parent, text="💬 消息对话", padding="8")
        messages_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        messages_frame.columnconfigure(0, weight=1)
        messages_frame.rowconfigure(1, weight=3)  # 消息区域权重3
        messages_frame.rowconfigure(3, weight=2)  # 日志区域权重2
        
        # 消息工具栏
        msg_toolbar = ttk.Frame(messages_frame)
        msg_toolbar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        
        # 当前会话信息
        self.current_session_label = ttk.Label(msg_toolbar, text="请选择会话", 
                                             font=('微软雅黑', 9, 'bold'), foreground='#2c3e50')
        self.current_session_label.pack(side=tk.LEFT)
        
        # 右侧按钮
        ttk.Button(msg_toolbar, text="🔧 强制检测", command=self.force_check_messages, 
                  width=10).pack(side=tk.RIGHT, padx=(5, 0))
        
        ttk.Button(msg_toolbar, text="🔄 刷新", command=self.refresh_current_messages, 
                  width=8).pack(side=tk.RIGHT, padx=(5, 0))
        
        ttk.Button(msg_toolbar, text="🔧 API调试", command=self.debug_message_api, 
                  width=10).pack(side=tk.RIGHT, padx=(5, 0))
        
        # 消息显示区域
        self.messages_text = scrolledtext.ScrolledText(
            messages_frame, 
            wrap=tk.WORD, 
            font=('微软雅黑', 10),
            bg='#f8f9fa',
            fg='#2c3e50',
            state=tk.DISABLED,
            relief=tk.FLAT,
            borderwidth=1
        )
        self.messages_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 8))
        
        # 配置消息文本框的标签样式
        self.messages_text.tag_configure("me", justify='right', foreground='#ffffff', 
                                        background='#007bff', relief='raised', borderwidth=1)
        self.messages_text.tag_configure("other", justify='left', foreground='#333333', 
                                        background='#e9ecef', relief='raised', borderwidth=1)
        self.messages_text.tag_configure("time", justify='center', foreground='#6c757d', 
                                        font=('微软雅黑', 8))
        self.messages_text.tag_configure("system", justify='center', foreground='#28a745', 
                                        font=('微软雅黑', 9), background='#d4edda')
        
        # 分隔线
        separator = ttk.Separator(messages_frame, orient='horizontal')
        separator.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # 日志显示区域
        log_frame = ttk.LabelFrame(messages_frame, text="📋 系统日志", padding="5")
        log_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(1, weight=1)
        
        # 日志工具栏
        log_toolbar = ttk.Frame(log_frame)
        log_toolbar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        # 日志状态标签
        self.log_status_label = ttk.Label(log_toolbar, text="💤 等待扫描...", 
                                        font=('微软雅黑', 8), foreground='#7f8c8d')
        self.log_status_label.pack(side=tk.LEFT)
        
        # 日志控制按钮
        ttk.Button(log_toolbar, text="清空日志", command=self.clear_logs, 
                  width=8).pack(side=tk.RIGHT, padx=(5, 0))
        
        # 自动滚动开关
        self.auto_scroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(log_toolbar, text="自动滚动", variable=self.auto_scroll_var).pack(side=tk.RIGHT, padx=(5, 0))
        
        # 日志文本区域
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=('Consolas', 9),
            bg='#2c3e50',
            fg='#ecf0f1',
            state=tk.DISABLED,
            relief=tk.FLAT,
            borderwidth=1,
            height=8
        )
        self.log_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置日志文本颜色标签
        self.log_text.tag_configure("info", foreground="#3498db")      # 蓝色 - 信息
        self.log_text.tag_configure("success", foreground="#2ecc71")   # 绿色 - 成功
        self.log_text.tag_configure("warning", foreground="#f39c12")   # 橙色 - 警告
        self.log_text.tag_configure("error", foreground="#e74c3c")     # 红色 - 错误
        self.log_text.tag_configure("scan", foreground="#9b59b6")      # 紫色 - 扫描
        self.log_text.tag_configure("message", foreground="#1abc9c")   # 青色 - 消息
        
        # 消息发送区域
        send_frame = ttk.Frame(messages_frame)
        send_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(8, 0))
        send_frame.columnconfigure(0, weight=1)
        
        # 消息输入框
        self.message_entry = tk.Text(send_frame, height=3, font=('微软雅黑', 10),
                                   bg='white', fg='#2c3e50', relief=tk.FLAT, borderwidth=1)
        self.message_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 8))
        
        # 发送按钮
        send_btn = ttk.Button(send_frame, text="发送\n(Ctrl+Enter)", 
                            command=self.send_message, width=12)
        send_btn.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # 绑定快捷键
        self.message_entry.bind('<Control-Return>', lambda e: self.send_message())
        
        # 状态显示
        self.status_label = ttk.Label(send_frame, text="请选择会话后开始对话", 
                                    font=('微软雅黑', 8), foreground='#7f8c8d')
        self.status_label.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
    
    def clear_logs(self):
        """清空日志"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def add_log(self, message, log_type="info"):
        """添加日志"""
        if not hasattr(self, 'log_text'):
            return
            
        # 在主线程中安全更新
        def _update():
            try:
                self.log_text.config(state=tk.NORMAL)
                
                # 添加时间戳
                timestamp = time.strftime("%H:%M:%S")
                log_line = f"[{timestamp}] {message}\n"
                
                # 插入日志
                self.log_text.insert(tk.END, log_line, log_type)
                
                # 限制日志行数（保留最新1000行）
                lines = self.log_text.get(1.0, tk.END).split('\n')
                if len(lines) > 1000:
                    self.log_text.delete(1.0, f"{len(lines)-1000}.0")
                
                # 自动滚动到底部
                if self.auto_scroll_var.get():
                    self.log_text.see(tk.END)
                
                self.log_text.config(state=tk.DISABLED)
            except:
                pass  # 忽略在窗口关闭时的更新错误
        
        try:
            if self.window and self.window.winfo_exists():
                self.window.after(0, _update)
        except:
            pass
    
    def _safe_update_label(self, label, text):
        """安全地更新标签文本"""
        try:
            if self._components_created and label and hasattr(label, 'config'):
                label.config(text=text)
        except (tk.TclError, AttributeError):
            pass
    
    def _safe_update_status(self, text, color):
        """安全地更新状态显示"""
        try:
            if self._components_created and hasattr(self, 'status_indicator') and hasattr(self, 'status_label'):
                self.status_indicator.config(foreground=color)
                self.status_label.config(text=text, foreground=color)
        except (tk.TclError, AttributeError):
            pass
    
    def refresh_current_messages(self):
        """刷新当前消息"""
        if self.current_session:
            self.load_session_messages()
    
    def clear_messages(self):
        """清空消息显示"""
        if confirm_dialog("清空消息", "确定要清空当前消息显示吗？", self.window):
            self.messages_text.config(state=tk.NORMAL)
            self.messages_text.delete(1.0, tk.END)
            self.messages_text.config(state=tk.DISABLED)
    
    def clear_input(self):
        """清空输入框"""
        self.message_entry.delete(1.0, tk.END)
    
    def force_check_messages(self):
        """强制检测所有会话的新消息"""
        @run_in_thread
        def _force_check():
            try:
                current_time = time.time()
                self._safe_update_status("🔍 强制检测中...", "blue")
                
                # 运行实时API测试
                print(f"\n🧪 === 实时API测试开始 ===")
                self.message_manager.test_real_time_api()
                print(f"🧪 === 实时API测试结束 ===\n")
                
                # 获取会话列表
                success, sessions = self.message_manager.get_sessions()
                if not success:
                    self._safe_update_status(f"❌ 获取会话列表失败: {sessions}", "red")
                    return
                
                print(f"\n🔧 强制检测模式 - 检查{len(sessions)}个会话")
                print(f"当前时间戳: {current_time}")
                
                # 选择一个有最近消息的会话进行详细调试
                target_session = None
                for session in sessions[:5]:  # 检查前5个会话
                    last_msg = session.get('last_msg')
                    if last_msg and last_msg.get('timestamp', 0) > 0:
                        target_session = session
                        break
                
                if target_session:
                    session_name = self.message_manager.format_session_name(target_session)
                    talker_id = target_session.get('talker_id')
                    session_type = target_session.get('session_type', 1)
                    
                    print(f"\n🎯 选择会话【{session_name}】进行详细调试")
                    print(f"会话ID: {talker_id}, 类型: {session_type}")
                    
                    # 调用调试方法获取完整信息
                    self.message_manager.debug_get_messages(talker_id, session_type, size=10)
                    
                    # 同时调用正常的获取方法进行对比
                    print(f"\n📊 对比：使用正常方法获取消息")
                    normal_success, normal_data = self.message_manager.get_session_messages(talker_id, session_type, size=10)
                    print(f"正常方法结果: 成功={normal_success}")
                    if normal_success:
                        messages = normal_data.get('messages', [])
                        print(f"正常方法获取到 {len(messages)} 条消息")
                        if messages:
                            print(f"最新消息发送者: {messages[0].get('sender_uid')}")
                            print(f"最新消息时间: {messages[0].get('timestamp')}")
                            content = messages[0].get('content', '')
                            try:
                                import json
                                content_obj = json.loads(content)
                                text = content_obj.get('content', content)
                            except:
                                text = content
                            print(f"最新消息内容: {text[:100]}")
                    else:
                        print(f"正常方法失败: {normal_data}")
                else:
                    print(f"未找到合适的会话进行调试")
                
                result_msg = f"✅ 强制检测完成，详细信息请查看控制台"
                print(f"\n{result_msg}")
                self._safe_update_status(result_msg, "blue")
                
            except Exception as e:
                error_msg = f"❌ 强制检测失败: {str(e)}"
                print(error_msg)
                self._safe_update_status(error_msg, "red")
        
        _force_check()
    
    def create_auto_reply_panel(self, parent):
        """创建自动回复设置面板"""
        # 自动回复框架
        auto_reply_frame = ttk.LabelFrame(parent, text="🤖 自动回复系统", padding="10")
        auto_reply_frame.grid(row=0, column=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        auto_reply_frame.columnconfigure(0, weight=1)
        auto_reply_frame.rowconfigure(3, weight=1)
        
        # 控制区域
        control_frame = ttk.LabelFrame(auto_reply_frame, text="🎛️ 系统控制", padding="10")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        control_frame.columnconfigure(1, weight=1)
        
        # 启用开关
        self.auto_reply_var = tk.BooleanVar()
        self.auto_reply_check = ttk.Checkbutton(
            control_frame, 
            text="🚀 启用自动回复", 
            variable=self.auto_reply_var,
            command=self.toggle_auto_reply
        )
        self.auto_reply_check.grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        
        # 状态指示器
        status_frame = ttk.Frame(control_frame)
        status_frame.grid(row=0, column=1, sticky=tk.E)
        
        self.status_indicator = tk.Label(status_frame, text="●", font=('Arial', 12), foreground="red")
        self.status_indicator.pack(side=tk.LEFT, padx=(0, 5))
        
        self.status_label = ttk.Label(status_frame, text="已停止", font=('微软雅黑', 9, 'bold'), foreground="red")
        self.status_label.pack(side=tk.LEFT)
        
        # 配置区域
        config_frame = ttk.LabelFrame(auto_reply_frame, text="⚙️ 回复配置", padding="10")
        config_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        config_frame.columnconfigure(1, weight=1)
        
        # 回复延迟设置
        ttk.Label(config_frame, text="⏰ 回复延迟(秒):", font=('微软雅黑', 9)).grid(row=0, column=0, sticky=tk.W, pady=5)
        delay_frame = ttk.Frame(config_frame)
        delay_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)
        
        self.delay_min_var = tk.IntVar(value=1)
        self.delay_max_var = tk.IntVar(value=3)
        
        ttk.Spinbox(delay_frame, from_=1, to=60, width=8, textvariable=self.delay_min_var).pack(side=tk.LEFT)
        ttk.Label(delay_frame, text=" 至 ", font=('微软雅黑', 8)).pack(side=tk.LEFT)
        ttk.Spinbox(delay_frame, from_=1, to=60, width=8, textvariable=self.delay_max_var).pack(side=tk.LEFT)
        ttk.Label(delay_frame, text="秒", font=('微软雅黑', 8), foreground='#666666').pack(side=tk.LEFT, padx=(5, 0))
        
        # 每日限制
        ttk.Label(config_frame, text="📊 每日限制:", font=('微软雅黑', 9)).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.daily_limit_var = tk.IntVar(value=0)
        limit_frame = ttk.Frame(config_frame)
        limit_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Spinbox(limit_frame, from_=0, to=9999, width=12, textvariable=self.daily_limit_var).pack(side=tk.LEFT)
        ttk.Label(limit_frame, text="(0=无限制)", font=('微软雅黑', 8), foreground='#666666').pack(side=tk.LEFT, padx=(5, 0))
        
        # 扫描间隔设置
        ttk.Label(config_frame, text="🔍 扫描间隔(秒):", font=('微软雅黑', 9)).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.scan_interval_var = tk.IntVar(value=8)
        scan_frame = ttk.Frame(config_frame)
        scan_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Spinbox(scan_frame, from_=1, to=300, width=12, textvariable=self.scan_interval_var).pack(side=tk.LEFT)
        ttk.Label(scan_frame, text="(1-300秒)", font=('微软雅黑', 8), foreground='#666666').pack(side=tk.LEFT, padx=(5, 0))
        
        # 按钮区域
        button_frame = ttk.Frame(config_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(10, 0))
        
        ttk.Button(button_frame, text="💾 保存配置", command=self.save_config, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="🔄 重置", command=self.reset_config, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="🧪 测试连接", command=self.test_auto_reply_connection, width=12).pack(side=tk.LEFT)
        
        # 统计信息框架
        stats_frame = ttk.LabelFrame(auto_reply_frame, text="📈 回复统计", padding="10")
        stats_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        stats_frame.columnconfigure(1, weight=1)
        
        # 统计信息网格布局
        ttk.Label(stats_frame, text="📊 总计回复:", font=('微软雅黑', 8)).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.total_replies_label = ttk.Label(stats_frame, text="0", font=('微软雅黑', 8, 'bold'), foreground='#2c3e50')
        self.total_replies_label.grid(row=0, column=1, sticky=tk.W)
        
        ttk.Label(stats_frame, text="📅 今日回复:", font=('微软雅黑', 8)).grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.today_replies_label = ttk.Label(stats_frame, text="0", font=('微软雅黑', 8, 'bold'), foreground='#27ae60')
        self.today_replies_label.grid(row=1, column=1, sticky=tk.W)
        
        ttk.Label(stats_frame, text="⚡ 成功率:", font=('微软雅黑', 8)).grid(row=0, column=2, sticky=tk.W, padx=(20, 10))
        self.success_rate_label = ttk.Label(stats_frame, text="100%", font=('微软雅黑', 8, 'bold'), foreground='#3498db')
        self.success_rate_label.grid(row=0, column=3, sticky=tk.W)
        
        ttk.Label(stats_frame, text="🕒 上次回复:", font=('微软雅黑', 8)).grid(row=1, column=2, sticky=tk.W, padx=(20, 10))
        self.last_reply_label = ttk.Label(stats_frame, text="暂无", font=('微软雅黑', 8, 'bold'), foreground='#7f8c8d')
        self.last_reply_label.grid(row=1, column=3, sticky=tk.W)
        
        # 规则管理区域
        rules_frame = ttk.LabelFrame(auto_reply_frame, text="📝 回复规则管理", padding="10")
        rules_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        rules_frame.columnconfigure(0, weight=1)
        rules_frame.rowconfigure(2, weight=1)
        
        # 规则工具栏
        rules_toolbar = ttk.Frame(rules_frame)
        rules_toolbar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 左侧按钮组
        left_buttons = ttk.Frame(rules_toolbar)
        left_buttons.pack(side=tk.LEFT)
        
        ttk.Button(left_buttons, text="➕ 添加规则", command=self.add_auto_reply_rule, 
                  width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(left_buttons, text="✏️ 编辑", command=self.edit_auto_reply_rule, 
                  width=10).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(left_buttons, text="🗑️ 删除", command=self.delete_auto_reply_rule, 
                  width=10).pack(side=tk.LEFT, padx=(0, 5))
        
        # 右侧功能按钮
        right_buttons = ttk.Frame(rules_toolbar)
        right_buttons.pack(side=tk.RIGHT)
        
        ttk.Button(right_buttons, text="📋 导入", command=self.import_rules, 
                  width=10).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(right_buttons, text="📤 导出", command=self.export_rules, 
                  width=10).pack(side=tk.LEFT)
        
        # 规则信息栏
        rules_info_frame = ttk.Frame(rules_frame)
        rules_info_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        self.rules_count_label = ttk.Label(rules_info_frame, text="规则总数: 0", 
                                         font=('微软雅黑', 8), foreground='#7f8c8d')
        self.rules_count_label.pack(side=tk.LEFT)
        
        self.active_rules_label = ttk.Label(rules_info_frame, text="启用: 0", 
                                          font=('微软雅黑', 8), foreground='#27ae60')
        self.active_rules_label.pack(side=tk.LEFT, padx=(20, 0))
        
        self.disabled_rules_label = ttk.Label(rules_info_frame, text="禁用: 0", 
                                            font=('微软雅黑', 8), foreground='#e74c3c')
        self.disabled_rules_label.pack(side=tk.LEFT, padx=(20, 0))
        
        # 规则列表
        list_frame = ttk.Frame(rules_frame)
        list_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        columns = ('status', 'keyword', 'reply', 'match_type', 'priority', 'description')
        self.rules_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)
        
        # 设置列标题和样式
        headers = {
            'status': ('状态', 60, 'center'),
            'keyword': ('关键词', 100, 'w'),
            'reply': ('回复内容', 150, 'w'),
            'match_type': ('匹配方式', 80, 'center'),
            'priority': ('优先级', 60, 'center'),
            'description': ('描述', 120, 'w')
        }
        
        for col, (text, width, anchor) in headers.items():
            self.rules_tree.heading(col, text=text, command=lambda c=col: self.sort_rules_column(c))
            self.rules_tree.column(col, width=width, anchor=anchor, minwidth=40)
        
        # 添加规则列表滚动条
        rules_v_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.rules_tree.yview)
        rules_h_scrollbar = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.rules_tree.xview)
        self.rules_tree.configure(yscrollcommand=rules_v_scrollbar.set, xscrollcommand=rules_h_scrollbar.set)
        
        # 布局规则列表
        self.rules_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        rules_v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        rules_h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # 创建右键菜单
        self.create_rules_context_menu()
        
        # 绑定事件
        self.rules_tree.bind('<Button-3>', self.show_rules_context_menu)
        self.rules_tree.bind('<Double-1>', lambda e: self.edit_auto_reply_rule())
        self.rules_tree.bind('<ButtonRelease-1>', self.on_rule_select)
        
        # 定期更新统计
        self.update_stats()
    
    def create_rules_context_menu(self):
        """创建规则右键菜单"""
        self.rules_menu = tk.Menu(self.window, tearoff=0)
        self.rules_menu.add_command(label="编辑规则", command=self.edit_auto_reply_rule)
        self.rules_menu.add_command(label="切换状态", command=self.toggle_rule_status)
        self.rules_menu.add_separator()
        self.rules_menu.add_command(label="删除规则", command=self.delete_auto_reply_rule)
    
    def save_config(self):
        """保存配置"""
        try:
            self.message_manager.reply_delay_min = self.delay_min_var.get()
            self.message_manager.reply_delay_max = self.delay_max_var.get()
            self.message_manager.daily_limit = self.daily_limit_var.get()
            self.message_manager.scan_interval = self.scan_interval_var.get()
            self.message_manager.save_account_config()
            show_message("成功", "配置已保存", "info", self.window)
        except Exception as e:
            show_message("错误", f"保存配置失败: {str(e)}", "error", self.window)
    
    def update_stats(self):
        """更新统计信息"""
        try:
            stats = self.message_manager.get_reply_stats()
            if stats:
                total = stats.get('total_replies', 0)
                today = stats.get('today_replies', 0)
                self._safe_update_label(self.total_replies_label, f"{total}")
                self._safe_update_label(self.today_replies_label, f"{today}")
                self._safe_update_label(self.success_rate_label, f"{stats.get('success_rate', '100%')}")
                self._safe_update_label(self.last_reply_label, f"{stats.get('last_reply', '暂无')}")
            else:
                self._safe_update_label(self.total_replies_label, "0")
                self._safe_update_label(self.today_replies_label, "0")
                self._safe_update_label(self.success_rate_label, "100%")
                self._safe_update_label(self.last_reply_label, "暂无")
        except Exception as e:
            print(f"更新统计失败: {str(e)}")
        
        # 每30秒更新一次统计
        if self.window:
            try:
                self.window.after(30000, self.update_stats)
            except (tk.TclError, AttributeError):
                pass
    
    def refresh_sessions(self):
        """刷新会话列表"""
        @run_in_thread
        def _refresh():
            try:
                # 检查窗口是否存在
                if not self.window:
                    return
                
                # 获取未读数
                success, unread_data = self.message_manager.get_unread_count()
                if success and self.window:
                    total_unread = unread_data.get('unfollow_unread', 0) + unread_data.get('follow_unread', 0)
                    try:
                        self.window.after(0, lambda: self._safe_update_label(self.unread_label, f"未读: {total_unread}"))
                    except (tk.TclError, AttributeError):
                        return  # 窗口已关闭
                
                # 获取会话列表
                success, sessions = self.message_manager.get_sessions()
                if success and self.window:
                    self.sessions_data = sessions
                    try:
                        self.window.after(0, self.update_sessions_tree)
                    except tk.TclError:
                        return  # 窗口已关闭
                # 如果失败，不显示错误消息，避免频繁弹窗
                    
            except Exception as e:
                print(f"刷新会话失败: {str(e)}")
    
    def update_sessions_tree(self):
        """更新会话列表显示"""
        # 清空现有项目
        for item in self.sessions_tree.get_children():
            self.sessions_tree.delete(item)
        
        for session in self.sessions_data:
            session_type = "用户"
            if session.get('session_type') == 2:
                session_type = "粉丝团"
            elif session.get('system_msg_type', 0) > 0:
                session_type = "系统"
            
            name = self.message_manager.format_session_name(session)
            unread = session.get('unread_count', 0)
            
            # 格式化最后消息时间
            last_msg_time = session.get('last_msg', {}).get('timestamp', 0)
            if last_msg_time:
                last_time = format_time(last_msg_time)
            else:
                last_time = ""
            
            # 插入到树形控件
            item = self.sessions_tree.insert('', tk.END, values=(session_type, name, unread, last_time))
            
            # 如果有未读消息，高亮显示
            if unread > 0:
                self.sessions_tree.set(item, 'unread', f"{unread} 🔴")
    
    def on_session_select(self, event):
        """会话选择事件"""
        selection = self.sessions_tree.selection()
        if selection:
            index = self.sessions_tree.index(selection[0])
            if 0 <= index < len(self.sessions_data):
                self.current_session = self.sessions_data[index]
                
                # 调试：打印会话信息
                print(f"🔍 选中会话: {self.current_session}")
                
                # 更新当前会话显示
                session_name = self.message_manager.format_session_name(self.current_session)
                self._safe_update_label(self.current_session_label, f"💬 当前会话: {session_name}")
                
                self.load_session_messages()
    
    def load_session_messages(self):
        """加载会话消息"""
        if not self.current_session:
            return
        
        @run_in_thread
        def _load():
            try:
                # 检查窗口是否存在
                if not self.window:
                    return
                
                talker_id = self.current_session['talker_id']
                session_type = self.current_session['session_type']
                
                success, msg_data = self.message_manager.get_session_messages(talker_id, session_type, size=50)
                if success and self.window:
                    messages = msg_data.get('messages', [])
                    # 只在消息有变化时才更新显示
                    current_msg_count = len(getattr(self, '_last_messages', []))
                    if len(messages) != current_msg_count:
                        self._last_messages = messages
                        try:
                            self.window.after(0, lambda: self.display_messages(messages))
                        except tk.TclError:
                            return  # 窗口已关闭
                # 如果失败，不显示错误消息
                    
            except Exception as e:
                print(f"加载消息失败: {str(e)}")
    
    def display_messages(self, messages):
        """显示消息"""
        try:
            self.messages_text.config(state=tk.NORMAL)
            self.messages_text.delete(1.0, tk.END)
            
            if not messages:
                self.messages_text.insert(tk.END, "💭 暂无消息记录\n\n选择一个会话开始聊天吧~", "system")
                self.messages_text.config(state=tk.DISABLED)
                return
            
            # 按时间分组消息（同一天的消息归为一组）
            current_date = None
            
            for i, msg in enumerate(reversed(messages)):  # 反转以显示最新消息在底部
                sender_uid = msg.get('sender_uid')
                msg_type = msg.get('msg_type', 1)
                content = msg.get('content', '')
                timestamp = msg.get('timestamp', 0)
                
                # 解析消息内容
                parsed_content = self.message_manager.parse_message_content(content, msg_type)
                
                # 格式化时间
                if timestamp:
                    from datetime import datetime
                    dt = datetime.fromtimestamp(timestamp)
                    msg_date = dt.strftime("%Y-%m-%d")
                    time_str = dt.strftime("%H:%M")
                    
                    # 如果是新的一天，插入日期分隔符
                    if current_date != msg_date:
                        current_date = msg_date
                        if i > 0:  # 不是第一条消息才插入分隔符
                            self.messages_text.insert(tk.END, "\n")
                        
                        # 插入日期分隔符
                        today = datetime.now().strftime("%Y-%m-%d")
                        if msg_date == today:
                            date_text = f"————————— 今天 —————————\n\n"
                        else:
                            date_text = f"————————— {msg_date} —————————\n\n"
                        self.messages_text.insert(tk.END, date_text, "time")
                else:
                    time_str = "未知"
                
                # 判断是否是自己发送的消息
                is_self = str(sender_uid) == str(self.uid)
                
                if is_self:
                    # 自己的消息靠右显示
                    self.messages_text.insert(tk.END, f"{'':>50}🕐 {time_str}\n", "time")
                    self.messages_text.insert(tk.END, f"{'':>30}我: {parsed_content}\n", "me")
                    self.messages_text.insert(tk.END, "\n")
                else:
                    # 对方的消息靠左显示
                    sender_name = self.get_sender_name(sender_uid)
                    self.messages_text.insert(tk.END, f"🕐 {time_str}\n", "time")
                    self.messages_text.insert(tk.END, f"{sender_name}: {parsed_content}\n", "other")
                    self.messages_text.insert(tk.END, "\n")
            
            self.messages_text.config(state=tk.DISABLED)
            self.messages_text.see(tk.END)
            
        except Exception as e:
            print(f"显示消息失败: {str(e)}")
    
    def get_sender_name(self, sender_uid):
        """获取发送者名称"""
        # 如果有会话信息，尝试获取用户名
        if self.current_session:
            session_name = self.message_manager.format_session_name(self.current_session)
            if session_name and session_name != "未知用户":
                return f"👤 {session_name}"
        
        return f"👤 用户{sender_uid}"
    
    def send_message(self):
        """发送消息"""
        if not self.current_session:
            show_message("提示", "请先选择一个会话", "warning", self.window)
            return
        
        content = self.message_entry.get(1.0, tk.END).strip()
        if not content:
            show_message("提示", "请输入消息内容", "warning", self.window)
            return
        
        @run_in_thread
        def _send():
            try:
                talker_id = self.current_session['talker_id']
                session_type = self.current_session['session_type']
                
                print(f"📤 正在发送消息到用户 {talker_id}: {content[:50]}{'...' if len(content) > 50 else ''}")
                
                # 检查窗口是否存在
                if not self.window:
                    return
                
                # 检查消息管理器是否正确初始化
                if not self.message_manager:
                    try:
                        self.window.after(0, lambda: show_message("错误", "消息管理器未初始化", "error", self.window))
                    except tk.TclError:
                        pass
                    return
                
                # 检查cookies
                cookies = dict(self.message_manager.session.cookies)
                if not cookies.get('DedeUserID') or not cookies.get('bili_jct'):
                    try:
                        self.window.after(0, lambda: show_message("错误", "账号登录状态无效，请重新登录", "error", self.window))
                    except tk.TclError:
                        pass
                    return
                
                # 发送消息：receiver_id=talker_id, content=content, receiver_type=1(用户), msg_type=1(文本)
                success, result = self.message_manager.send_message(talker_id, content, 1, 1)
                if success:
                    print(f"✅ 消息发送成功")
                    if self.window:
                        try:
                            self.window.after(0, lambda: self.message_entry.delete(1.0, tk.END))
                            self.window.after(0, lambda: show_message("成功", "消息发送成功", "info", self.window))
                            # 重新加载消息
                            self.window.after(1000, self.load_session_messages)
                        except tk.TclError:
                            pass
                else:
                    print(f"❌ 消息发送失败: {result}")
                    if self.window:
                        try:
                            self.window.after(0, lambda: show_message("错误", f"发送失败: {result}", "error", self.window))
                        except tk.TclError:
                            pass
                    
            except Exception as e:
                print(f"❌ 发送消息异常: {str(e)}")
                if self.window:
                    try:
                        self.window.after(0, lambda: show_message("错误", f"发送消息失败: {str(e)}", "error", self.window))
                    except tk.TclError:
                        pass
    
    def toggle_auto_reply(self):
        """切换自动回复状态"""
        def _toggle():
            try:
                # 检查窗口是否存在
                if not self.window:
                    return
                
                # 检查消息管理器
                if not self.message_manager:
                    try:
                        self.window.after(0, lambda: show_message("错误", "消息管理器未初始化", "error", self.window))
                        self.window.after(0, lambda: self.auto_reply_var.set(False))
                    except tk.TclError:
                        pass
                    return
                
                # 检查cookies
                cookies = dict(self.message_manager.session.cookies)
                if not cookies.get('DedeUserID') or not cookies.get('bili_jct'):
                    try:
                        self.window.after(0, lambda: show_message("错误", "账号登录状态无效，请重新登录", "error", self.window))
                        self.window.after(0, lambda: self.auto_reply_var.set(False))
                    except tk.TclError:
                        pass
                    return
                
                if self.auto_reply_var.get():
                    print(f"🚀 账号 {self.uid} 正在启动自动回复...")
                    if self.window:
                        try:
                            self.window.after(0, lambda: self._safe_update_status("启动中...", "orange"))
                        except tk.TclError:
                            pass
                    self.message_manager.start_auto_reply_listener()
                    if self.window:
                        try:
                            self.window.after(0, lambda: self._safe_update_status("运行中", "green"))
                        except tk.TclError:
                            pass
                    print(f"✅ 账号 {self.uid} 自动回复已启动")
                else:
                    print(f"🔴 账号 {self.uid} 正在停止自动回复...")
                    if self.window:
                        try:
                            self.window.after(0, lambda: self._safe_update_status("停止中...", "orange"))
                        except tk.TclError:
                            pass
                    self.message_manager.stop_auto_reply_listener()
                    if self.window:
                        try:
                            self.window.after(0, lambda: self._safe_update_status("已停止", "red"))
                        except tk.TclError:
                            pass
                    print(f"🔴 账号 {self.uid} 自动回复已停止")
            except Exception as e:
                print(f"❌ 账号 {self.uid} 切换自动回复状态失败: {str(e)}")
                if self.window:
                    try:
                        self.window.after(0, lambda: show_message("错误", f"切换自动回复状态失败: {str(e)}", "error", self.window))
                        # 恢复开关状态
                        self.window.after(0, lambda: self.auto_reply_var.set(self.message_manager.auto_reply_enabled if self.message_manager else False))
                    except tk.TclError:
                        pass
        
        # 启动线程
        import threading
        threading.Thread(target=_toggle, daemon=True).start()
    
    def update_status_display(self, text, color):
        """更新状态显示"""
        self._safe_update_status(text, color)
    
    def add_auto_reply_rule(self):
        """添加自动回复规则"""
        dialog = AutoReplyRuleDialog(self.window)
        result = dialog.show()
        
        if result:
            keyword, reply_content, match_type, case_sensitive, priority, description = result
            rule_id = self.message_manager.add_auto_reply_rule(
                keyword=keyword,
                reply_content=reply_content,
                match_type=match_type,
                case_sensitive=case_sensitive,
                priority=priority,
                description=description
            )
            if rule_id:
                self.update_rules_tree()
                show_message("成功", "规则添加成功", "info", self.window)
            else:
                show_message("错误", "规则添加失败", "error", self.window)
    
    def edit_auto_reply_rule(self):
        """编辑自动回复规则"""
        selection = self.rules_tree.selection()
        if not selection:
            show_message("提示", "请先选择一个规则", "warning", self.window)
            return
        
        # 获取选中规则的索引
        item = selection[0]
        values = self.rules_tree.item(item, 'values')
        
        # 从数据库获取完整规则信息
        rules = self.message_manager.get_auto_reply_rules()
        rule_index = self.rules_tree.index(item)
        
        if 0 <= rule_index < len(rules):
            rule = rules[rule_index]
            
            dialog = AutoReplyRuleDialog(self.window, rule)
            result = dialog.show()
            
            if result:
                keyword, reply_content, match_type, case_sensitive, priority, description = result
                success = self.message_manager.update_auto_reply_rule(
                    rule_id=rule['id'],
                    keyword=keyword,
                    reply_content=reply_content,
                    match_type=match_type,
                    case_sensitive=case_sensitive,
                    priority=priority,
                    description=description
                )
                if success:
                    self.update_rules_tree()
                    show_message("成功", "规则更新成功", "info", self.window)
                else:
                    show_message("错误", "规则更新失败", "error", self.window)
    
    def delete_auto_reply_rule(self):
        """删除自动回复规则"""
        selection = self.rules_tree.selection()
        if not selection:
            show_message("提示", "请先选择一个规则", "warning", self.window)
            return
        
        if confirm_dialog("确认删除", "确定要删除选中的自动回复规则吗？", self.window):
            item = selection[0]
            rule_index = self.rules_tree.index(item)
            rules = self.message_manager.get_auto_reply_rules()
            
            if 0 <= rule_index < len(rules):
                rule = rules[rule_index]
                success = self.message_manager.delete_auto_reply_rule(rule['id'])
                if success:
                    self.update_rules_tree()
                    show_message("成功", "规则删除成功", "info", self.window)
                else:
                    show_message("错误", "规则删除失败", "error", self.window)
    
    def toggle_rule_status(self):
        """切换规则启用状态"""
        selection = self.rules_tree.selection()
        if not selection:
            show_message("提示", "请先选择一个规则", "warning", self.window)
            return
        
        item = selection[0]
        rule_index = self.rules_tree.index(item)
        rules = self.message_manager.get_auto_reply_rules()
        
        if 0 <= rule_index < len(rules):
            rule = rules[rule_index]
            success = self.message_manager.toggle_rule_status(rule['id'])
            if success:
                self.update_rules_tree()
    
    def update_rules_tree(self):
        """更新规则列表显示"""
        # 清空现有项目
        for item in self.rules_tree.get_children():
            self.rules_tree.delete(item)
        
        rules = self.message_manager.get_auto_reply_rules()
        enabled_count = 0
        disabled_count = 0
        
        for rule in rules:
            keyword = rule.get('keyword', '')[:15] + ('...' if len(rule.get('keyword', '')) > 15 else '')
            reply = rule.get('reply_content', '')[:25] + ('...' if len(rule.get('reply_content', '')) > 25 else '')
            description = rule.get('description', '')[:20] + ('...' if len(rule.get('description', '')) > 20 else '')
            
            # 匹配类型显示名称
            match_type_names = {
                'exact': '🎯精确',
                'contains': '📝包含',
                'startswith': '🚀开头',
                'endswith': '🎌结尾',
                'regex': '⚙️正则',
                'word_boundary': '🔍词边界',
                'fuzzy': '🌟智能',
                'fuzzy_contains': '💫智能包含'
            }
            match_type = match_type_names.get(rule.get('match_type', 'contains'), '📝包含')
            
            priority = rule.get('priority', 0)
            is_enabled = rule.get('enabled', True)
            
            if is_enabled:
                status = "🟢 启用"
                enabled_count += 1
            else:
                status = "🔴 禁用"
                disabled_count += 1
            
            # 插入行数据
            item = self.rules_tree.insert('', tk.END, values=(
                status, keyword, reply, match_type, priority, description
            ))
            
            # 根据状态设置行样式
            if not is_enabled:
                # 可以在这里设置禁用规则的特殊样式
                pass
        
        # 更新规则统计信息
        total_rules = len(rules)
        self.rules_count_label.config(text=f"规则总数: {total_rules}")
        self.active_rules_label.config(text=f"启用: {enabled_count}")
        self.disabled_rules_label.config(text=f"禁用: {disabled_count}")
    
    def show_rules_context_menu(self, event):
        """显示规则右键菜单"""
        try:
            self.rules_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.rules_menu.grab_release()
    
    def load_auto_reply_rules(self):
        """加载自动回复规则"""
        try:
            # 从数据库加载配置
            config = self.message_manager.db.get_account_config(self.uid)
            if config:
                self.auto_reply_var.set(config.get('auto_reply_enabled', False))
                self.delay_min_var.set(config.get('reply_delay_min', 1))
                self.delay_max_var.set(config.get('reply_delay_max', 3))
                self.daily_limit_var.set(config.get('daily_limit', 0))
                self.scan_interval_var.set(config.get('scan_interval', 8))
                
                # 更新状态显示
                if config.get('auto_reply_enabled', False):
                    # 如果配置显示为启用，但实际可能没有启动，需要检查
                    if self.message_manager.auto_reply_enabled and self.message_manager.listening_thread and self.message_manager.listening_thread.is_alive():
                        self.update_status_display("运行中", "green")
                    else:
                        self.update_status_display("已停止", "red")
                        self.auto_reply_var.set(False)
                else:
                    self.update_status_display("已停止", "red")
            
            self.update_rules_tree()
        except Exception as e:
            print(f"加载自动回复规则失败: {str(e)}")
    
    def start_refresh_thread(self):
        """启动自动刷新线程"""
        if self.refresh_thread and self.refresh_thread.is_alive():
            return
        
        def _auto_refresh():
            refresh_counter = 0
            while self.auto_refresh_enabled and self.window:
                try:
                    if self.window and self.window.winfo_exists():
                        # 每10秒刷新一次会话列表（提高频率）
                        if refresh_counter % 10 == 0:
                            try:
                                self.window.after(0, self.refresh_sessions)
                            except tk.TclError:
                                break
                        
                        # 每3秒更新一次统计信息
                        if refresh_counter % 3 == 0:
                            try:
                                self.window.after(0, self.update_stats)
                            except tk.TclError:
                                break
                        
                        # 如果有选中的会话，每5秒刷新一次消息
                        if self.current_session and refresh_counter % 5 == 0:
                            try:
                                self.window.after(0, self.load_session_messages)
                            except tk.TclError:
                                break
                    else:
                        break  # 窗口不存在，退出循环
                    
                    time.sleep(1)  # 每秒检查一次
                    refresh_counter += 1
                    
                    # 防止计数器溢出
                    if refresh_counter >= 1000:
                        refresh_counter = 0
                        
                except Exception as e:
                    print(f"自动刷新线程出错: {str(e)}")
                    break
        
        self.refresh_thread = threading.Thread(target=_auto_refresh, daemon=True)
        self.refresh_thread.start()
    
    def on_closing(self):
        """窗口关闭事件"""
        # 标记组件已销毁
        self._components_created = False
        self.auto_refresh_enabled = False
        
        # 停止自动回复监听
        if self.message_manager:
            self.message_manager.stop_auto_reply_listener()
        
        # 调用关闭回调
        if self.on_close_callback:
            try:
                self.on_close_callback()
            except Exception as e:
                print(f"执行关闭回调时出错: {str(e)}")
        
        if self.window:
            self.window.destroy()
            self.window = None

    def refresh_messages_timer(self):
        """消息列表刷新定时器"""
        if not self.window:
            return
        
        if self.message_manager and self.current_session:
            self.refresh_message_list()
        
        # 每5秒刷新一次消息列表
        try:
            self.window.after(5000, self.refresh_messages_timer)
        except tk.TclError:
            pass
    
    def refresh_message_list(self):
        """刷新当前会话的消息列表"""
        if not self.current_session or not self.message_manager:
            return
        
        try:
            talker_id = self.current_session.get('talker_id')
            session_type = self.current_session.get('session_type', 1)
            
            if not talker_id:
                return
            
            # 获取最新消息
            success, msg_data = self.message_manager.get_session_messages(talker_id, session_type, size=50)
            
            if success:
                new_messages = msg_data.get('messages', [])
                
                # 检查消息是否有变化
                current_messages = getattr(self, '_last_messages', [])
                if len(new_messages) != len(current_messages):
                    print(f"账号 {self.uid} 消息列表有更新，重新加载消息")
                    self._last_messages = new_messages
                    self.display_messages(new_messages)
            
        except Exception as e:
            print(f"刷新消息列表时出错: {str(e)}")
    
    def load_messages(self, talker_id, session_type=1):
        """加载会话消息"""
        if not self.current_session:
            return
        
        @run_in_thread
        def _load():
            try:
                # 检查窗口是否存在
                if not self.window:
                    return
                
                success, msg_data = self.message_manager.get_session_messages(talker_id, session_type, size=50)
                if success and self.window:
                    messages = msg_data.get('messages', [])
                    # 缓存当前消息
                    self._last_messages = messages
                    try:
                        self.window.after(0, lambda: self.display_messages(messages))
                    except tk.TclError:
                        pass
                # 如果失败，不显示错误消息
                    
            except Exception as e:
                print(f"加载消息失败: {str(e)}")
        
        _load()

    def reset_config(self):
        """重置配置到默认值"""
        if confirm_dialog("重置配置", "确定要重置配置到默认值吗？", self.window):
            self.delay_min_var.set(1)
            self.delay_max_var.set(3)
            self.daily_limit_var.set(0)
            self.scan_interval_var.set(8)
            self.save_config()
    
    def import_rules(self):
        """导入规则"""
        show_message("提示", "规则导入功能开发中...", "info", self.window)
    
    def export_rules(self):
        """导出规则"""
        show_message("提示", "规则导出功能开发中...", "info", self.window)
    
    def test_auto_reply_connection(self):
        """测试自动回复连接"""
        def _test():
            try:
                print(f"🔍 测试账号 {self.uid} 连接状态...")
                
                # 检查cookies
                cookies = dict(self.message_manager.session.cookies)
                print(f"Cookies状态: DedeUserID={cookies.get('DedeUserID')}, bili_jct={'存在' if cookies.get('bili_jct') else '缺失'}")
                
                # 测试获取会话列表
                success, sessions = self.message_manager.get_sessions()
                print(f"获取会话列表: {success}, 会话数量: {len(sessions) if success else 0}")
                
                if success and sessions:
                    # 测试获取第一个会话的消息
                    first_session = sessions[0]
                    talker_id = first_session.get('talker_id')
                    session_type = first_session.get('session_type', 1)
                    
                    success2, msg_data = self.message_manager.get_session_messages(talker_id, session_type, size=5)
                    print(f"获取消息: {success2}, 消息数量: {len(msg_data.get('messages', [])) if success2 else 0}")
                
                # 测试规则匹配
                rules = self.message_manager.get_auto_reply_rules(enabled_only=True)
                print(f"启用的规则数量: {len(rules)}")
                
                if rules:
                    test_message = "你好"
                    match_result = self.message_manager.match_auto_reply(test_message)
                    print(f"测试消息'{test_message}'匹配结果: {'匹配成功' if match_result else '无匹配'}")
                
            except Exception as e:
                print(f"❌ 测试连接失败: {str(e)}")
        
        # 启动线程
        import threading
        threading.Thread(target=_test, daemon=True).start()
    
    def sort_rules_column(self, col):
        """规则列排序"""
        # 实现规则列表排序功能
        pass
    
    def on_rule_select(self, event):
        """规则选择事件"""
        # 可以在这里添加规则选择后的操作
        pass

    def debug_message_api(self):
        """调试消息API"""
        @run_in_thread
        def _debug():
            try:
                self.add_log("🔧 开始API调试...", "info")
                if hasattr(self, 'message_manager') and self.message_manager:
                    self.message_manager.debug_message_api()
                else:
                    self.add_log("❌ 消息管理器未初始化", "error")
            except Exception as e:
                self.add_log(f"❌ API调试出错: {str(e)}", "error")
        
        _debug()


class AutoReplyRuleDialog:
    """自动回复规则对话框"""
    
    def __init__(self, parent, rule=None):
        """
        初始化对话框
        
        Args:
            parent: 父窗口
            rule: 编辑的规则（None表示新建）
        """
        self.parent = parent
        self.rule = rule
        self.result = None
        self.dialog = None
        
    def show(self):
        """显示对话框"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("新建自动回复规则" if not self.rule else "编辑自动回复规则")
        self.dialog.geometry("600x520")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        self.dialog.resizable(False, False)
        
        # 居中显示
        center_window(self.dialog, 600, 520)
        
        # 设置图标和样式
        self.dialog.configure(bg='#f0f0f0')
        
        self.init_ui()
        
        # 设置焦点到关键词输入框
        self.keyword_entry.focus_set()
        
        # 绑定快捷键
        self.dialog.bind('<Return>', lambda e: self.on_ok())
        self.dialog.bind('<Escape>', lambda e: self.on_cancel())
        
        # 等待对话框关闭
        self.dialog.wait_window()
        return self.result
    
    def init_ui(self):
        """初始化界面"""
        # 主容器
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题区域
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_text = "🤖 新建自动回复规则" if not self.rule else "✏️ 编辑自动回复规则"
        title_label = ttk.Label(title_frame, text=title_text, font=('微软雅黑', 14, 'bold'))
        title_label.pack(anchor='w')
        
        subtitle_text = "设置触发关键词和自动回复内容" if not self.rule else "修改规则配置"
        subtitle_label = ttk.Label(title_frame, text=subtitle_text, font=('微软雅黑', 9), foreground='#666666')
        subtitle_label.pack(anchor='w', pady=(5, 0))
        
        # 创建滚动区域
        canvas = tk.Canvas(main_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 基本信息组
        basic_group = ttk.LabelFrame(scrollable_frame, text="📝 基本设置", padding="15")
        basic_group.pack(fill=tk.X, pady=(0, 15))
        
        # 关键词
        ttk.Label(basic_group, text="触发关键词:", font=('微软雅黑', 9, 'bold')).grid(row=0, column=0, sticky='w', pady=(0, 5))
        self.keyword_entry = ttk.Entry(basic_group, width=60, font=('微软雅黑', 10))
        self.keyword_entry.grid(row=0, column=1, columnspan=2, sticky='ew', pady=(0, 5))
        
        ttk.Label(basic_group, text="当接收到包含此关键词的消息时触发自动回复", 
                 font=('微软雅黑', 8), foreground='#666666').grid(row=1, column=1, columnspan=2, sticky='w', pady=(0, 10))
        
        # 回复内容
        ttk.Label(basic_group, text="回复内容:", font=('微软雅黑', 9, 'bold')).grid(row=2, column=0, sticky='nw', pady=(5, 0))
        
        reply_frame = ttk.Frame(basic_group)
        reply_frame.grid(row=2, column=1, columnspan=2, sticky='ew', pady=(5, 0))
        
        self.reply_text = tk.Text(reply_frame, width=55, height=6, wrap=tk.WORD, font=('微软雅黑', 10),
                                 relief='solid', borderwidth=1)
        reply_scrollbar = ttk.Scrollbar(reply_frame, orient="vertical", command=self.reply_text.yview)
        self.reply_text.configure(yscrollcommand=reply_scrollbar.set)
        
        self.reply_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        reply_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 字符计数
        self.char_count_label = ttk.Label(basic_group, text="0/500 字符", font=('微软雅黑', 8), foreground='#666666')
        self.char_count_label.grid(row=3, column=1, columnspan=2, sticky='e', pady=(2, 0))
        
        # 绑定文本变化事件
        self.reply_text.bind('<KeyRelease>', self.update_char_count)
        self.reply_text.bind('<Button-1>', self.update_char_count)
        
        basic_group.columnconfigure(1, weight=1)
        
        # 匹配设置组
        match_group = ttk.LabelFrame(scrollable_frame, text="🎯 匹配设置", padding="15")
        match_group.pack(fill=tk.X, pady=(0, 15))
        
        # 匹配方式
        ttk.Label(match_group, text="匹配方式:", font=('微软雅黑', 9, 'bold')).grid(row=0, column=0, sticky='w', pady=(0, 10))
        
        self.match_type_var = tk.StringVar(value="contains")
        match_frame = ttk.Frame(match_group)
        match_frame.grid(row=0, column=1, columnspan=2, sticky='w', pady=(0, 10))
        
        # 匹配方式选项 - 重新组织布局
        match_options = [
            ("🎯 精确匹配", "exact", "完全相同才匹配"),
            ("📝 包含匹配", "contains", "消息中包含关键词即匹配"),
            ("🚀 开头匹配", "startswith", "消息以关键词开头"),
            ("🎌 结尾匹配", "endswith", "消息以关键词结尾"),
            ("⚙️ 正则表达式", "regex", "使用正则表达式匹配"),
            ("🔍 词语边界", "word_boundary", "作为完整词语匹配"),
            ("🌟 智能匹配", "fuzzy", "容错匹配，相似度>80%"),
            ("💫 智能包含", "fuzzy_contains", "智能包含匹配")
        ]
        
        for i, (text, value, desc) in enumerate(match_options):
            row = i // 2
            col = i % 2
            
            option_frame = ttk.Frame(match_frame)
            option_frame.grid(row=row, column=col, sticky='w', padx=(0, 20), pady=2)
            
            ttk.Radiobutton(option_frame, text=text, variable=self.match_type_var, 
                           value=value, width=15).pack(anchor='w')
            ttk.Label(option_frame, text=desc, font=('微软雅黑', 7), 
                     foreground='#888888').pack(anchor='w')
        
        # 匹配选项
        options_frame = ttk.Frame(match_group)
        options_frame.grid(row=1, column=1, columnspan=2, sticky='w', pady=(10, 0))
        
        self.case_sensitive_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="🔤 区分大小写", 
                       variable=self.case_sensitive_var).pack(side=tk.LEFT, padx=(0, 20))
        
        # 高级设置组
        advanced_group = ttk.LabelFrame(scrollable_frame, text="⚙️ 高级设置", padding="15")
        advanced_group.pack(fill=tk.X, pady=(0, 15))
        
        # 优先级
        priority_frame = ttk.Frame(advanced_group)
        priority_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(priority_frame, text="优先级:", font=('微软雅黑', 9, 'bold')).pack(side=tk.LEFT)
        
        self.priority_var = tk.IntVar(value=0)
        priority_spinbox = ttk.Spinbox(priority_frame, from_=-100, to=100, width=10, 
                                      textvariable=self.priority_var)
        priority_spinbox.pack(side=tk.LEFT, padx=(10, 0))
        
        ttk.Label(priority_frame, text="(数值越大优先级越高，默认为0)", 
                 font=('微软雅黑', 8), foreground='#666666').pack(side=tk.LEFT, padx=(10, 0))
        
        # 描述
        desc_frame = ttk.Frame(advanced_group)
        desc_frame.pack(fill=tk.X)
        
        ttk.Label(desc_frame, text="规则描述:", font=('微软雅黑', 9, 'bold')).pack(anchor='w')
        self.description_entry = ttk.Entry(desc_frame, width=60, font=('微软雅黑', 10))
        self.description_entry.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(desc_frame, text="可选，用于标识和管理规则", 
                 font=('微软雅黑', 8), foreground='#666666').pack(anchor='w', pady=(2, 0))
        
        # 预览区域
        preview_group = ttk.LabelFrame(scrollable_frame, text="👀 规则预览", padding="15")
        preview_group.pack(fill=tk.X, pady=(0, 15))
        
        self.preview_text = tk.Text(preview_group, height=4, wrap=tk.WORD, 
                                   font=('微软雅黑', 9), state=tk.DISABLED,
                                   bg='#f8f8f8', relief='solid', borderwidth=1)
        self.preview_text.pack(fill=tk.X)
        
        # 绑定实时预览更新
        self.keyword_entry.bind('<KeyRelease>', self.update_preview)
        self.reply_text.bind('<KeyRelease>', self.update_preview)
        self.match_type_var.trace('w', lambda *args: self.update_preview())
        self.case_sensitive_var.trace('w', lambda *args: self.update_preview())
        self.priority_var.trace('w', lambda *args: self.update_preview())
        
        # 配置滚动区域
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        # 按钮样式
        style = ttk.Style()
        style.configure('Accent.TButton', font=('微软雅黑', 10, 'bold'))
        
        ttk.Button(button_frame, text="✅ 确定", command=self.on_ok, 
                  style='Accent.TButton', width=12).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="❌ 取消", command=self.on_cancel, 
                  width=12).pack(side=tk.RIGHT)
        
        # 测试按钮
        ttk.Button(button_frame, text="🧪 测试匹配", command=self.test_match, 
                  width=12).pack(side=tk.LEFT)
        
        # 如果是编辑模式，填充现有数据
        if self.rule:
            self.load_rule_data()
        
        # 初始化预览
        self.dialog.after(100, self.update_preview)
        self.dialog.after(100, self.update_char_count)
    
    def load_rule_data(self):
        """加载规则数据到界面"""
        self.keyword_entry.insert(0, self.rule.get('keyword', ''))
        self.reply_text.insert(1.0, self.rule.get('reply_content', ''))
        self.match_type_var.set(self.rule.get('match_type', 'contains'))
        self.case_sensitive_var.set(self.rule.get('case_sensitive', False))
        self.priority_var.set(self.rule.get('priority', 0))
        self.description_entry.insert(0, self.rule.get('description', ''))
    
    def update_char_count(self, event=None):
        """更新字符计数"""
        content = self.reply_text.get(1.0, tk.END).strip()
        char_count = len(content)
        
        color = '#666666'
        if char_count > 500:
            color = 'red'
        elif char_count > 400:
            color = 'orange'
        
        self.char_count_label.config(text=f"{char_count}/500 字符", foreground=color)
    
    def update_preview(self, event=None):
        """更新规则预览"""
        try:
            keyword = self.keyword_entry.get().strip()
            reply_content = self.reply_text.get(1.0, tk.END).strip()
            match_type = self.match_type_var.get()
            case_sensitive = self.case_sensitive_var.get()
            priority = self.priority_var.get()
            
            # 匹配类型说明
            match_type_desc = {
                'exact': '精确匹配',
                'contains': '包含匹配',
                'startswith': '开头匹配',
                'endswith': '结尾匹配',
                'regex': '正则表达式',
                'word_boundary': '词语边界',
                'fuzzy': '智能匹配',
                'fuzzy_contains': '智能包含'
            }.get(match_type, '未知')
            
            preview_text = f"""规则配置预览：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 触发关键词: {keyword or '(未设置)'}
🎯 匹配方式: {match_type_desc}
🔤 区分大小写: {'是' if case_sensitive else '否'}
⭐ 优先级: {priority}
💬 回复内容: {reply_content[:50] + '...' if len(reply_content) > 50 else reply_content or '(未设置)'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
            
            self.preview_text.config(state=tk.NORMAL)
            self.preview_text.delete(1.0, tk.END)
            self.preview_text.insert(1.0, preview_text)
            self.preview_text.config(state=tk.DISABLED)
            
        except Exception as e:
            pass
    
    def test_match(self):
        """测试匹配功能"""
        keyword = self.keyword_entry.get().strip()
        if not keyword:
            show_message("提示", "请先输入关键词", "warning", self.dialog)
            return
        
        test_text = ask_string("测试匹配", "请输入要测试的消息内容:", self.dialog)
        if not test_text:
            return
        
        # 模拟匹配测试
        match_type = self.match_type_var.get()
        case_sensitive = self.case_sensitive_var.get()
        
        # 处理大小写敏感
        if case_sensitive:
            text_to_match = test_text
            keyword_to_match = keyword
        else:
            text_to_match = test_text.lower()
            keyword_to_match = keyword.lower()
        
        matched = False
        try:
            if match_type == 'exact':
                matched = text_to_match.strip() == keyword_to_match.strip()
            elif match_type == 'contains':
                matched = keyword_to_match in text_to_match
            elif match_type == 'startswith':
                matched = text_to_match.startswith(keyword_to_match)
            elif match_type == 'endswith':
                matched = text_to_match.endswith(keyword_to_match)
            elif match_type == 'regex':
                import re
                flags = 0 if case_sensitive else re.IGNORECASE
                matched = bool(re.search(keyword, test_text, flags))
            elif match_type == 'word_boundary':
                import re
                pattern = r'\b' + re.escape(keyword_to_match) + r'\b'
                flags = 0 if case_sensitive else re.IGNORECASE
                matched = bool(re.search(pattern, text_to_match, flags))
            elif match_type == 'fuzzy':
                from difflib import SequenceMatcher
                similarity = SequenceMatcher(None, text_to_match, keyword_to_match).ratio()
                matched = similarity >= 0.8
            elif match_type == 'fuzzy_contains':
                if len(keyword_to_match) <= 3:
                    matched = keyword_to_match in text_to_match
                else:
                    words = keyword_to_match.split()
                    matched = any(word in text_to_match for word in words if len(word) > 1)
        except Exception as e:
            show_message("错误", f"匹配测试失败: {str(e)}", "error", self.dialog)
            return
        
        result_msg = f"测试结果：{'✅ 匹配成功' if matched else '❌ 匹配失败'}\n\n"
        result_msg += f"测试消息：{test_text}\n"
        result_msg += f"关键词：{keyword}\n"
        result_msg += f"匹配方式：{match_type}\n"
        result_msg += f"区分大小写：{'是' if case_sensitive else '否'}"
        
        if matched:
            reply_content = self.reply_text.get(1.0, tk.END).strip()
            if reply_content:
                result_msg += f"\n\n将会回复：{reply_content}"
        
        show_message("匹配测试结果", result_msg, "info" if matched else "warning", self.dialog)
    
    def validate_input(self):
        """验证输入数据"""
        keyword = self.keyword_entry.get().strip()
        reply_content = self.reply_text.get(1.0, tk.END).strip()
        
        if not keyword:
            show_message("输入错误", "关键词不能为空！", "error", self.dialog)
            self.keyword_entry.focus_set()
            return False
        
        if len(keyword) > 100:
            show_message("输入错误", "关键词长度不能超过100个字符！", "error", self.dialog)
            self.keyword_entry.focus_set()
            return False
        
        if not reply_content:
            show_message("输入错误", "回复内容不能为空！", "error", self.dialog)
            self.reply_text.focus_set()
            return False
        
        if len(reply_content) > 500:
            show_message("输入错误", "回复内容长度不能超过500个字符！", "error", self.dialog)
            self.reply_text.focus_set()
            return False
        
        # 验证正则表达式
        if self.match_type_var.get() == 'regex':
            try:
                import re
                re.compile(keyword)
            except re.error as e:
                show_message("输入错误", f"正则表达式格式错误：{str(e)}", "error", self.dialog)
                self.keyword_entry.focus_set()
                return False
        
        return True
    
    def on_ok(self):
        """确定按钮"""
        if not self.validate_input():
            return
        
        keyword = self.keyword_entry.get().strip()
        reply_content = self.reply_text.get(1.0, tk.END).strip()
        match_type = self.match_type_var.get()
        case_sensitive = self.case_sensitive_var.get()
        priority = self.priority_var.get()
        description = self.description_entry.get().strip()
        
        self.result = (keyword, reply_content, match_type, case_sensitive, priority, description)
        self.dialog.destroy()
    
    def on_cancel(self):
        """取消按钮"""
        self.result = None
        self.dialog.destroy() 