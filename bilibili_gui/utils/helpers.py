#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Version: 1.0.0
Author: @OxenFxc
Copyright: https://github.com/OxenFxc
License: MIT License
Description: B站多账号扫码登录系统 - 自动私信回复功能
"""

import time
import tkinter as tk
from tkinter import messagebox
from typing import Any, Optional
import threading


def format_time(timestamp: float, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    try:
        return time.strftime(format_str, time.localtime(timestamp))
    except (ValueError, OSError):
        return "未知时间"


def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}分钟"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours}小时"
    else:
        days = seconds // 86400
        return f"{days}天"


def show_message(title: str, message: str, msg_type: str = "info", parent: tk.Widget = None):
    try:
        if msg_type == "info":
            messagebox.showinfo(title, message, parent=parent)
        elif msg_type == "warning":
            messagebox.showwarning(title, message, parent=parent)
        elif msg_type == "error":
            messagebox.showerror(title, message, parent=parent)
        else:
            messagebox.showinfo(title, message, parent=parent)
    except Exception as e:
        print(f"显示消息对话框失败: {str(e)}")


def confirm_dialog(title: str, message: str, parent: tk.Widget = None) -> bool:
    try:
        return messagebox.askyesno(title, message, parent=parent)
    except Exception as e:
        print(f"显示确认对话框失败: {str(e)}")
        return False


def ask_string(title: str, prompt: str, parent: tk.Widget = None, initial_value: str = "") -> Optional[str]:
    try:
        from tkinter import simpledialog
        return simpledialog.askstring(title, prompt, parent=parent, initialvalue=initial_value)
    except Exception as e:
        print(f"显示输入对话框失败: {str(e)}")
        return None


def center_window(window: tk.Tk, width: int, height: int):
    try:
        # 获取屏幕尺寸
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        
        # 计算居中位置
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        # 设置窗口位置和大小
        window.geometry(f"{width}x{height}+{x}+{y}")
    except Exception as e:
        print(f"窗口居中失败: {str(e)}")


def run_in_thread(func, *args, **kwargs):
    thread = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
    thread.start()
    return thread


def safe_call(func, *args, **kwargs) -> tuple:
    try:
        result = func(*args, **kwargs)
        return True, result
    except Exception as e:
        return False, str(e)


def validate_url(url: str) -> bool:
    try:
        import re
        pattern = r'^https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*)?(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?$'
        return bool(re.match(pattern, url))
    except Exception:
        return False


class StatusManager:
    def __init__(self):
        """初始化状态管理器"""
        self._status = {}
        self._callbacks = {}
    
    def set_status(self, key: str, value: Any):
        """
        设置状态
        
        Args:
            key (str): 状态键
            value (Any): 状态值
        """
        old_value = self._status.get(key)
        self._status[key] = value
        
        # 如果值发生变化，调用回调函数
        if old_value != value and key in self._callbacks:
            for callback in self._callbacks[key]:
                try:
                    callback(key, value, old_value)
                except Exception as e:
                    print(f"状态回调执行失败: {str(e)}")
    
    def get_status(self, key: str, default: Any = None) -> Any:
        """
        获取状态
        
        Args:
            key (str): 状态键
            default (Any): 默认值
            
        Returns:
            Any: 状态值
        """
        return self._status.get(key, default)
    
    def register_callback(self, key: str, callback):
        """
        注册状态变化回调
        
        Args:
            key (str): 状态键
            callback: 回调函数
        """
        if key not in self._callbacks:
            self._callbacks[key] = []
        self._callbacks[key].append(callback)
    
    def unregister_callback(self, key: str, callback):
        """
        取消注册回调
        
        Args:
            key (str): 状态键
            callback: 回调函数
        """
        if key in self._callbacks and callback in self._callbacks[key]:
            self._callbacks[key].remove(callback) 