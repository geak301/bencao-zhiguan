# -*- coding: utf-8 -*-
"""
数据库连接工具（智能双模式：MySQL / SQLite）

- 默认使用 SQLite（Python 内置，无需安装数据库，即开即用）
- 以下任一条件启用 MySQL：
  1. 设置环境变量 USE_MYSQL=1
  2. 存在 DATABASE_URL（Railway/Render 等 PaaS 平台注入）
  3. 存在 MYSQL_URL（Railway MySQL 模板注入）
- MySQL 连接配置优先级：DATABASE_URL / MYSQL_URL → MYSQLHOST等 → DB_HOST等 → 本机默认
- 自动处理 %s 和 ? 占位符差异
"""
import os
import sqlite3
import urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB_PATH = os.path.join(BASE_DIR, "herb_management.db")

_env_use_mysql = os.environ.get("USE_MYSQL", "").strip().lower() in ("1", "true", "yes")
_has_db_url = bool(os.environ.get("DATABASE_URL", "").strip() or os.environ.get("MYSQL_URL", "").strip())
_mysql_available = False

if _env_use_mysql or _has_db_url:
    try:
        import pymysql
        _mysql_available = True
    except ImportError:
        _mysql_available = False


def is_mysql():
    return (_env_use_mysql or _has_db_url) and _mysql_available


def _get_mysql_cfg():
    """返回 MySQL 连接配置（兼容 Railway / 通用 PaaS / 本机）"""
    import pymysql
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        db_url = os.environ.get("MYSQL_URL", "").strip()
    if db_url:
        parsed = urllib.parse.urlparse(db_url)
        cfg = {
            "host": parsed.hostname or "127.0.0.1",
            "port": parsed.port or 3306,
            "user": urllib.parse.unquote(parsed.username) if parsed.username else "root",
            "password": urllib.parse.unquote(parsed.password) if parsed.password else "",
            "database": parsed.path.lstrip("/") or "herb_management_system",
        }
    elif os.environ.get("MYSQLHOST", "").strip():
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
        return pymysql.connect(**_get_mysql_cfg())
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
