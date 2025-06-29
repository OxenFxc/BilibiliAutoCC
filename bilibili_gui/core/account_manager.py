#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Version: 1.0.0
Author: @OxenFxc
Copyright: https://github.com/OxenFxc
License: MIT License
Description: B站多账号扫码登录系统 - 自动私信回复功能
"""

import json
import os
import time
from typing import Dict, List, Optional, Tuple
from .login import BilibiliLogin


class AccountManager:
    def __init__(self, accounts_file: str = "bilibili_accounts.json"):
        """
        初始化账号管理器
        
        Args:
            accounts_file (str): 账号数据文件路径
        """
        self.accounts_file = accounts_file
        self.current_account = None
        self.current_cookies = {}
        self.login_handler = BilibiliLogin()
        
    def load_accounts(self) -> Dict:
        """
        加载所有账号数据
        
        Returns:
            Dict: 账号数据字典
        """
        try:
            if os.path.exists(self.accounts_file):
                with open(self.accounts_file, 'r', encoding='utf-8') as f:
                    accounts = json.load(f)
                return accounts
        except Exception as e:
            print(f"加载账号数据失败: {str(e)}")
        return {}
    
    def save_accounts(self, accounts: Dict):
        """
        保存所有账号数据
        
        Args:
            accounts (Dict): 账号数据字典
        """
        try:
            with open(self.accounts_file, 'w', encoding='utf-8') as f:
                json.dump(accounts, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise Exception(f"保存账号数据失败: {str(e)}")
    
    def add_account(self, cookies: Dict, user_info: Dict, account_name: str = None) -> str:
        """
        添加新账号
        
        Args:
            cookies (Dict): Cookie字典
            user_info (Dict): 用户信息
            account_name (str): 自定义账号名称
            
        Returns:
            str: 账号ID
        """
        accounts = self.load_accounts()
        
        uid = str(user_info.get('mid', ''))
        username = user_info.get('uname', f'用户{uid}')
        
        # 使用自定义名称或默认用户名
        display_name = account_name if account_name else username
        
        account_data = {
            'uid': uid,
            'username': username,
            'display_name': display_name,
            'cookies': cookies,
            'user_info': user_info,
            'login_time': time.time(),
            'last_verify': time.time()
        }
        
        accounts[uid] = account_data
        self.save_accounts(accounts)
        
        return uid
    
    def list_accounts(self) -> List[Dict]:
        """
        列出所有账号
        
        Returns:
            List[Dict]: 账号列表
        """
        accounts = self.load_accounts()
        account_list = []
        
        for uid, account_data in accounts.items():
            # 验证账号状态
            is_valid, _ = self.login_handler.verify_login(account_data.get('cookies', {}))
            
            account_info = {
                'uid': uid,
                'username': account_data.get('username', ''),
                'display_name': account_data.get('display_name', ''),
                'login_time': account_data.get('login_time', 0),
                'last_verify': account_data.get('last_verify', 0),
                'is_valid': is_valid,
                'user_info': account_data.get('user_info', {})
            }
            account_list.append(account_info)
        
        return account_list
    
    def switch_account(self, uid: str) -> Tuple[bool, str]:
        """
        切换到指定账号
        
        Args:
            uid (str): 账号UID
            
        Returns:
            Tuple[bool, str]: (切换成功标志, 消息)
        """
        accounts = self.load_accounts()
        
        if uid not in accounts:
            return False, f"账号不存在: {uid}"
        
        account_data = accounts[uid]
        cookies = account_data.get('cookies', {})
        
        # 验证账号状态
        is_valid, user_info = self.login_handler.verify_login(cookies)
        
        if is_valid:
            self.current_cookies = cookies
            self.current_account = uid
            
            # 更新最后验证时间
            account_data['last_verify'] = time.time()
            accounts[uid] = account_data
            self.save_accounts(accounts)
            
            return True, f"已切换到账号: {account_data.get('display_name')}"
        else:
            return False, f"账号登录状态已失效: {account_data.get('display_name')}"
    
    def remove_account(self, uid: str) -> Tuple[bool, str]:
        """
        删除指定账号
        
        Args:
            uid (str): 账号UID
            
        Returns:
            Tuple[bool, str]: (删除成功标志, 消息)
        """
        accounts = self.load_accounts()
        
        if uid not in accounts:
            return False, f"账号不存在: {uid}"
        
        account_name = accounts[uid].get('display_name', uid)
        del accounts[uid]
        self.save_accounts(accounts)
        
        # 如果删除的是当前账号，清除当前状态
        if self.current_account == uid:
            self.current_account = None
            self.current_cookies = {}
        
        return True, f"账号已删除: {account_name}"
    
    def get_account_info(self, uid: str) -> Optional[Dict]:
        """
        获取指定账号信息
        
        Args:
            uid (str): 账号UID
            
        Returns:
            Optional[Dict]: 账号信息
        """
        accounts = self.load_accounts()
        return accounts.get(uid)
    
    def update_account_name(self, uid: str, new_name: str) -> Tuple[bool, str]:
        """
        更新账号显示名称
        
        Args:
            uid (str): 账号UID
            new_name (str): 新名称
            
        Returns:
            Tuple[bool, str]: (更新成功标志, 消息)
        """
        accounts = self.load_accounts()
        
        if uid not in accounts:
            return False, f"账号不存在: {uid}"
        
        old_name = accounts[uid].get('display_name', '')
        accounts[uid]['display_name'] = new_name
        self.save_accounts(accounts)
        
        return True, f"账号名称已更新: {old_name} -> {new_name}"
    
    def get_current_account(self) -> Optional[Dict]:
        """
        获取当前账号信息
        
        Returns:
            Optional[Dict]: 当前账号信息
        """
        if self.current_account:
            return self.get_account_info(self.current_account)
        return None
    
    def verify_all_accounts(self) -> Dict[str, bool]:
        """
        验证所有账号状态
        
        Returns:
            Dict[str, bool]: 账号UID对应的有效性状态
        """
        accounts = self.load_accounts()
        results = {}
        
        for uid, account_data in accounts.items():
            cookies = account_data.get('cookies', {})
            is_valid, _ = self.login_handler.verify_login(cookies)
            results[uid] = is_valid
            
            # 更新验证时间
            account_data['last_verify'] = time.time()
            accounts[uid] = account_data
        
        self.save_accounts(accounts)
        return results 