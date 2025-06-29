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
from typing import Dict, Any


class Config:
    DEFAULT_CONFIG = {
        "window": {
            "width": 800,
            "height": 600,
            "min_width": 600,
            "min_height": 400,
            "center_on_screen": True
        },
        "qrcode": {
            "size": (250, 250),
            "refresh_interval": 2000,  # 毫秒
            "timeout": 180  # 秒
        },
        "accounts": {
            "file_path": "bilibili_accounts.json",
            "auto_verify": True,
            "verify_interval": 3600  # 秒，1小时
        },
        "ui": {
            "theme": "light",
            "font_family": "微软雅黑",
            "font_size": 10,
            "show_tooltips": True
        },
        "network": {
            "timeout": 10,  # 秒
            "retry_count": 3
        }
    }
    
    def __init__(self, config_file: str = "config.json"):
        """
        初始化配置管理器
        
        Args:
            config_file (str): 配置文件路径
        """
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            Dict[str, Any]: 配置字典
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # 合并默认配置和用户配置
                return self._merge_config(self.DEFAULT_CONFIG, config)
            else:
                # 如果配置文件不存在，创建默认配置
                self.save_config(self.DEFAULT_CONFIG)
                return self.DEFAULT_CONFIG.copy()
        except Exception as e:
            print(f"加载配置文件失败: {str(e)}")
            return self.DEFAULT_CONFIG.copy()
    
    def save_config(self, config: Dict[str, Any] = None):
        """
        保存配置文件
        
        Args:
            config (Dict[str, Any]): 要保存的配置，如果为None则保存当前配置
        """
        try:
            if config is None:
                config = self.config
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置文件失败: {str(e)}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key_path (str): 配置键路径，用点分隔，如 'window.width'
            default (Any): 默认值
            
        Returns:
            Any: 配置值
        """
        try:
            keys = key_path.split('.')
            value = self.config
            
            for key in keys:
                value = value[key]
            
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path: str, value: Any):
        """
        设置配置值
        
        Args:
            key_path (str): 配置键路径，用点分隔
            value (Any): 配置值
        """
        try:
            keys = key_path.split('.')
            config = self.config
            
            # 导航到最后一个键的父级
            for key in keys[:-1]:
                if key not in config:
                    config[key] = {}
                config = config[key]
            
            # 设置最后一个键的值
            config[keys[-1]] = value
            
            # 保存配置
            self.save_config()
        except Exception as e:
            print(f"设置配置值失败: {str(e)}")
    
    def _merge_config(self, default: Dict, user: Dict) -> Dict:
        """
        合并默认配置和用户配置
        
        Args:
            default (Dict): 默认配置
            user (Dict): 用户配置
            
        Returns:
            Dict: 合并后的配置
        """
        result = default.copy()
        
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def reset_to_default(self):
        """重置为默认配置"""
        self.config = self.DEFAULT_CONFIG.copy()
        self.save_config()
    
    def get_accounts_file(self) -> str:
        """获取账号文件路径"""
        return self.get('accounts.file_path', 'bilibili_accounts.json')
    
    def get_window_config(self) -> Dict[str, Any]:
        """获取窗口配置"""
        return self.get('window', {})
    
    def get_qrcode_config(self) -> Dict[str, Any]:
        """获取二维码配置"""
        return self.get('qrcode', {}) 