# -*- coding: utf-8 -*-
"""
数据库连接工具（智能双模式：MySQL / SQLite）

- 默认使用 SQLite（Python 内置，无需安装数据库，即开即用）
- 设置环境变量 USE_MYSQL=1 时切换到 MySQL
- 自动处理 %s 和 ? 占位符差异
"""
import os
import sqlite3
import urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB_PATH = os.path.join(BASE_DIR, "herb_management.db")

_use_mysql = os.environ.get("USE_MYSQL", "").strip().lower() in ("1", "true", "yes")
_mysql_available = False

if _use_mysql:
    try:
        import pymysql
        _mysql_available = True
    except ImportError:
        _mysql_available = False


def is_mysql():
    return _use_mysql and _mysql_available


def _convert_placeholders(sql):
    """将 SQL 中的 %s 占位符转换为 SQLite 的 ?"""
    if is_mysql():
        return sql
    return sql.replace("%s", "?")


class DictCursorSqlite:
    """SQLite 字典游标包装"""
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, args=None):
        sql = _convert_placeholders(sql)
        if args is None:
            return self._cursor.execute(sql)
        return self._cursor.execute(sql, args)

    def fetchall(self):
        columns = [desc[0] for desc in self._cursor.description] if self._cursor.description else []
        return [dict(zip(columns, row)) for row in self._cursor.fetchall()]

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        columns = [desc[0] for desc in self._cursor.description] if self._cursor.description else []
        return dict(zip(columns, row))

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount


def get_conn():
    if is_mysql():
        import pymysql
        # 优先用 MYSQL_URL 解析（Railway MySQL 自动提供）
        mysql_url = os.environ.get("MYSQL_URL") or os.environ.get("MYSQL_PUBLIC_URL")
        if mysql_url:
            parsed = urllib.parse.urlparse(mysql_url)
            cfg = {
                "host": parsed.hostname,
                "port": parsed.port or 3306,
                "user": parsed.username,
                "password": parsed.password,
                "database": parsed.path.lstrip("/"),
                "charset": "utf8mb4",
                "cursorclass": pymysql.cursors.DictCursor,
            }
        else:
            cfg = {
                "host": os.environ.get("DB_HOST") or os.environ.get("MYSQLHOST") or "127.0.0.1",
                "port": int(os.environ.get("DB_PORT") or os.environ.get("MYSQLPORT") or "3306"),
                "user": os.environ.get("DB_USER") or os.environ.get("MYSQLUSER") or "root",
                "password": os.environ.get("DB_PASSWORD") or os.environ.get("MYSQLPASSWORD") or "",
                "database": os.environ.get("DB_NAME") or os.environ.get("MYSQLDATABASE") or "herb_management_system",
                "charset": "utf8mb4",
                "cursorclass": pymysql.cursors.DictCursor,
            }
        return pymysql.connect(**cfg)
    else:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def query(sql, args=None, one=False):
    conn = get_conn()
    try:
        if is_mysql():
            with conn.cursor() as cur:
                cur.execute(sql, args)
                rows = cur.fetchall()
                return rows[0] if one and rows else rows
        else:
            cur = DictCursorSqlite(conn.cursor())
            cur.execute(sql, args)
            rows = cur.fetchall()
            return rows[0] if one and rows else rows
    finally:
        conn.close()


def execute(sql, args=None):
    conn = get_conn()
    try:
        if is_mysql():
            with conn.cursor() as cur:
                affected = cur.execute(sql, args)
                last_id = cur.lastrowid
            conn.commit()
            return affected, last_id
        else:
            cur = DictCursorSqlite(conn.cursor())
            affected = cur.execute(sql, args)
            last_id = cur.lastrowid
            conn.commit()
            return cur.rowcount, last_id
    finally:
        conn.close()
