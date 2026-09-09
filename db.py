# -*- coding: utf-8 -*-
"""
数据库连接工具

连接配置优先级：
1. 环境变量 DATABASE_URL（Railway/Render 等 PaaS 平台自动注入，如 mysql://user:pass@host:port/dbname）
2. 环境变量 MYSQL_URL（Railway MySQL 模板注入的完整连接串，如 mysql://user:pass@host:port/dbname）
3. 环境变量 MYSQLHOST / MYSQLPORT / MYSQLUSER / MYSQLPASSWORD / MYSQLDATABASE（Railway MySQL 单变量）
4. 环境变量 DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME
5. 本机默认配置（127.0.0.1 / root / 本机密码）
"""
import os
import urllib.parse

import pymysql


def _parse_database_url(url):
    """解析 mysql://user:pass@host:port/dbname 格式的连接串"""
    parsed = urllib.parse.urlparse(url)
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 3306,
        "user": urllib.parse.unquote(parsed.username) if parsed.username else "root",
        "password": urllib.parse.unquote(parsed.password) if parsed.password else "",
        "database": parsed.path.lstrip("/") or "herb_management_system",
    }


def get_db_config():
    """根据环境变量返回数据库连接配置"""
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        db_url = os.environ.get("MYSQL_URL", "").strip()
    if db_url:
        cfg = _parse_database_url(db_url)
    elif os.environ.get("MYSQLHOST", "").strip():
        # Railway MySQL 单变量模式
        cfg = {
            "host": os.environ.get("MYSQLHOST", "127.0.0.1"),
            "port": int(os.environ.get("MYSQLPORT", "3306")),
            "user": os.environ.get("MYSQLUSER", "root"),
            "password": os.environ.get("MYSQLPASSWORD", ""),
            "database": os.environ.get("MYSQLDATABASE", "herb_management_system"),
        }
    else:
        cfg = {
            "host": os.environ.get("DB_HOST", "127.0.0.1"),
            "port": int(os.environ.get("DB_PORT", "3306")),
            "user": os.environ.get("DB_USER", "root"),
            # 本机 MySQL 密码请通过环境变量 DB_PASSWORD 设置，或自行修改此处
            "password": os.environ.get("DB_PASSWORD", "YOUR_MYSQL_PASSWORD"),
            "database": os.environ.get("DB_NAME", "herb_management_system"),
        }
    cfg["charset"] = "utf8mb4"
    cfg["cursorclass"] = pymysql.cursors.DictCursor
    return cfg


def get_conn():
    """获取数据库连接"""
    return pymysql.connect(**get_db_config())


def query(sql, args=None, one=False):
    """查询：返回 dict 列表（one=True 时返回单条或 None）"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            rows = cur.fetchall()
            return rows[0] if one and rows else rows
    finally:
        conn.close()


def execute(sql, args=None):
    """增删改：返回受影响行数"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            affected = cur.execute(sql, args)
        conn.commit()
        return affected
    finally:
        conn.close()
