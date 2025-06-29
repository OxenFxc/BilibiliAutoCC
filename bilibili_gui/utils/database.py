#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Version: 1.0.0
Author: @OxenFxc
Copyright: https://github.com/OxenFxc
License: MIT License
Description: B站多账号扫码登录系统 - 自动私信回复功能
"""

import sqlite3
import time
import json
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
import os


class AutoReplyDatabase:
    def __init__(self, db_path: str = "auto_reply.db"):
        """
        初始化数据库管理器
        
        Args:
            db_path (str): 数据库文件路径
        """
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化数据库表结构"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 创建自动回复日志表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS auto_reply_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        account_uid TEXT NOT NULL,
                        sender_uid TEXT NOT NULL,
                        received_message TEXT NOT NULL,
                        reply_message TEXT NOT NULL,
                        keyword_matched TEXT NOT NULL,
                        match_type TEXT NOT NULL,
                        created_time REAL NOT NULL,
                        session_type INTEGER DEFAULT 1
                    )
                """)
                
                # 创建自动回复统计表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS auto_reply_stats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        account_uid TEXT NOT NULL,
                        total_replies INTEGER DEFAULT 0,
                        today_replies INTEGER DEFAULT 0,
                        last_reply_time REAL DEFAULT 0,
                        last_update_date TEXT DEFAULT '',
                        UNIQUE(account_uid)
                    )
                """)
                
                # 创建自动回复规则表（新增）
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS auto_reply_rules (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        account_uid TEXT NOT NULL,
                        keyword TEXT NOT NULL,
                        reply_content TEXT NOT NULL,
                        match_type TEXT NOT NULL DEFAULT 'contains',
                        case_sensitive INTEGER DEFAULT 0,
                        enabled INTEGER DEFAULT 1,
                        priority INTEGER DEFAULT 0,
                        description TEXT DEFAULT '',
                        created_time REAL NOT NULL,
                        updated_time REAL NOT NULL
                    )
                """)
                
                # 创建账号配置表（新增）
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS account_configs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        account_uid TEXT NOT NULL,
                        auto_reply_enabled INTEGER DEFAULT 0,
                        reply_delay_min INTEGER DEFAULT 1,
                        reply_delay_max INTEGER DEFAULT 3,
                        daily_limit INTEGER DEFAULT 0,
                        scan_interval INTEGER DEFAULT 8,
                        config_data TEXT DEFAULT '{}',
                        updated_time REAL NOT NULL,
                        UNIQUE(account_uid)
                    )
                """)
                
                # 尝试添加scan_interval列（如果不存在）
                try:
                    cursor.execute("ALTER TABLE account_configs ADD COLUMN scan_interval INTEGER DEFAULT 8")
                except sqlite3.OperationalError:
                    # 列已存在，忽略错误
                    pass
                
                # 创建索引
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_auto_reply_logs_account 
                    ON auto_reply_logs(account_uid)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_auto_reply_logs_time 
                    ON auto_reply_logs(created_time)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_auto_reply_stats_account 
                    ON auto_reply_stats(account_uid)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_auto_reply_rules_account 
                    ON auto_reply_rules(account_uid)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_account_configs_uid 
                    ON account_configs(account_uid)
                """)
                
                conn.commit()
                
        except Exception as e:
            print(f"初始化数据库失败: {str(e)}")
    
    def log_auto_reply(self, account_uid: str, sender_uid: str, 
                      received_message: str, reply_message: str,
                      keyword_matched: str, match_type: str,
                      session_type: int = 1) -> bool:
        """
        记录自动回复日志
        
        Args:
            account_uid (str): 账号UID
            sender_uid (str): 发送者UID
            received_message (str): 接收到的消息
            reply_message (str): 回复的消息
            keyword_matched (str): 匹配的关键词
            match_type (str): 匹配类型
            session_type (int): 会话类型
            
        Returns:
            bool: 是否成功
        """
        try:
            current_time = time.time()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 插入日志记录
                cursor.execute("""
                    INSERT INTO auto_reply_logs 
                    (account_uid, sender_uid, received_message, reply_message,
                     keyword_matched, match_type, created_time, session_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (account_uid, sender_uid, received_message, reply_message,
                      keyword_matched, match_type, current_time, session_type))
                
                # 更新统计数据
                self._update_stats(cursor, account_uid, current_time)
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"记录自动回复日志失败: {str(e)}")
            return False
    
    def _update_stats(self, cursor, account_uid: str, current_time: float):
        """更新统计数据"""
        today = date.today().isoformat()
        
        # 获取现有统计数据
        cursor.execute("""
            SELECT total_replies, today_replies, last_update_date 
            FROM auto_reply_stats WHERE account_uid = ?
        """, (account_uid,))
        
        result = cursor.fetchone()
        
        if result:
            total_replies, today_replies, last_update_date = result
            
            # 如果是新的一天，重置今日回复数
            if last_update_date != today:
                today_replies = 0
            
            # 更新统计
            cursor.execute("""
                UPDATE auto_reply_stats 
                SET total_replies = ?, today_replies = ?, 
                    last_reply_time = ?, last_update_date = ?
                WHERE account_uid = ?
            """, (total_replies + 1, today_replies + 1, current_time, today, account_uid))
        else:
            # 创建新的统计记录
            cursor.execute("""
                INSERT INTO auto_reply_stats 
                (account_uid, total_replies, today_replies, last_reply_time, last_update_date)
                VALUES (?, 1, 1, ?, ?)
            """, (account_uid, current_time, today))
    
    # 新增：自动回复规则管理方法
    def save_auto_reply_rule(self, account_uid: str, keyword: str, reply_content: str,
                           match_type: str = 'contains', case_sensitive: bool = False,
                           enabled: bool = True, priority: int = 0, 
                           description: str = '', rule_id: int = None) -> int:
        """
        保存自动回复规则
        
        Args:
            account_uid (str): 账号UID
            keyword (str): 关键词
            reply_content (str): 回复内容
            match_type (str): 匹配类型
            case_sensitive (bool): 是否区分大小写
            enabled (bool): 是否启用
            priority (int): 优先级
            description (str): 描述
            rule_id (int): 规则ID（用于更新）
            
        Returns:
            int: 规则ID
        """
        try:
            current_time = time.time()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if rule_id:
                    # 更新现有规则
                    cursor.execute("""
                        UPDATE auto_reply_rules 
                        SET keyword = ?, reply_content = ?, match_type = ?,
                            case_sensitive = ?, enabled = ?, priority = ?,
                            description = ?, updated_time = ?
                        WHERE id = ? AND account_uid = ?
                    """, (keyword, reply_content, match_type, int(case_sensitive),
                          int(enabled), priority, description, current_time, rule_id, account_uid))
                    
                    return rule_id
                else:
                    # 创建新规则
                    cursor.execute("""
                        INSERT INTO auto_reply_rules 
                        (account_uid, keyword, reply_content, match_type,
                         case_sensitive, enabled, priority, description,
                         created_time, updated_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (account_uid, keyword, reply_content, match_type,
                          int(case_sensitive), int(enabled), priority, description,
                          current_time, current_time))
                    
                    return cursor.lastrowid
                
        except Exception as e:
            print(f"保存自动回复规则失败: {str(e)}")
            return 0
    
    def get_auto_reply_rules(self, account_uid: str, enabled_only: bool = False) -> List[Dict]:
        """
        获取自动回复规则
        
        Args:
            account_uid (str): 账号UID
            enabled_only (bool): 是否只获取启用的规则
            
        Returns:
            List[Dict]: 规则列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT id, keyword, reply_content, match_type, case_sensitive,
                           enabled, priority, description, created_time, updated_time
                    FROM auto_reply_rules 
                    WHERE account_uid = ?
                """
                params = [account_uid]
                
                if enabled_only:
                    query += " AND enabled = 1"
                
                query += " ORDER BY priority DESC, created_time ASC"
                
                cursor.execute(query, params)
                
                columns = ['id', 'keyword', 'reply_content', 'match_type', 'case_sensitive',
                          'enabled', 'priority', 'description', 'created_time', 'updated_time']
                
                rules = []
                for row in cursor.fetchall():
                    rule = dict(zip(columns, row))
                    rule['case_sensitive'] = bool(rule['case_sensitive'])
                    rule['enabled'] = bool(rule['enabled'])
                    rules.append(rule)
                
                return rules
                
        except Exception as e:
            print(f"获取自动回复规则失败: {str(e)}")
            return []
    
    def delete_auto_reply_rule(self, account_uid: str, rule_id: int) -> bool:
        """
        删除自动回复规则
        
        Args:
            account_uid (str): 账号UID
            rule_id (int): 规则ID
            
        Returns:
            bool: 是否成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM auto_reply_rules 
                    WHERE id = ? AND account_uid = ?
                """, (rule_id, account_uid))
                
                return cursor.rowcount > 0
                
        except Exception as e:
            print(f"删除自动回复规则失败: {str(e)}")
            return False
    
    def toggle_rule_status(self, account_uid: str, rule_id: int) -> bool:
        """
        切换规则启用状态
        
        Args:
            account_uid (str): 账号UID
            rule_id (int): 规则ID
            
        Returns:
            bool: 是否成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE auto_reply_rules 
                    SET enabled = NOT enabled, updated_time = ?
                    WHERE id = ? AND account_uid = ?
                """, (time.time(), rule_id, account_uid))
                
                return cursor.rowcount > 0
                
        except Exception as e:
            print(f"切换规则状态失败: {str(e)}")
            return False
    
    # 新增：账号配置管理
    def save_account_config(self, account_uid: str, auto_reply_enabled: bool = False,
                          reply_delay_min: int = 1, reply_delay_max: int = 3,
                          daily_limit: int = 0, scan_interval: int = 8, 
                          config_data: Dict = None) -> bool:
        """
        保存账号配置
        
        Args:
            account_uid (str): 账号UID
            auto_reply_enabled (bool): 是否启用自动回复
            reply_delay_min (int): 最小回复延迟（秒）
            reply_delay_max (int): 最大回复延迟（秒）
            daily_limit (int): 每日回复限制（0表示无限制）
            scan_interval (int): 扫描间隔（秒）
            config_data (Dict): 其他配置数据
            
        Returns:
            bool: 是否成功
        """
        try:
            config_json = json.dumps(config_data or {}, ensure_ascii=False)
            current_time = time.time()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO account_configs 
                    (account_uid, auto_reply_enabled, reply_delay_min, reply_delay_max,
                     daily_limit, scan_interval, config_data, updated_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (account_uid, int(auto_reply_enabled), reply_delay_min, reply_delay_max,
                      daily_limit, scan_interval, config_json, current_time))
                
                return True
                
        except Exception as e:
            print(f"保存账号配置失败: {str(e)}")
            return False
    
    def get_account_config(self, account_uid: str) -> Optional[Dict]:
        """
        获取账号配置
        
        Args:
            account_uid (str): 账号UID
            
        Returns:
            Optional[Dict]: 配置信息
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT auto_reply_enabled, reply_delay_min, reply_delay_max,
                           daily_limit, scan_interval, config_data, updated_time
                    FROM account_configs 
                    WHERE account_uid = ?
                """, (account_uid,))
                
                result = cursor.fetchone()
                if result:
                    config = {
                        'auto_reply_enabled': bool(result[0]),
                        'reply_delay_min': result[1],
                        'reply_delay_max': result[2],
                        'daily_limit': result[3],
                        'scan_interval': result[4] if result[4] is not None else 8,
                        'config_data': json.loads(result[5]) if result[5] else {},
                        'updated_time': result[6]
                    }
                    return config
                
                return None
                
        except Exception as e:
            print(f"获取账号配置失败: {str(e)}")
            return None

    def get_reply_logs(self, account_uid: str, limit: int = 100, 
                      offset: int = 0) -> List[Dict]:
        """
        获取自动回复日志
        
        Args:
            account_uid (str): 账号UID
            limit (int): 限制数量
            offset (int): 偏移量
            
        Returns:
            List[Dict]: 日志列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, sender_uid, received_message, reply_message,
                           keyword_matched, match_type, created_time, session_type
                    FROM auto_reply_logs 
                    WHERE account_uid = ?
                    ORDER BY created_time DESC
                    LIMIT ? OFFSET ?
                """, (account_uid, limit, offset))
                
                columns = ['id', 'sender_uid', 'received_message', 'reply_message',
                          'keyword_matched', 'match_type', 'created_time', 'session_type']
                
                logs = []
                for row in cursor.fetchall():
                    log = dict(zip(columns, row))
                    logs.append(log)
                
                return logs
                
        except Exception as e:
            print(f"获取回复日志失败: {str(e)}")
            return []
    
    def get_reply_stats(self, account_uid: str) -> Optional[Dict]:
        """
        获取回复统计
        
        Args:
            account_uid (str): 账号UID
            
        Returns:
            Optional[Dict]: 统计信息
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT total_replies, today_replies, last_reply_time, last_update_date
                    FROM auto_reply_stats 
                    WHERE account_uid = ?
                """, (account_uid,))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'total_replies': result[0],
                        'today_replies': result[1],
                        'last_reply_time': result[2],
                        'last_update_date': result[3]
                    }
                
                return None
                
        except Exception as e:
            print(f"获取回复统计失败: {str(e)}")
            return None

    def delete_old_logs(self, days: int = 30) -> bool:
        """
        删除旧日志
        
        Args:
            days (int): 保留天数
            
        Returns:
            bool: 是否成功
        """
        try:
            cutoff_time = time.time() - (days * 24 * 3600)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM auto_reply_logs 
                    WHERE created_time < ?
                """, (cutoff_time,))
                
                deleted_count = cursor.rowcount
                print(f"删除了 {deleted_count} 条旧日志记录")
                return True
                
        except Exception as e:
            print(f"删除旧日志失败: {str(e)}")
            return False

    def get_daily_stats(self, account_uid: str, days: int = 7) -> List[Dict]:
        """
        获取每日统计
        
        Args:
            account_uid (str): 账号UID
            days (int): 统计天数
            
        Returns:
            List[Dict]: 每日统计列表
        """
        try:
            start_time = time.time() - (days * 24 * 3600)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DATE(created_time, 'unixepoch') as date,
                           COUNT(*) as count
                    FROM auto_reply_logs 
                    WHERE account_uid = ? AND created_time >= ?
                    GROUP BY date
                    ORDER BY date
                """, (account_uid, start_time))
                
                stats = []
                for row in cursor.fetchall():
                    stats.append({
                        'date': row[0],
                        'count': row[1]
                    })
                
                return stats
                
        except Exception as e:
            print(f"获取每日统计失败: {str(e)}")
            return []

    def get_keyword_stats(self, account_uid: str, limit: int = 10) -> List[Dict]:
        """
        获取关键词统计
        
        Args:
            account_uid (str): 账号UID
            limit (int): 返回数量限制
            
        Returns:
            List[Dict]: 关键词统计列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT keyword_matched, COUNT(*) as count,
                           MAX(created_time) as last_used
                    FROM auto_reply_logs 
                    WHERE account_uid = ?
                    GROUP BY keyword_matched
                    ORDER BY count DESC
                    LIMIT ?
                """, (account_uid, limit))
                
                stats = []
                for row in cursor.fetchall():
                    stats.append({
                        'keyword': row[0],
                        'count': row[1],
                        'last_used': row[2]
                    })
                
                return stats
                
        except Exception as e:
            print(f"获取关键词统计失败: {str(e)}")
            return [] 