#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Version: 1.0.0
Author: @OxenFxc
Copyright: https://github.com/OxenFxc
License: MIT License
Description: B站多账号扫码登录系统 - 自动私信回复功能
"""

import qrcode
import io
from PIL import Image, ImageTk
from typing import Optional
import tkinter as tk


class QRCodeHandler:
    def __init__(self):
        """初始化二维码处理器"""
        pass
    
    def generate_qrcode_image(self, qr_url: str, save_path: str = None) -> Optional[Image.Image]:
        """
        生成二维码图片
        
        Args:
            qr_url (str): 二维码内容URL
            save_path (str): 保存路径（可选）
            
        Returns:
            Optional[Image.Image]: PIL图片对象
        """
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_url)
            qr.make(fit=True)
            
            # 创建二维码图片
            img = qr.make_image(fill_color="black", back_color="white")
            
            # 如果指定了保存路径，则保存
            if save_path:
                img.save(save_path)
            
            return img
        except Exception as e:
            print(f"生成二维码失败: {str(e)}")
            return None
    
    def generate_qrcode_for_tkinter(self, qr_url: str, size: tuple = (200, 200)) -> Optional[ImageTk.PhotoImage]:
        """
        生成适用于Tkinter的二维码图片
        
        Args:
            qr_url (str): 二维码内容URL
            size (tuple): 图片尺寸 (width, height)
            
        Returns:
            Optional[ImageTk.PhotoImage]: Tkinter可用的图片对象
        """
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_url)
            qr.make(fit=True)
            
            # 创建二维码图片
            img = qr.make_image(fill_color="black", back_color="white")
            
            # 调整尺寸
            img = img.resize(size, Image.Resampling.LANCZOS)
            
            # 转换为Tkinter可用的格式
            photo = ImageTk.PhotoImage(img)
            
            return photo
        except Exception as e:
            print(f"生成Tkinter二维码失败: {str(e)}")
            return None
    
    def show_qrcode_in_terminal(self, qr_url: str):
        """
        在终端中显示二维码（文字版）
        
        Args:
            qr_url (str): 二维码内容URL
        """
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=1,
                border=1,
            )
            qr.add_data(qr_url)
            qr.make(fit=True)
            
            print("\n" + "="*50)
            print("请使用哔哩哔哩APP扫描以下二维码:")
            print("="*50)
            qr.print_ascii(invert=True)
            print("="*50 + "\n")
            
        except Exception as e:
            print(f"显示二维码失败: {str(e)}")
    
    def create_placeholder_image(self, size: tuple = (200, 200), text: str = "等待生成二维码...") -> ImageTk.PhotoImage:
        """
        创建占位符图片
        
        Args:
            size (tuple): 图片尺寸
            text (str): 显示文本
            
        Returns:
            ImageTk.PhotoImage: 占位符图片
        """
        try:
            # 创建空白图片
            img = Image.new('RGB', size, color='white')
            
            # 转换为Tkinter可用的格式
            photo = ImageTk.PhotoImage(img)
            
            return photo
        except Exception as e:
            print(f"创建占位符图片失败: {str(e)}")
            # 返回一个最小的图片
            img = Image.new('RGB', (100, 100), color='white')
            return ImageTk.PhotoImage(img) 