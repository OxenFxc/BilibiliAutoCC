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

# 确保当前目录在Python路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from bilibili_gui.main import main
    
    if __name__ == "__main__":
        main()
        
except ImportError as e:
    print(f"导入GUI模块失败: {str(e)}")
    print("请确保bilibili_gui目录存在且包含所有必要文件")
    print("建议运行: pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"程序运行出错: {str(e)}")
    sys.exit(1) 
