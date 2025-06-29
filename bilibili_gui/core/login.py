#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Version: 1.0.0
Author: @OxenFxc
Copyright: https://github.com/OxenFxc
License: MIT License
Description: B站多账号扫码登录系统 - 自动私信回复功能
"""

import requests
import time
from typing import Tuple, Dict


class BilibiliLogin:
    def __init__(self):
        """初始化登录器"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://passport.bilibili.com/'
        })
        self.qrcode_key = None
        
    def get_qrcode(self) -> Tuple[bool, str, str]:
        """
        申请二维码
        
        Returns:
            Tuple[bool, str, str]: (成功标志, 二维码URL, 二维码密钥)
        """
        url = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 0:
                qr_data = data.get('data', {})
                qr_url = qr_data.get('url', '')
                qrcode_key = qr_data.get('qrcode_key', '')
                
                self.qrcode_key = qrcode_key
                return True, qr_url, qrcode_key
            else:
                return False, "", data.get('message', '未知错误')
                
        except Exception as e:
            return False, "", f"网络请求失败: {str(e)}"
    
    def poll_login_status(self) -> Tuple[int, str, Dict]:
        """
        轮询登录状态
        
        Returns:
            Tuple[int, str, Dict]: (状态码, 状态信息, Cookie数据)
        """
        if not self.qrcode_key:
            return -1, "未获取到二维码密钥", {}
        
        url = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
        params = {
            'qrcode_key': self.qrcode_key
        }
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 0:
                poll_data = data.get('data', {})
                status_code = poll_data.get('code')
                message = poll_data.get('message', '')
                
                # 提取Cookie
                cookies = {}
                if status_code == 0:  # 登录成功
                    for cookie in response.cookies:
                        cookies[cookie.name] = cookie.value
                
                return status_code, message, cookies
            else:
                return -1, data.get('message', '未知错误'), {}
                
        except Exception as e:
            return -1, f"网络请求失败: {str(e)}", {}
    
    def verify_login(self, cookies: Dict) -> Tuple[bool, Dict]:
        """
        验证登录状态
        
        Args:
            cookies (Dict): Cookie字典
            
        Returns:
            Tuple[bool, Dict]: (登录状态, 用户信息)
        """
        url = "https://api.bilibili.com/x/web-interface/nav"
        
        # 创建临时session
        temp_session = requests.Session()
        temp_session.headers.update(self.session.headers)
        
        # 设置Cookie
        for name, value in cookies.items():
            temp_session.cookies.set(name, value)
        
        try:
            response = temp_session.get(url)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 0:
                user_data = data.get('data', {})
                if user_data.get('isLogin'):
                    return True, user_data
            
            return False, {}
            
        except Exception as e:
            return False, {} 