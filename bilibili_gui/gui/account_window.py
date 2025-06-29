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
from ..utils import center_window, format_time, show_message


class AccountWindow:
    def __init__(self, parent, account_manager, uid):
        """
        初始化账号详情窗口
        
        Args:
            parent: 父窗口
            account_manager: 账号管理器
            uid: 账号UID
        """
        self.parent = parent
        self.account_manager = account_manager
        self.uid = uid
        self.window = None
        
    def show(self):
        """显示账号详情窗口"""
        account_info = self.account_manager.get_account_info(self.uid)
        if not account_info:
            show_message("错误", "账号信息不存在", "error", self.parent)
            return
        
        self.window = tk.Toplevel(self.parent)
        self.window.title(f"账号详情 - {account_info.get('display_name', '未知')}")
        self.window.geometry("600x700")
        self.window.transient(self.parent)
        self.window.grab_set()
        
        # 居中显示
        center_window(self.window, 600, 700)
        
        # 初始化UI
        self.init_ui(account_info)
    
    def init_ui(self, account_info):
        """初始化用户界面"""
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # 标题
        title_label = ttk.Label(main_frame, text=f"账号详情", 
                               font=('微软雅黑', 16, 'bold'))
        title_label.grid(row=0, column=0, pady=(0, 20))
        
        # 创建滚动文本区域
        text_frame = ttk.Frame(main_frame)
        text_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        # 详细信息文本
        info_text = tk.Text(text_frame, wrap=tk.WORD, font=('微软雅黑', 10), 
                           state=tk.DISABLED)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=info_text.yview)
        info_text.configure(yscrollcommand=scrollbar.set)
        
        info_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # 生成详细信息内容
        content = self.generate_account_details(account_info)
        
        info_text.config(state=tk.NORMAL)
        info_text.insert(1.0, content)
        info_text.config(state=tk.DISABLED)
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, pady=(20, 0))
        
        ttk.Button(button_frame, text="关闭", 
                  command=self.window.destroy).pack()
    
    def generate_account_details(self, account_info):
        """生成账号详细信息文本"""
        user_info = account_info.get('user_info', {})
        
        content = f"""账号基本信息
{'='*50}
显示名称：{account_info.get('display_name', '未知')}
用户名：{user_info.get('uname', '未知')}
UID：{user_info.get('mid', '未知')}
登录时间：{format_time(account_info.get('login_time', 0))}
最后验证：{format_time(account_info.get('last_verify', 0))}

用户等级信息
{'='*50}
当前等级：Lv{user_info.get('level_info', {}).get('current_level', 0)}
当前经验：{user_info.get('level_info', {}).get('current_exp', 0)}
升级所需经验：{user_info.get('level_info', {}).get('next_exp', '--')}

资产信息
{'='*50}
硬币数量：{user_info.get('money', 0)}
节操值：{user_info.get('moral', 0)}

会员信息
{'='*50}"""
        
        if user_info.get('vipStatus'):
            vip_label = user_info.get('vip_label', {})
            content += f"""
会员类型：{vip_label.get('text', '大会员')}
会员状态：{user_info.get('vipType', 0)}"""
            
            vip_due = user_info.get('vipDueDate', 0)
            if vip_due > 0:
                due_date = format_time(vip_due / 1000, "%Y-%m-%d %H:%M:%S")
                content += f"""
到期时间：{due_date}"""
        else:
            content += """
会员状态：非会员"""
        
        # 认证信息
        official = user_info.get('official', {})
        content += f"""

认证信息
{'='*50}"""
        
        if official.get('type') != -1:
            content += f"""
认证状态：已认证
认证类型：{official.get('role', 0)}
认证标题：{official.get('title', '已认证')}
认证描述：{official.get('desc', '无')}"""
        else:
            content += """
认证状态：未认证"""
        
        # 头像挂件信息
        pendant = user_info.get('pendant', {})
        if pendant.get('pid', 0) > 0:
            content += f"""

头像挂件
{'='*50}
挂件名称：{pendant.get('name', '未知')}
挂件ID：{pendant.get('pid', 0)}"""
        
        return content 