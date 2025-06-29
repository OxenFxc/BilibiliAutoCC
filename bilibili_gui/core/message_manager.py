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
import time
import random
import requests
import threading
import re
import uuid
import difflib
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from ..utils.database import AutoReplyDatabase


class MessageManager:
    def __init__(self, login_handler, account_uid: str):
        """
        初始化私信管理器
        
        Args:
            login_handler: 登录处理器
            account_uid: 账号UID
        """
        self.login_handler = login_handler
        self.account_uid = account_uid
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://message.bilibili.com/'
        })
        
        # 自动回复相关
        self.auto_reply_enabled = False
        self.listening_thread = None
        self.stop_listening = False
        
        # 私信缓存
        self.sessions_cache = {}
        self.messages_cache = {}
        
        # 数据库管理器
        self.db = AutoReplyDatabase()
        
        # 加载账号配置
        self.load_account_config()
        
        # 回复统计（用于每日限制）
        self.today_reply_count = 0
        self._update_today_count()
        
        # 消息处理相关
        self.processed_messages = set()  # 已处理的消息ID
        self.replied_messages = set()    # 已回复的消息ID（更强的防重复机制）
        self.my_recent_replies = set()   # 最近发送的回复内容，用于避免回复自己的消息
        self.message_lock = threading.Lock()  # 线程锁确保线程安全
        
        # 清理旧的处理记录（程序启动时）
        self._cleanup_old_records()
        
        # 日志管理
        self.log_count = 0
        self.last_log_clear = time.time()
        
        # GUI日志回调
        self.gui_log_callback = None
        
    def load_account_config(self):
        """加载账号配置"""
        config = self.db.get_account_config(self.account_uid)
        if config:
            self.reply_delay_min = config.get('reply_delay_min', 2)
            self.reply_delay_max = config.get('reply_delay_max', 8)
            self.daily_limit = config.get('daily_limit', 100)
            self.scan_interval = config.get('scan_interval', 8)
            self.account_config = config.get('config_data', {})
        else:
            # 默认配置
            self.reply_delay_min = 2
            self.reply_delay_max = 8
            self.daily_limit = 100
            self.scan_interval = 8
            self.account_config = {}
    
    def save_account_config(self, auto_reply_enabled: bool = None):
        """保存账号配置"""
        if auto_reply_enabled is not None:
            self.auto_reply_enabled = auto_reply_enabled
        
        self.db.save_account_config(
            account_uid=self.account_uid,
            auto_reply_enabled=self.auto_reply_enabled,
            reply_delay_min=self.reply_delay_min,
            reply_delay_max=self.reply_delay_max,
            daily_limit=self.daily_limit,
            scan_interval=self.scan_interval,
            config_data=self.account_config
        )
    
    def _update_today_count(self):
        """更新今日回复数量"""
        stats = self.db.get_reply_stats(self.account_uid)
        if stats:
            # 检查是否是新的一天
            today = datetime.now().date().isoformat()
            if stats.get('last_update_date') == today:
                self.today_reply_count = stats.get('today_replies', 0)
            else:
                self.today_reply_count = 0
        else:
            self.today_reply_count = 0
    
    def set_cookies(self, cookies: Dict):
        """设置请求Cookie"""
        self.session.cookies.clear()
        for key, value in cookies.items():
            self.session.cookies.set(key, str(value))
    
    def get_unread_count(self) -> Tuple[bool, Dict]:
        """
        获取未读私信数
        
        Returns:
            Tuple[bool, Dict]: (成功标志, 未读消息统计)
        """
        try:
            url = "https://api.vc.bilibili.com/session_svr/v1/session_svr/single_unread"
            params = {
                'unread_type': 0,
                'show_unfollow_list': 1,
                'show_dustbin': 1,
                'build': 0,
                'mobi_app': 'web'
            }
            
            response = self.session.get(url, params=params)
            data = response.json()
            
            if data.get('code') == 0:
                return True, data.get('data', {})
            else:
                return False, f"获取未读私信数失败: {data.get('message', '未知错误')}"
                
        except Exception as e:
            return False, f"获取未读私信数异常: {str(e)}"
    
    def get_sessions(self, session_type: int = 4, size: int = 20) -> Tuple[bool, List]:
        """
        获取会话列表
        
        Args:
            session_type (int): 会话类型 1:用户与系统 2:未关注人 3:粉丝团 4:所有 5:被拦截
            size (int): 返回的会话数量
            
        Returns:
            Tuple[bool, List]: (成功标志, 会话列表)
        """
        try:
            url = "https://api.vc.bilibili.com/session_svr/v1/session_svr/get_sessions"
            params = {
                'session_type': session_type,
                'group_fold': 0,
                'unfollow_fold': 0,
                'sort_rule': 2,
                'size': size,
                'build': 0,
                'mobi_app': 'web'
            }
            
            response = self.session.get(url, params=params)
            data = response.json()
            
            if data.get('code') == 0:
                sessions = data.get('data', {}).get('session_list', [])
                # 缓存会话列表
                self.sessions_cache = {session['talker_id']: session for session in sessions if sessions}
                return True, sessions
            else:
                return False, f"获取会话列表失败: {data.get('message', '未知错误')}"
                
        except Exception as e:
            return False, f"获取会话列表异常: {str(e)}"
    
    def get_session_messages(self, talker_id: int, session_type: int = 1, 
                           size: int = 20, begin_seqno: int = None) -> Tuple[bool, Dict]:
        """
        获取会话消息
        
        Args:
            talker_id (int): 聊天对象ID
            session_type (int): 会话类型 1:用户 2:粉丝团
            size (int): 消息数量
            begin_seqno (int): 开始序列号
            
        Returns:
            Tuple[bool, Dict]: (成功标志, 消息数据)
        """
        try:
            url = "https://api.vc.bilibili.com/svr_sync/v1/svr_sync/fetch_session_msgs"
            params = {
                'talker_id': talker_id,
                'session_type': session_type,
                'size': size,
                'sender_device_id': 1,
                'build': 0,
                'mobi_app': 'web'
            }
            
            if begin_seqno:
                params['begin_seqno'] = begin_seqno
            
            response = self.session.get(url, params=params)
            data = response.json()
            
            if data.get('code') == 0:
                # 缓存消息
                cache_key = f"{talker_id}_{session_type}"
                self.messages_cache[cache_key] = data.get('data', {})
                return True, data.get('data', {})
            else:
                return False, f"获取消息失败: {data.get('message', '未知错误')}"
                
        except Exception as e:
            return False, f"获取消息异常: {str(e)}"
    
    def send_message(self, receiver_id: int, content: str, 
                    receiver_type: int = 1, msg_type: int = 1) -> Tuple[bool, Any]:
        """
        发送私信
        
        Args:
            receiver_id (int): 接收者ID
            content (str): 消息内容
            receiver_type (int): 接收者类型 1:用户 2:粉丝团
            msg_type (int): 消息类型 1:文本 2:图片 5:撤回
            
        Returns:
            Tuple[bool, Any]: (成功标志, 返回数据或错误信息)
        """
        try:
            # 获取当前登录用户的mid
            cookies = dict(self.session.cookies)
            sender_uid = cookies.get('DedeUserID')
            if not sender_uid:
                return False, "未找到发送者UID"
            
            # 获取CSRF token
            csrf_token = cookies.get('bili_jct')
            if not csrf_token:
                return False, "未找到CSRF token"
            
            url = "https://api.vc.bilibili.com/web_im/v1/web_im/send_msg"
            
            # 生成设备ID (UUID v4)
            dev_id = str(uuid.uuid4()).upper()
            
            # 构造消息内容
            if msg_type == 1:  # 文本消息
                message_content = json.dumps({"content": content}, ensure_ascii=False)
            else:
                message_content = content
            
            data = {
                'msg[sender_uid]': sender_uid,
                'msg[receiver_id]': receiver_id,
                'msg[receiver_type]': receiver_type,
                'msg[msg_type]': msg_type,
                'msg[msg_status]': 0,
                'msg[content]': message_content,
                'msg[timestamp]': int(time.time()),
                'msg[new_face_version]': 0,
                'msg[dev_id]': dev_id,
                'csrf': csrf_token,
                'csrf_token': csrf_token
            }
            
            response = self.session.post(url, data=data)
            result = response.json()
            
            if result.get('code') == 0:
                return True, result.get('data')
            else:
                return False, f"发送消息失败: {result.get('message', '未知错误')}"
                
        except Exception as e:
            return False, f"发送消息异常: {str(e)}"
    
    def match_auto_reply(self, message_text):
        """匹配自动回复规则"""
        try:
            if not message_text or not message_text.strip():
                self._log_with_management(f"❌ 账号 {self.account_uid} 消息为空，跳过匹配")
                return None
                
            # 获取启用的规则，按优先级排序
            rules = self.get_auto_reply_rules(enabled_only=True)
            self._log_with_management(f"🔍 账号 {self.account_uid} 准备匹配消息: 【{message_text}】")
            self._log_with_management(f"📊 账号 {self.account_uid} 可用规则数量: {len(rules)}")
            
            if not rules:
                self._log_with_management(f"⚠️ 账号 {self.account_uid} 没有启用的自动回复规则！")
                return None
            
            # 按优先级排序（优先级越高，越早匹配）
            rules.sort(key=lambda x: x.get('priority', 0), reverse=True)
            self._log_with_management(f"📝 账号 {self.account_uid} 开始逐个匹配 {len(rules)} 条规则:")
            
            for i, rule in enumerate(rules, 1):
                keyword = rule.get('keyword', '').strip()
                if not keyword:
                    continue
                    
                match_type = rule.get('match_type', 'contains')
                case_sensitive = rule.get('case_sensitive', False)
                priority = rule.get('priority', 0)
                
                # 处理大小写敏感
                if case_sensitive:
                    text_to_match = message_text
                    keyword_to_match = keyword
                else:
                    text_to_match = message_text.lower()
                    keyword_to_match = keyword.lower()
                
                matched = False
                self._log_with_management(f"  🔍 规则{i}: 关键词=【{keyword}】, 类型={match_type}, 优先级={priority}, 大小写敏感={case_sensitive}")
                
                try:
                    if match_type == 'exact':
                        matched = text_to_match.strip() == keyword_to_match.strip()
                    elif match_type == 'contains':
                        matched = keyword_to_match in text_to_match
                    elif match_type == 'startswith':
                        matched = text_to_match.startswith(keyword_to_match)
                    elif match_type == 'endswith':
                        matched = text_to_match.endswith(keyword_to_match)
                    elif match_type == 'regex':
                        import re
                        flags = 0 if case_sensitive else re.IGNORECASE
                        matched = bool(re.search(keyword, message_text, flags))
                    elif match_type == 'word_boundary':
                        import re
                        pattern = r'\b' + re.escape(keyword_to_match) + r'\b'
                        flags = 0 if case_sensitive else re.IGNORECASE
                        matched = bool(re.search(pattern, text_to_match, flags))
                    elif match_type == 'fuzzy':
                        # 简单的模糊匹配：允许少量字符差异
                        from difflib import SequenceMatcher
                        similarity = SequenceMatcher(None, text_to_match, keyword_to_match).ratio()
                        matched = similarity >= 0.8
                        self._log_with_management(f"    模糊匹配相似度: {similarity:.2f}")
                    elif match_type == 'fuzzy_contains':
                        # 模糊包含匹配
                        if len(keyword_to_match) <= 3:
                            # 短关键词直接包含匹配
                            matched = keyword_to_match in text_to_match
                        else:
                            # 长关键词允许部分匹配
                            words = keyword_to_match.split()
                            matched = any(word in text_to_match for word in words if len(word) > 1)
                    
                    result_text = "✅ 匹配成功" if matched else "❌ 匹配失败"
                    self._log_with_management(f"    {result_text}")
                    
                    if matched:
                        reply_content = rule.get('reply_content', '')
                        self._log_with_management(f"🎯 账号 {self.account_uid} 规则匹配成功！回复内容: 【{reply_content[:30]}{'...' if len(reply_content) > 30 else ''}】")
                        return {
                            'keyword': keyword,
                            'keyword_matched': keyword,
                            'reply_content': reply_content,
                            'match_type': match_type,
                            'rule_id': rule.get('id'),
                            'priority': priority
                        }
                        
                except Exception as e:
                    self._log_with_management(f"    ❌ 匹配出错: {str(e)}")
                    continue
            
            return None
            
        except Exception as e:
            self._log_with_management(f"❌ 账号 {self.account_uid} match_auto_reply出错: {str(e)}")
            return None
    
    def add_auto_reply_rule(self, keyword: str, reply_content: str, 
                          match_type: str = "contains", case_sensitive: bool = False,
                          enabled: bool = True, priority: int = 0, 
                          description: str = "") -> int:
        """
        添加自动回复规则
        
        Args:
            keyword (str): 关键词
            reply_content (str): 回复内容
            match_type (str): 匹配类型
            case_sensitive (bool): 是否区分大小写
            enabled (bool): 是否启用
            priority (int): 优先级
            description (str): 描述
            
        Returns:
            int: 规则ID
        """
        return self.db.save_auto_reply_rule(
            account_uid=self.account_uid,
            keyword=keyword,
            reply_content=reply_content,
            match_type=match_type,
            case_sensitive=case_sensitive,
            enabled=enabled,
            priority=priority,
            description=description
        )
    
    def update_auto_reply_rule(self, rule_id: int, keyword: str, reply_content: str,
                             match_type: str = "contains", case_sensitive: bool = False,
                             enabled: bool = True, priority: int = 0,
                             description: str = "") -> bool:
        """
        更新自动回复规则
        
        Args:
            rule_id (int): 规则ID
            keyword (str): 关键词
            reply_content (str): 回复内容
            match_type (str): 匹配类型
            case_sensitive (bool): 是否区分大小写
            enabled (bool): 是否启用
            priority (int): 优先级
            description (str): 描述
            
        Returns:
            bool: 是否成功
        """
        result = self.db.save_auto_reply_rule(
            account_uid=self.account_uid,
            keyword=keyword,
            reply_content=reply_content,
            match_type=match_type,
            case_sensitive=case_sensitive,
            enabled=enabled,
            priority=priority,
            description=description,
            rule_id=rule_id
        )
        return result > 0
    
    def debug_get_messages(self, talker_id, session_type=1, size=20):
        """调试消息获取API - 输出完整的原始数据"""
        print(f"\n🔧 调试消息获取API")
        print(f"目标会话ID: {talker_id}")
        print(f"会话类型: {session_type}")
        print(f"获取数量: {size}")
        print(f"当前账号UID: {self.account_uid}")
        
        # 检查cookies
        cookies_dict = dict(self.session.cookies)
        print(f"关键Cookies:")
        print(f"  DedeUserID: {cookies_dict.get('DedeUserID', '未设置')}")
        print(f"  bili_jct: {'已设置' if cookies_dict.get('bili_jct') else '未设置'}")
        print(f"  总共cookies数量: {len(cookies_dict)}")
        
        # 准备请求参数
        url = 'https://api.vc.bilibili.com/svr_sync/v1/svr_sync/fetch_session_msgs'
        params = {
            'talker_id': talker_id,
            'session_type': session_type,
            'size': size,
            'sender_device_id': 1,
            'build': 0,
            'mobi_app': 'web'
        }
        
        print(f"\n🌐 API请求信息:")
        print(f"URL: {url}")
        print(f"请求参数: {params}")
        
        try:
            # 发送请求
            response = self.session.get(url, params=params)
            print(f"\n📡 响应状态:")
            print(f"HTTP状态码: {response.status_code}")
            print(f"响应头: {dict(response.headers)}")
            
            # 解析响应
            try:
                data = response.json()
                print(f"\n📄 原始JSON响应:")
                import json
                print(json.dumps(data, ensure_ascii=False, indent=2))
                
                # 分析响应结构
                print(f"\n🔍 响应结构分析:")
                print(f"code: {data.get('code', '未知')}")
                print(f"message: {data.get('message', '未知')}")
                
                if 'data' in data:
                    data_section = data['data']
                    print(f"data字段类型: {type(data_section)}")
                    
                    if isinstance(data_section, dict):
                        print(f"data字段包含的键: {list(data_section.keys())}")
                        
                        if 'messages' in data_section:
                            messages = data_section['messages']
                            print(f"messages字段类型: {type(messages)}")
                            print(f"消息数量: {len(messages) if isinstance(messages, list) else '不是列表'}")
                            
                            if isinstance(messages, list) and len(messages) > 0:
                                print(f"\n📨 消息详细分析 (前3条):")
                                for i, msg in enumerate(messages[:3]):
                                    print(f"  消息 {i+1}:")
                                    print(f"    完整消息对象: {msg}")
                                    print(f"    sender_uid: {msg.get('sender_uid', '未知')}")
                                    print(f"    receiver_id: {msg.get('receiver_id', '未知')}")
                                    print(f"    msg_type: {msg.get('msg_type', '未知')}")
                                    print(f"    timestamp: {msg.get('timestamp', '未知')}")
                                    print(f"    content: {msg.get('content', '未知')}")
                                    print(f"    msg_key: {msg.get('msg_key', '未知')}")
                                    print(f"    所有字段: {list(msg.keys()) if isinstance(msg, dict) else '不是字典'}")
                                    
                                    # 解析消息内容
                                    if 'content' in msg:
                                        try:
                                            content_json = json.loads(msg['content'])
                                            print(f"    解析后的内容: {content_json}")
                                        except:
                                            print(f"    内容解析失败，原始内容: {msg['content']}")
                                    print()
                            else:
                                print("    无消息或消息列表为空")
                        else:
                            print("    data中没有messages字段")
                    else:
                        print(f"    data不是字典类型: {data_section}")
                else:
                    print("    响应中没有data字段")
                    
            except json.JSONDecodeError as e:
                print(f"❌ JSON解析失败: {e}")
                print(f"原始响应文本: {response.text}")
                
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            
        return False, "调试完成"
    
    def delete_auto_reply_rule(self, rule_id: int) -> bool:
        """删除自动回复规则"""
        return self.db.delete_auto_reply_rule(self.account_uid, rule_id)
    
    def toggle_rule_status(self, rule_id: int) -> bool:
        """切换规则启用状态"""
        return self.db.toggle_rule_status(self.account_uid, rule_id)
    
    def get_auto_reply_rules(self, enabled_only: bool = False) -> List[Dict]:
        """获取自动回复规则"""
        return self.db.get_auto_reply_rules(self.account_uid, enabled_only)
    
    def start_auto_reply_listener(self):
        """启动自动回复监听"""
        if self.listening_thread and self.listening_thread.is_alive():
            return
            
        self.auto_reply_enabled = True
        self.stop_listening = False
        self.save_account_config()
        
        self.listening_thread = threading.Thread(
            target=self._auto_reply_worker, 
            daemon=True,
            name=f"AutoReply-{self.account_uid}"
        )
        self.listening_thread.start()
        print(f"✅ 账号 {self.account_uid} 自动回复监听已启动")
    
    def stop_auto_reply_listener(self):
        """停止自动回复监听"""
        self.auto_reply_enabled = False
        self.stop_listening = True
        self.save_account_config()
        
        if self.listening_thread:
            self.listening_thread.join(timeout=5)
        
        print(f"🔴 账号 {self.account_uid} 自动回复监听已停止")
    
    def _auto_reply_worker(self):
        """自动回复工作线程"""
        startup_time = time.time()
        self._log_with_management(f"🚀 账号 {self.account_uid} 自动回复系统启动")
        self._log_with_management(f"⏰ 启动时间: {time.strftime('%H:%M:%S', time.localtime(startup_time))}")
        
        while not self.stop_listening and self.auto_reply_enabled:
            try:
                # 获取会话列表
                success, sessions = self.get_sessions()
                if not success:
                    self._log_with_management(f"❌ 账号 {self.account_uid} 获取会话列表失败: {sessions}")
                    time.sleep(10)  # 失败时等待更长时间
                    continue
                
                if not sessions:
                    self._log_with_management(f"📋 账号 {self.account_uid} 无会话记录")
                    time.sleep(8)
                    continue
                
                current_time = time.time()
                self._log_with_management(f"\n🔍 账号 {self.account_uid} [{time.strftime('%H:%M:%S', time.localtime(current_time))}] 开始扫描消息... 总会话数: {len(sessions)}")
                
                # 显示会话概览（前10个）
                self._log_with_management(f"📋 账号 {self.account_uid} 会话列表概览:")
                for i, session in enumerate(sessions[:10], 1):
                    session_name = self.format_session_name(session)
                    last_msg = session.get('last_msg', {})
                    msg_timestamp = last_msg.get('timestamp', 0)
                    unread_count = session.get('unread_count', 0)
                    
                    if msg_timestamp > 0:
                        time_str = time.strftime('%H:%M:%S', time.localtime(msg_timestamp))
                        time_diff = current_time - msg_timestamp
                        if time_diff <= 30:
                            time_status = "🟢 最近"
                        elif time_diff <= 300:
                            time_status = "🟡 较早"
                        else:
                            time_status = "⚪ 较早"
                    else:
                        time_str = "无"
                        time_status = "⚪ 无时间"
                    
                    self._log_with_management(f"    {i:2d}. {time_status} [{session_name}] 未读:{unread_count} 最后:{time_str}")
                
                # 简化的扫描逻辑：检查最近活跃的会话（最多前20个）
                processed_count = 0
                scanned_count = 0
                max_scan = min(20, len(sessions))
                
                for i, session in enumerate(sessions[:max_scan]):
                    if self.stop_listening or not self.auto_reply_enabled:
                        break
                    
                    talker_id = session.get('talker_id')
                    session_type = session.get('session_type', 1)
                    session_name = self.format_session_name(session)
                    
                    if not talker_id:
                        continue
                    
                    scanned_count += 1
                    self._log_with_management(f"🔎 扫描 [{scanned_count}/{max_scan}] {session_name} (最后消息:{time.strftime('%H:%M:%S', time.localtime(session.get('last_msg', {}).get('timestamp', 0)))})")
                    
                    # 获取消息详情
                    success, msg_data = self.get_session_messages(talker_id, session_type, size=10)
                    if not success:
                        self._log_with_management(f"   ❌ 获取消息失败: {msg_data}")
                        continue
                    
                    messages = msg_data.get('messages', [])
                    if not messages:
                        self._log_with_management(f"   ⚪ 无消息记录")
                        continue
                    
                    # 显示最新的几条消息（便于调试）
                    for j, msg in enumerate(messages[:3]):
                        sender_uid = msg.get('sender_uid')
                        msg_type = msg.get('msg_type', 0)
                        msg_timestamp = msg.get('timestamp', 0)
                        content_raw = msg.get('content', '')
                        
                        # 解析消息内容
                        try:
                            if msg_type == 1:  # 文本消息
                                content_json = json.loads(content_raw)
                                message_text = content_json.get('content', '')
                            else:
                                message_text = f"[类型{msg_type}消息]"
                        except:
                            message_text = content_raw[:50] if content_raw else "[空消息]"
                        
                        sender_status = "我" if str(sender_uid) == str(self.account_uid) else f"对方({sender_uid})"
                        time_str = time.strftime('%H:%M:%S', time.localtime(msg_timestamp))
                        
                        self._log_with_management(f"📨 [{j+1}] {time_str} {sender_status}: {message_text[:30]}{'...' if len(message_text) > 30 else ''}")
                    
                    # 处理消息 - 简化逻辑
                    for msg in messages:
                        if self.stop_listening or not self.auto_reply_enabled:
                            break
                        
                        try:
                            sender_uid = msg.get('sender_uid')
                            msg_type = msg.get('msg_type', 0)
                            msg_timestamp = msg.get('timestamp', 0)
                            
                            # 调试：显示每条消息的处理步骤
                            time_str = time.strftime('%H:%M:%S', time.localtime(msg_timestamp))
                            sender_status = "我" if str(sender_uid) == str(self.account_uid) else f"对方({sender_uid})"
                            self._log_with_management(f"   🔍 处理消息: {time_str} {sender_status} 类型:{msg_type}")
                            
                            # 跳过自己发送的消息
                            if str(sender_uid) == str(self.account_uid):
                                self._log_with_management(f"   ⏭️ 跳过自己的消息")
                                continue
                            
                            # 只处理文本消息
                            if msg_type != 1:
                                self._log_with_management(f"   ⏭️ 跳过非文本消息 (类型:{msg_type})")
                                continue
                            
                            # 生成消息唯一ID
                            msg_id = self._generate_message_id(talker_id, msg)
                            self._log_with_management(f"   🆔 消息ID: {msg_id}")
                            
                                                        # 检查是否已处理过此消息
                            with self.message_lock:
                                if msg_id in self.processed_messages:
                                    self._log_with_management(f"   ⏭️ 消息已处理过，跳过")
                                    continue
                                
                                # 扩大时间检查范围：处理24小时内的消息
                                time_diff = current_time - msg_timestamp
                                self._log_with_management(f"   ⏰ 时间差: {time_diff:.0f}秒 ({time_diff/3600:.1f}小时)")
                                if time_diff > 86400:  # 超过24小时的消息不处理
                                    self._log_with_management(f"   ⏭️ 消息超过24小时，跳过")
                                    continue
                                
                                # 标记消息已处理
                                self.processed_messages.add(msg_id)
                                self._log_with_management(f"   ✅ 消息标记为已处理")
                                
                                # 清理旧记录
                                if len(self.processed_messages) > 1000:
                                    old_messages = list(self.processed_messages)[:500]
                                    for old_msg in old_messages:
                                        self.processed_messages.discard(old_msg)
                            
                            # 解析消息内容
                            content_raw = msg.get('content', '')
                            self._log_with_management(f"   📝 原始内容: {content_raw[:50]}{'...' if len(content_raw) > 50 else ''}")
                            if not content_raw:
                                self._log_with_management(f"   ⏭️ 消息内容为空，跳过")
                                continue
                            
                            # 尝试解析JSON格式的消息内容
                            try:
                                content_json = json.loads(content_raw)
                                message_text = content_json.get('content', '')
                                self._log_with_management(f"   📄 解析后内容: {message_text}")
                            except:
                                # 如果不是JSON格式，直接使用原始内容
                                message_text = content_raw
                                self._log_with_management(f"   📄 使用原始内容: {message_text}")
                            
                            if not message_text or not message_text.strip():
                                self._log_with_management(f"   ⏭️ 解析后内容为空，跳过")
                                continue
                            
                                                        # 记录收到新消息
                            self._log_with_management(f"📨 账号 {self.account_uid} 收到新消息 [{session_name}]: {message_text[:50]}")
                            
                            # 匹配自动回复规则
                            reply_result = self.match_auto_reply(message_text.strip())
                            if reply_result:
                                reply_content = reply_result.get('reply_content', '')
                                keyword_matched = reply_result.get('keyword', '')
                                self._log_with_management(f"🎯 账号 {self.account_uid} 匹配到关键词【{keyword_matched}】，准备回复")
                                
                                # 检查每日限制
                                today_count = self.get_today_reply_count()
                                if self.daily_limit > 0 and today_count >= self.daily_limit:
                                    self._log_with_management(f"⏸️ 账号 {self.account_uid} 已达每日回复限制 ({today_count}/{self.daily_limit})")
                                    continue
                                
                                # 添加随机延迟
                                delay = random.randint(self.min_delay, self.max_delay)
                                self._log_with_management(f"⏳ 账号 {self.account_uid} 等待 {delay} 秒后回复...")
                                time.sleep(delay)
                                
                                # 发送回复
                                success, response = self.send_message(
                                    receiver_id=talker_id,
                                    content=reply_content,
                                    receiver_type=session_type
                                )
                                
                                if success:
                                    # 记录成功的回复
                                    with self.message_lock:
                                        self.replied_messages.add(msg_id)
                                    
                                    self.db.add_reply_log(
                                        account_uid=self.account_uid,
                                        receiver_id=talker_id,
                                        receiver_name=session_name,
                                        original_message=message_text,
                                        reply_content=reply_content,
                                        success=True
                                    )
                                    
                                    self._update_today_count()
                                    processed_count += 1
                                    
                                    self._log_with_management(f"✅ 账号 {self.account_uid} 回复成功 -> [{session_name}]: {reply_content}")
                                else:
                                    self.db.add_reply_log(
                                        account_uid=self.account_uid,
                                        receiver_id=talker_id,
                                        receiver_name=session_name,
                                        original_message=message_text,
                                        reply_content=reply_content,
                                        success=False,
                                        error_message=str(response)
                                    )
                                    
                                    self._log_with_management(f"❌ 账号 {self.account_uid} 回复失败 -> [{session_name}]: {response}")
                            else:
                                self._log_with_management(f"⚪ 账号 {self.account_uid} 消息【{message_text[:30]}{'...' if len(message_text) > 30 else ''}】未匹配到任何规则")
                            
                        except Exception as e:
                            self._log_with_management(f"❌ 账号 {self.account_uid} 处理消息时出错: {str(e)}")
                            import traceback
                            traceback.print_exc()
                
                # 输出扫描结果
                self._log_with_management(f"📊 账号 {self.account_uid} 扫描完成: 检查了{scanned_count}个最近活跃会话，处理了{processed_count}条新消息")
                
                # 等待下次扫描
                self._log_with_management(f"💤 账号 {self.account_uid} 等待 {self.scan_interval} 秒后进行下次扫描...")
                time.sleep(self.scan_interval)
                
            except Exception as e:
                self._log_with_management(f"❌ 账号 {self.account_uid} 扫描过程中出错: {str(e)}")
                import traceback
                traceback.print_exc()
                time.sleep(10)  # 出错时等待10秒
        
        self._log_with_management(f"🛑 账号 {self.account_uid} 自动回复系统已停止")
    
    def parse_message_content(self, content: str, msg_type: int) -> str:
        """
        解析消息内容
        
        Args:
            content (str): 原始消息内容
            msg_type (int): 消息类型
            
        Returns:
            str: 解析后的可读内容
        """
        try:
            if msg_type == 1:  # 文本消息
                content_json = json.loads(content)
                return content_json.get('content', content)
            elif msg_type == 2:  # 图片消息
                content_json = json.loads(content)
                return f"[图片] {content_json.get('url', '')}"
            elif msg_type == 10:  # 通知消息
                content_json = json.loads(content)
                return content_json.get('text', content_json.get('title', '通知消息'))
            elif msg_type == 11:  # 视频推送
                content_json = json.loads(content)
                return f"[视频推送] {content_json.get('title', '')}"
            elif msg_type == 18:  # 系统消息（如发送限制提示）
                try:
                    content_json = json.loads(content)
                    if isinstance(content_json.get('content'), list):
                        # 处理复杂的系统消息格式
                        text_parts = []
                        for item in content_json['content']:
                            if isinstance(item, dict) and 'text' in item:
                                text_parts.append(item['text'])
                        return f"[系统消息] {' '.join(text_parts)}"
                    else:
                        return f"[系统消息] {content_json.get('content', content)}"
                except:
                    return f"[系统消息] {content}"
            else:
                return f"[消息类型{msg_type}] {content}"
        except:
            return content
    
    def get_session_info(self, talker_id: int) -> Optional[Dict]:
        """获取会话信息"""
        return self.sessions_cache.get(talker_id)
    
    def format_session_name(self, session: Dict) -> str:
        """格式化会话名称"""
        if session.get('session_type') == 2:  # 粉丝团
            return f"[粉丝团] {session.get('group_name', '未知')}"
        else:
            return session.get('uname', f"用户{session.get('talker_id', '')}")
    
    def get_reply_stats(self) -> Optional[Dict]:
        """获取回复统计"""
        return self.db.get_reply_stats(self.account_uid)
    
    def get_reply_logs(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """获取回复日志"""
        return self.db.get_reply_logs(self.account_uid, limit, offset)
    
    def get_keyword_stats(self, limit: int = 10) -> List[Dict]:
        """获取关键词统计"""
        return self.db.get_keyword_stats(self.account_uid, limit)
    
    def get_daily_stats(self, days: int = 7) -> List[Dict]:
        """获取每日统计"""
        return self.db.get_daily_stats(self.account_uid, days)
    
    def _cleanup_old_records(self):
        """清理旧的处理记录（程序启动时）"""
        # 清空处理记录，避免影响新的检测
        with self.message_lock:
            self.processed_messages.clear()
            self.replied_messages.clear()
            self.my_recent_replies.clear()
        print(f"🧹 账号 {self.account_uid} 清理了旧的消息处理记录")
    
    def _clear_console_logs(self):
        """清理控制台日志"""
        try:
            import os
            # Windows系统清屏
            if os.name == 'nt':
                os.system('cls')
            # Unix/Linux系统清屏
            else:
                os.system('clear')
            print(f"🧹 控制台日志已清理 - {time.strftime('%H:%M:%S')}")
        except:
            pass
    
    def _should_clear_logs(self):
        """检查是否需要清理日志"""
        current_time = time.time()
        # 每10分钟清理一次日志
        if current_time - self.last_log_clear > 600:
            self.last_log_clear = current_time
            return True
        return False
    
    def _log_with_management(self, message):
        """带日志管理的输出"""
        # 检查是否需要清理日志
        if self._should_clear_logs():
            self._clear_console_logs()
        
        # 控制台输出
        print(message)
        self.log_count += 1
        
        # GUI日志输出
        if self.gui_log_callback:
            # 根据消息内容判断日志类型
            log_type = "info"
            if "✅" in message or "成功" in message:
                log_type = "success"
            elif "❌" in message or "失败" in message or "错误" in message:
                log_type = "error"
            elif "⚠️" in message or "警告" in message:
                log_type = "warning"
            elif "🔍" in message or "🔎" in message or "扫描" in message or "检测" in message:
                log_type = "scan"
            elif "📩" in message or "📨" in message or "消息" in message:
                log_type = "message"
            
            try:
                self.gui_log_callback(message, log_type)
            except:
                pass  # 忽略GUI回调错误
    
    def _generate_message_id(self, talker_id, msg):
        """生成消息唯一ID"""
        sender_uid = msg.get('sender_uid', '')
        timestamp = msg.get('timestamp', 0)
        msg_key = msg.get('msg_key', '')
        msg_seqno = msg.get('msg_seqno', '')  # 添加序列号
        content = msg.get('content', '')
        
        # 使用多个字段确保唯一性，包括消息内容的哈希
        import hashlib
        content_hash = hashlib.md5(str(content).encode()).hexdigest()[:8]
        
        # 使用更多字段确保唯一性
        return f"{talker_id}_{sender_uid}_{timestamp}_{msg_key}_{msg_seqno}_{content_hash}"
    
    def get_today_reply_count(self):
        """获取今日回复数量"""
        return self.today_reply_count

    def set_gui_log_callback(self, callback):
        """设置GUI日志回调函数"""
        self.gui_log_callback = callback

    def debug_message_api(self, talker_id=3546864267823928):
        """调试消息API"""
        self._log_with_management(f"🔧 开始调试消息API - 目标用户: {talker_id}")
        
        # 1. 测试会话列表API
        self._log_with_management("📋 步骤1：测试会话列表API")
        success, sessions = self.get_sessions()
        if success:
            self._log_with_management(f"✅ 会话列表获取成功，共 {len(sessions)} 个会话")
            
            # 查找目标用户
            target_session = None
            for session in sessions:
                if session.get('talker_id') == talker_id:
                    target_session = session
                    break
            
            if target_session:
                last_msg = target_session.get('last_msg', {})
                msg_timestamp = last_msg.get('timestamp', 0)
                time_str = time.strftime('%H:%M:%S', time.localtime(msg_timestamp)) if msg_timestamp else "无"
                self._log_with_management(f"🎯 找到目标会话: 最后消息时间 {time_str}")
                self._log_with_management(f"📄 会话详情: {target_session}")
            else:
                self._log_with_management(f"❌ 未找到目标用户 {talker_id} 的会话")
                return
        else:
            self._log_with_management(f"❌ 会话列表获取失败: {sessions}")
            return
        
        # 2. 测试消息详情API - 多种参数组合
        test_params = [
            {"session_type": 1, "size": 20},
            {"session_type": 1, "size": 10},
            {"session_type": 2, "size": 20},
            {"session_type": 1, "size": 50},
        ]
        
        for i, params in enumerate(test_params, 1):
            self._log_with_management(f"📨 步骤2.{i}：测试消息详情API - 参数: {params}")
            
            try:
                url = "https://api.vc.bilibili.com/svr_sync/v1/svr_sync/fetch_session_msgs"
                request_params = {
                    'talker_id': talker_id,
                    'session_type': params['session_type'],
                    'size': params['size'],
                    'sender_device_id': 1,
                    'build': 0,
                    'mobi_app': 'web'
                }
                
                self._log_with_management(f"🌐 请求URL: {url}")
                self._log_with_management(f"📝 请求参数: {request_params}")
                
                response = self.session.get(url, params=request_params)
                self._log_with_management(f"📊 响应状态码: {response.status_code}")
                self._log_with_management(f"📋 响应头: {dict(response.headers)}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        self._log_with_management(f"✅ JSON解析成功")
                        self._log_with_management(f"📄 响应数据结构: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                        
                        if isinstance(data, dict):
                            code = data.get('code', 'N/A')
                            message = data.get('message', 'N/A')
                            self._log_with_management(f"🔢 响应码: {code}, 消息: {message}")
                            
                            if code == 0:  # 成功
                                msg_data = data.get('data', {})
                                if isinstance(msg_data, dict):
                                    messages = msg_data.get('messages', [])
                                    self._log_with_management(f"📨 获取到 {len(messages)} 条消息")
                                    
                                    if messages:
                                        # 统计消息分布
                                        my_count = 0
                                        other_count = 0
                                        other_messages = []
                                        my_messages = []
                                        
                                        for msg in messages:
                                            sender_uid = msg.get('sender_uid')
                                            if str(sender_uid) == str(self.account_uid):
                                                my_count += 1
                                                my_messages.append(msg)
                                            else:
                                                other_count += 1
                                                other_messages.append(msg)
                                        
                                        self._log_with_management(f"📊 消息统计: 我的消息 {my_count} 条，对方消息 {other_count} 条")
                                        
                                        # 显示前5条对方的消息
                                        if other_messages:
                                            self._log_with_management(f"🔍 对方发送的消息 (前{min(5, len(other_messages))}条):")
                                            for j, msg in enumerate(other_messages[:5]):
                                                sender_uid = msg.get('sender_uid')
                                                msg_type = msg.get('msg_type', 0)
                                                timestamp = msg.get('timestamp', 0)
                                                content = msg.get('content', '')
                                                
                                                time_str = time.strftime('%H:%M:%S', time.localtime(timestamp)) if timestamp else "无"
                                                
                                                # 尝试解析消息内容
                                                try:
                                                    if msg_type == 1:
                                                        content_obj = json.loads(content)
                                                        text = content_obj.get('content', '')
                                                    else:
                                                        text = f"[类型{msg_type}消息]"
                                                except:
                                                    text = content[:50] if content else "[空消息]"
                                                
                                                self._log_with_management(f"    📨 [{j+1}] {time_str} 对方({sender_uid}): {text}")
                                        else:
                                            self._log_with_management("⚠️ 没有对方发送的消息")
                                        
                                        # 显示前3条我的消息
                                        if my_messages:
                                            self._log_with_management(f"🔍 我发送的消息 (前{min(3, len(my_messages))}条):")
                                            for j, msg in enumerate(my_messages[:3]):
                                                sender_uid = msg.get('sender_uid')
                                                msg_type = msg.get('msg_type', 0)
                                                timestamp = msg.get('timestamp', 0)
                                                content = msg.get('content', '')
                                                
                                                time_str = time.strftime('%H:%M:%S', time.localtime(timestamp)) if timestamp else "无"
                                                
                                                # 尝试解析消息内容
                                                try:
                                                    if msg_type == 1:
                                                        content_obj = json.loads(content)
                                                        text = content_obj.get('content', '')
                                                    else:
                                                        text = f"[类型{msg_type}消息]"
                                                except:
                                                    text = content[:50] if content else "[空消息]"
                                                
                                                self._log_with_management(f"    📨 [{j+1}] {time_str} 我: {text}")
                                        
                                        # 显示最新的混合消息（按时间排序）
                                        self._log_with_management(f"🔍 最新消息时间线 (前10条):")
                                        for j, msg in enumerate(messages[:10]):
                                            sender_uid = msg.get('sender_uid')
                                            msg_type = msg.get('msg_type', 0)
                                            timestamp = msg.get('timestamp', 0)
                                            content = msg.get('content', '')
                                            
                                            time_str = time.strftime('%H:%M:%S', time.localtime(timestamp)) if timestamp else "无"
                                            sender_status = "我" if str(sender_uid) == str(self.account_uid) else f"对方({sender_uid})"
                                            
                                            # 尝试解析消息内容
                                            try:
                                                if msg_type == 1:
                                                    content_obj = json.loads(content)
                                                    text = content_obj.get('content', '')
                                                else:
                                                    text = f"[类型{msg_type}消息]"
                                            except:
                                                text = content[:50] if content else "[空消息]"
                                            
                                            self._log_with_management(f"    📨 [{j+1}] {time_str} {sender_status}: {text}")
                                    else:
                                        self._log_with_management("⚠️ 消息列表为空")
                                        self._log_with_management(f"📄 完整data数据: {msg_data}")
                                else:
                                    self._log_with_management(f"❌ data字段不是字典: {type(msg_data)}")
                            else:
                                self._log_with_management(f"❌ API返回错误码: {code}, 消息: {message}")
                        else:
                            self._log_with_management(f"❌ 响应不是字典格式: {type(data)}")
                            self._log_with_management(f"📄 原始响应: {str(data)[:500]}")
                    except json.JSONDecodeError as e:
                        self._log_with_management(f"❌ JSON解析失败: {str(e)}")
                        self._log_with_management(f"📄 原始响应文本: {response.text[:500]}")
                else:
                    self._log_with_management(f"❌ HTTP请求失败: {response.status_code}")
                    self._log_with_management(f"📄 响应文本: {response.text[:500]}")
                    
            except Exception as e:
                self._log_with_management(f"❌ 测试过程中出错: {str(e)}")
            
            self._log_with_management("─" * 50)
        
        # 3. 测试Cookie有效性
        self._log_with_management("🍪 步骤3：测试Cookie有效性")
        try:
            # 测试用户信息API
            url = "https://api.bilibili.com/x/web-interface/nav"
            response = self.session.get(url)
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 0:
                    user_info = data.get('data', {})
                    uname = user_info.get('uname', 'Unknown')
                    mid = user_info.get('mid', 'Unknown')
                    self._log_with_management(f"✅ Cookie有效 - 用户: {uname} (UID: {mid})")
                else:
                    self._log_with_management(f"❌ Cookie可能无效 - 错误码: {data.get('code')}")
            else:
                self._log_with_management(f"❌ 用户信息API请求失败: {response.status_code}")
        except Exception as e:
            self._log_with_management(f"❌ Cookie测试出错: {str(e)}")
        
        self._log_with_management("🔧 消息API调试完成") 