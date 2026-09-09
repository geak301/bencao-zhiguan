# -*- coding: utf-8 -*-
"""
数据库初始化脚本
- 创建数据库 herb_management_system
- 创建 users / herbs / operation_logs 三张表
- 写入默认账号（admin/123456、doctor/123456、patient/123456）

用法：python init_db.py
"""
import hashlib
import os
import urllib.parse

import pymysql

DB_NAME = "herb_management_system"


def _load_conn_config():
    """读取数据库连接：优先 DATABASE_URL/MYSQL_URL（PaaS 平台），否则本机 root"""
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        db_url = os.environ.get("MYSQL_URL", "").strip()
    if db_url:
        parsed = urllib.parse.urlparse(db_url)
        return {
            "host": parsed.hostname or "127.0.0.1",
            "port": parsed.port or 3306,
            "user": urllib.parse.unquote(parsed.username) if parsed.username else "root",
            "password": urllib.parse.unquote(parsed.password) if parsed.password else "",
            "database": parsed.path.lstrip("/") or DB_NAME,
            "charset": "utf8mb4",
        }
    if os.environ.get("MYSQLHOST", "").strip():
        # Railway MySQL 单变量模式
        return {
            "host": os.environ.get("MYSQLHOST", "127.0.0.1"),
            "port": int(os.environ.get("MYSQLPORT", "3306")),
            "user": os.environ.get("MYSQLUSER", "root"),
            "password": os.environ.get("MYSQLPASSWORD", ""),
            "database": os.environ.get("MYSQLDATABASE", DB_NAME),
            "charset": "utf8mb4",
        }
    return {
        "host": os.environ.get("DB_HOST", "127.0.0.1"),
        "port": int(os.environ.get("DB_PORT", "3306")),
        "user": os.environ.get("DB_USER", "root"),
        # 本机 MySQL 密码请通过环境变量 DB_PASSWORD 设置，或自行修改此处
        "password": os.environ.get("DB_PASSWORD", "YOUR_MYSQL_PASSWORD"),
        "database": None,  # 本机模式下先不选库，建库后再 USE
        "charset": "utf8mb4",
    }

CREATE_DATABASE_SQL = (
    f"CREATE DATABASE IF NOT EXISTS {DB_NAME} "
    f"DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
)

CREATE_TABLES_SQL = [
    # 用户表
    """
    CREATE TABLE IF NOT EXISTS users (
        username        VARCHAR(50)  NOT NULL COMMENT '用户名',
        password        VARCHAR(64)  NOT NULL COMMENT '密码(SHA256)',
        role            VARCHAR(20)  NOT NULL DEFAULT 'patient' COMMENT '角色: admin/doctor/patient',
        name            VARCHAR(50)  NOT NULL COMMENT '真实姓名',
        phone           VARCHAR(30)  DEFAULT NULL COMMENT '联系电话',
        status          VARCHAR(20)  NOT NULL DEFAULT 'active' COMMENT '状态: active/inactive',
        department      VARCHAR(50)  DEFAULT NULL COMMENT '所属科室(医生)',
        license         VARCHAR(50)  DEFAULT NULL COMMENT '执业医师证号(医生)',
        gender          VARCHAR(10)  DEFAULT NULL COMMENT '性别(病人)',
        age             INT          DEFAULT NULL COMMENT '年龄(病人)',
        idcard          VARCHAR(30)  DEFAULT NULL COMMENT '身份证号(病人)',
        create_time     VARCHAR(50)  DEFAULT NULL COMMENT '注册时间',
        PRIMARY KEY (username)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表'
    """,
    # 药材表
    """
    CREATE TABLE IF NOT EXISTS herbs (
        code               VARCHAR(50)   NOT NULL COMMENT '药材编码',
        name               VARCHAR(50)   NOT NULL COMMENT '药材名称',
        category           VARCHAR(50)   DEFAULT NULL COMMENT '类别',
        origin             VARCHAR(100)  DEFAULT NULL COMMENT '产地',
        storage            VARCHAR(100)  DEFAULT NULL COMMENT '储存条件',
        unit               VARCHAR(20)   DEFAULT NULL COMMENT '单位',
        price              DECIMAL(10,2) DEFAULT NULL COMMENT '单价',
        quantity           INT           DEFAULT 0 COMMENT '库存数量',
        warning_threshold  INT           DEFAULT 200 COMMENT '预警阈值',
        description        TEXT          COMMENT '描述',
        created_at         DATETIME      DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
        updated_at         DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
        PRIMARY KEY (code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='药材表'
    """,
    # 操作日志表
    """
    CREATE TABLE IF NOT EXISTS operation_logs (
        id             INT AUTO_INCREMENT PRIMARY KEY COMMENT '日志ID',
        herb_code      VARCHAR(50)  DEFAULT NULL COMMENT '药材编码',
        herb_name      VARCHAR(50)  DEFAULT NULL COMMENT '药材名称',
        action         VARCHAR(20)  NOT NULL COMMENT '操作: add/edit/delete',
        changes        JSON         DEFAULT NULL COMMENT '字段变更明细',
        operator       VARCHAR(50)  DEFAULT NULL COMMENT '操作人用户名',
        operator_name  VARCHAR(50)  DEFAULT NULL COMMENT '操作人姓名',
        timestamp      BIGINT       DEFAULT NULL COMMENT '操作时间戳',
        time_str       VARCHAR(50)  DEFAULT NULL COMMENT '操作时间文本'
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='操作日志表'
    """,
]

# 默认账号：admin/123456、doctor/123456、patient/123456
DEFAULT_USERS = [
    {
        "username": "admin",
        "password": "123456",
        "role": "admin",
        "name": "系统管理员",
        "phone": "13800138000",
        "status": "active",
        "department": None,
        "license": None,
        "gender": None,
        "age": None,
        "idcard": None,
        "create_time": "2026/9/7 00:00:00",
    },
    {
        "username": "doctor",
        "password": "123456",
        "role": "doctor",
        "name": "李医生",
        "phone": "13900139000",
        "status": "active",
        "department": "中医内科",
        "license": "110101202600001",
        "gender": None,
        "age": None,
        "idcard": None,
        "create_time": "2026/9/7 00:00:00",
    },
    {
        "username": "patient",
        "password": "123456",
        "role": "patient",
        "name": "王病人",
        "phone": "13700137000",
        "status": "active",
        "department": None,
        "license": None,
        "gender": "男",
        "age": 35,
        "idcard": "340104199101011234",
        "create_time": "2026/9/7 00:00:00",
    },
]


def sha256_pwd(password):
    """SHA256 哈希密码（与后端一致）"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def main():
    conn_cfg = _load_conn_config()
    via_url = bool(os.environ.get("DATABASE_URL", "").strip())
    conn = pymysql.connect(**{k: v for k, v in conn_cfg.items() if k != "database"})
    try:
        with conn.cursor() as cur:
            if via_url:
                # PaaS 平台：直接使用平台分配的数据库
                print(f"[1/4] 使用平台数据库 {conn_cfg['database']} ...")
            else:
                print(f"[1/4] 创建数据库 {DB_NAME} ...")
                cur.execute(CREATE_DATABASE_SQL)

            print("[2/4] 创建数据表 ...")
            cur.execute(f"USE {conn_cfg['database']}")
            for sql in CREATE_TABLES_SQL:
                cur.execute(sql)

            print("[3/4] 写入默认账号 ...")
            for u in DEFAULT_USERS:
                sql = """
                    INSERT INTO users
                        (username, password, role, name, phone, status,
                         department, license, gender, age, idcard, create_time)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        password = VALUES(password), role = VALUES(role),
                        name = VALUES(name), phone = VALUES(phone), status = VALUES(status)
                """
                cur.execute(sql, (
                    u["username"], sha256_pwd(u["password"]), u["role"], u["name"],
                    u["phone"], u["status"], u["department"], u["license"],
                    u["gender"], u["age"], u["idcard"], u["create_time"],
                ))

            print("[4/4] 校验表结构 ...")
            cur.execute("SHOW TABLES")
            tables = [r[0] for r in cur.fetchall()]
            for t in ["users", "herbs", "operation_logs"]:
                assert t in tables, f"缺少表 {t}"
                print(f"  - 表 {t} 就绪")
            cur.execute("SELECT username, role FROM users")
            for r in cur.fetchall():
                print(f"  - 账号 {r[0]} ({r[1]})")
        conn.commit()
        print("\n数据库初始化完成！")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
