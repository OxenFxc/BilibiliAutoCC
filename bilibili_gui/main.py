#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Version: 1.0.0
Author: @OxenFxc
Copyright: https://github.com/OxenFxc
License: MIT License
Description: B站多账号扫码登录系统 - 自动私信回复功能
"""

import sys
import os
import tkinter as tk
from tkinter import messagebox

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from bilibili_gui.gui import MainWindow
    from bilibili_gui.utils import show_message
except ImportError as e:
    print(f"导入模块失败: {str(e)}")
    print("请确保已安装所有依赖包: pip install -r requirements.txt")
    sys.exit(1)


def check_dependencies():
    required_packages = [
        'requests',
        'qrcode',
        'Pillow'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            if package == 'Pillow':
                try:
                    __import__('PIL')
                except ImportError:
                    missing_packages.append(package)
            else:
                missing_packages.append(package)
    
    return missing_packages


def main():
    """主函数"""
    print("🔵 B站多账号扫码登录系统 - GUI版本")
    print("=" * 50)
    
    # 检查依赖
    missing_packages = check_dependencies()
    if missing_packages:
        error_msg = f"""缺少必要的依赖包：{', '.join(missing_packages)}

请运行以下命令安装：
pip install {' '.join(missing_packages)}

或者安装所有依赖：
pip install -r requirements.txt"""
        
        print(f"❌ {error_msg}")
        
        # 如果Tkinter可用，显示图形错误对话框
        try:
            root = tk.Tk()
            root.withdraw()  # 隐藏主窗口
            messagebox.showerror("依赖包缺失", error_msg)
            root.destroy()
        except:
            pass
        
        return
    
    try:
        # 创建并运行主窗口
        app = MainWindow()
        app.run()
        
    except KeyboardInterrupt:
        print("\n👋 用户中断程序")
    except Exception as e:
        error_msg = f"程序运行出错: {str(e)}"
        print(f"❌ {error_msg}")
        
        # 显示错误对话框
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("程序错误", error_msg)
            root.destroy()
        except:
            pass


if __name__ == "__main__":
    main() 