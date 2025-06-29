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
from tkinter import ttk
import threading
import time
from typing import Optional

from ..core import BilibiliLogin, QRCodeHandler
from ..utils import center_window, show_message, ask_string, run_in_thread


class LoginWindow:
    def __init__(self, parent, account_manager, config):
        """
        初始化登录窗口
        
        Args:
            parent: 父窗口
            account_manager: 账号管理器
            config: 配置管理器
        """
        self.parent = parent
        self.account_manager = account_manager
        self.config = config
        
        self.login_handler = BilibiliLogin()
        self.qr_handler = QRCodeHandler()
        
        self.window = None
        self.qr_label = None
        self.status_label = None
        self.progress = None
        
        self.login_thread = None
        self.polling = False
        self.qr_photo = None
        
    def show(self):
        """显示登录窗口"""
        self.window = tk.Toplevel(self.parent)
        self.window.title("扫码登录")
        self.window.geometry("500x600")
        self.window.transient(self.parent)
        self.window.grab_set()
        
        # 居中显示
        center_window(self.window, 500, 600)
        
        # 初始化UI
        self.init_ui()
        
        # 绑定关闭事件
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 开始登录流程
        self.start_login()
    
    def init_ui(self):
        """初始化用户界面"""
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        # 标题
        title_label = ttk.Label(main_frame, text="B站账号扫码登录", 
                               font=('微软雅黑', 16, 'bold'))
        title_label.grid(row=0, column=0, pady=(0, 20))
        
        # 说明文本
        desc_label = ttk.Label(main_frame, text="请使用哔哩哔哩手机APP扫描下方二维码", 
                              font=('微软雅黑', 10))
        desc_label.grid(row=1, column=0, pady=(0, 10))
        
        # 二维码显示区域
        qr_frame = ttk.LabelFrame(main_frame, text="二维码", padding="10")
        qr_frame.grid(row=2, column=0, pady=(0, 20), sticky=(tk.W, tk.E))
        qr_frame.columnconfigure(0, weight=1)
        
        # 二维码标签
        self.qr_label = ttk.Label(qr_frame, text="正在生成二维码...", 
                                 font=('微软雅黑', 12), anchor='center')
        self.qr_label.grid(row=0, column=0, pady=20)
        
        # 状态显示
        self.status_label = ttk.Label(main_frame, text="正在申请二维码...", 
                                     font=('微软雅黑', 10), foreground='blue')
        self.status_label.grid(row=3, column=0, pady=(0, 10))
        
        # 进度条
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        
        # 账号名称输入区域
        name_frame = ttk.LabelFrame(main_frame, text="账号设置（可选）", padding="10")
        name_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        name_frame.columnconfigure(1, weight=1)
        
        ttk.Label(name_frame, text="自定义名称:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(name_frame, textvariable=self.name_var, width=30)
        self.name_entry.grid(row=0, column=1, sticky=(tk.W, tk.E))
        
        ttk.Label(name_frame, text="留空则使用默认用户名", 
                 font=('微软雅黑', 8), foreground='gray').grid(row=1, column=0, columnspan=2, 
                                                            sticky=tk.W, pady=(5, 0))
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, pady=(0, 10))
        
        self.refresh_btn = ttk.Button(button_frame, text="刷新二维码", 
                                     command=self.refresh_qrcode, state=tk.DISABLED)
        self.refresh_btn.grid(row=0, column=0, padx=(0, 10))
        
        self.cancel_btn = ttk.Button(button_frame, text="取消", 
                                    command=self.on_closing)
        self.cancel_btn.grid(row=0, column=1)
    
    def start_login(self):
        """开始登录流程"""
        self.progress.start()
        self.polling = True
        
        # 在新线程中执行登录
        self.login_thread = run_in_thread(self._login_process)
    
    def _login_process(self):
        """登录处理流程（在新线程中执行）"""
        try:
            # 申请二维码
            self.update_status("正在申请二维码...")
            success, qr_url, qrcode_key = self.login_handler.get_qrcode()
            
            if not success:
                self.update_status(f"申请二维码失败: {qr_url}", "error")
                return
            
            # 生成二维码图片
            self.update_status("正在生成二维码...")
            qr_config = self.config.get_qrcode_config()
            qr_size = qr_config.get('size', (250, 250))
            
            self.qr_photo = self.qr_handler.generate_qrcode_for_tkinter(qr_url, qr_size)
            
            if self.qr_photo:
                # 在主线程中更新UI
                self.window.after(0, self._update_qr_display)
                self.update_status("请使用手机APP扫描二维码")
                
                # 启用刷新按钮
                self.window.after(0, lambda: self.refresh_btn.config(state=tk.NORMAL))
                
                # 开始轮询登录状态
                self._poll_login_status()
            else:
                self.update_status("生成二维码失败", "error")
                
        except Exception as e:
            self.update_status(f"登录过程出错: {str(e)}", "error")
    
    def _update_qr_display(self):
        """更新二维码显示"""
        if self.qr_photo and self.qr_label:
            self.qr_label.config(image=self.qr_photo, text="")
    
    def _poll_login_status(self):
        """轮询登录状态"""
        if not self.polling:
            return
        
        try:
            status_code, message, cookies = self.login_handler.poll_login_status()
            
            if status_code == 0:  # 登录成功
                self.update_status("登录成功！正在保存账号信息...", "success")
                self._handle_login_success(cookies)
                
            elif status_code == 86101:  # 未扫码
                self.update_status("等待扫码...")
                # 继续轮询
                if self.polling:
                    threading.Timer(2.0, self._poll_login_status).start()
                    
            elif status_code == 86090:  # 已扫码未确认
                self.update_status("扫码成功！请在手机上确认登录...", "warning")
                # 继续轮询
                if self.polling:
                    threading.Timer(1.0, self._poll_login_status).start()
                    
            elif status_code == 86038:  # 二维码已失效
                self.update_status("二维码已失效，请刷新后重试", "error")
                self.polling = False
                
            else:
                self.update_status(f"登录状态异常: {message}", "error")
                # 继续轮询，可能是临时问题
                if self.polling:
                    threading.Timer(3.0, self._poll_login_status).start()
                    
        except Exception as e:
            self.update_status(f"检查登录状态失败: {str(e)}", "error")
            # 继续轮询
            if self.polling:
                threading.Timer(5.0, self._poll_login_status).start()
    
    def _handle_login_success(self, cookies):
        """处理登录成功"""
        try:
            # 验证登录并获取用户信息
            is_valid, user_info = self.login_handler.verify_login(cookies)
            
            if is_valid:
                # 获取自定义账号名称
                custom_name = self.name_var.get().strip()
                account_name = custom_name if custom_name else None
                
                # 添加账号
                uid = self.account_manager.add_account(cookies, user_info, account_name)
                
                # 切换到新账号
                self.account_manager.switch_account(uid)
                
                self.update_status("账号添加成功！", "success")
                
                # 显示成功信息
                username = user_info.get('uname', '用户')
                display_name = account_name if account_name else username
                
                self.window.after(0, lambda: show_message(
                    "登录成功", 
                    f"账号 '{display_name}' 登录成功！\n用户名: {username}\nUID: {user_info.get('mid')}", 
                    "info", 
                    self.window
                ))
                
                # 延迟关闭窗口
                self.window.after(2000, self.close_window)
                
            else:
                self.update_status("登录验证失败", "error")
                
        except Exception as e:
            self.update_status(f"保存账号信息失败: {str(e)}", "error")
    
    def update_status(self, message, status_type="info"):
        """
        更新状态显示
        
        Args:
            message: 状态消息
            status_type: 状态类型 (info, warning, error, success)
        """
        color_map = {
            "info": "blue",
            "warning": "orange", 
            "error": "red",
            "success": "green"
        }
        
        color = color_map.get(status_type, "black")
        
        if self.status_label:
            self.window.after(0, lambda: self.status_label.config(text=message, foreground=color))
    
    def refresh_qrcode(self):
        """刷新二维码"""
        self.refresh_btn.config(state=tk.DISABLED)
        self.polling = False
        
        # 重新开始登录流程
        self.start_login()
    
    def on_closing(self):
        """窗口关闭事件"""
        self.polling = False
        self.progress.stop()
        self.close_window()
    
    def close_window(self):
        """关闭窗口"""
        if self.window:
            self.window.destroy() 