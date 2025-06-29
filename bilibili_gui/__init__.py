#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Version: 1.0.0
Author: @OxenFxc
Copyright: https://github.com/OxenFxc
License: MIT License
Description: B站多账号扫码登录系统 - 自动私信回复功能
"""

__version__ = "1.0.0"
__author__ = "BiliRe Project"
__description__ = "B站多账号扫码登录系统GUI版本"

# 导出主要类和函数
from .gui import MainWindow
from .core import BilibiliLogin, AccountManager, QRCodeHandler
from .utils import Config, show_message

__all__ = [
    'MainWindow',
    'BilibiliLogin', 
    'AccountManager',
    'QRCodeHandler',
    'Config',
    'show_message'
] 
