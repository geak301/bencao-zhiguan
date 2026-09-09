# -*- coding: utf-8 -*-
"""
本草智管平台 - 后端服务（Flask + MySQL）
- 托管前端静态页面
- 提供 REST API：登录/注册、药材管理、用户管理、操作日志、仪表盘统计

启动方式：
    cd backend
    python app.py
然后浏览器访问 http://127.0.0.1:5000
"""
import hashlib
import json
import os
import time

from flask import Flask, jsonify, request, send_from_directory

from db import execute, query

# ============ 路径配置 ============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

DEFAULT_WARNING_THRESHOLD = 200

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")


# ============ 工具函数 ============
def sha256_pwd(password: str) -> str:
    """SHA256 哈希密码"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def ok(data=None, message="success"):
    return jsonify({"code": 0, "message": message, "data": data})


def fail(message, code=1, http=200):
    return jsonify({"code": code, "message": message, "data": None}), http


def user_to_camel(row):
    """数据库用户行 -> 前端 camelCase 对象"""
    return {
        "username": row["username"],
        "password": "",  # 不返回密码明文/哈希
        "role": row["role"],
        "name": row["name"],
        "phone": row["phone"],
        "status": row["status"],
        "department": row["department"],
        "license": row["license"],
        "gender": row["gender"],
        "age": row["age"],
        "idcard": row["idcard"],
        "createTime": row["create_time"],
    }


def herb_to_camel(row):
    """数据库药材行 -> 前端 camelCase 对象"""
    return {
        "code": row["code"],
        "name": row["name"],
        "category": row["category"],
        "origin": row["origin"],
        "storage": row["storage"],
        "unit": row["unit"],
        "price": float(row["price"]) if row["price"] is not None else None,
        "quantity": row["quantity"],
        "warningThreshold": row["warning_threshold"],
        "description": row["description"],
    }


def log_to_camel(row):
    """数据库日志行 -> 前端 camelCase 对象"""
    changes = row["changes"]
    if isinstance(changes, str):
        try:
            changes = json.loads(changes)
        except Exception:
            changes = []
    return {
        "id": f"log_{row['id']}",
        "herbCode": row["herb_code"],
        "herbName": row["herb_name"],
        "action": row["action"],
        "changes": changes or [],
        "operator": row["operator"],
        "operatorName": row["operator_name"],
        "timestamp": row["timestamp"],
        "timeStr": row["time_str"],
    }


def add_log(herb_code, herb_name, action, changes, operator, operator_name):
    """写入操作日志"""
    execute(
        """INSERT INTO operation_logs
           (herb_code, herb_name, action, changes, operator, operator_name, timestamp, time_str)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            herb_code, herb_name, action,
            json.dumps(changes, ensure_ascii=False, default=str),
            operator, operator_name,
            int(time.time() * 1000),
            time.strftime("%Y/%m/%d %H:%M:%S"),
        ),
    )


def get_current_user():
    """从请求头 X-User 获取当前登录用户信息，未登录或禁用返回 None"""
    username = request.headers.get("X-User", "").strip()
    if not username:
        return None
    return query("SELECT * FROM users WHERE username = %s", (username,), one=True)


def require_login():
    """要求登录，失败返回 (None, response)"""
    user = get_current_user()
    if not user:
        return None, fail("未登录或账号不存在", code=401, http=401)
    if user["status"] != "active":
        return None, fail("该账号已被禁用", code=403, http=403)
    return user, None


def require_admin():
    """要求管理员权限"""
    user, err = require_login()
    if err:
        return None, err
    if user["role"] != "admin":
        return None, fail("无权限：仅管理员可执行此操作", code=403, http=403)
    return user, None


# ============ 页面路由 ============
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


# ============ 认证接口 ============
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return fail("请填写用户名和密码")

    user = query("SELECT * FROM users WHERE username = %s", (username,), one=True)
    if not user or user["password"] != sha256_pwd(password):
        return fail("用户名或密码错误")
    if user["status"] == "inactive":
        return fail("该账号已被禁用，请联系管理员")

    return ok({
        "username": user["username"],
        "role": user["role"],
        "name": user["name"],
        "phone": user["phone"],
    })


@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    role = data.get("role") or "patient"

    if not username or not password or not name or not phone:
        return fail("请填写所有必填字段")
    if role not in ("admin", "doctor", "patient"):
        return fail("角色不合法")
    if role == "admin":
        admin_key = data.get("adminKey") or ""
        if admin_key != "admin123":
            return fail("管理员注册密钥错误")

    if query("SELECT 1 FROM users WHERE username = %s", (username,), one=True):
        return fail("用户名已存在，请更换用户名")

    department = (data.get("department") or "").strip() if role == "doctor" else None
    license_no = (data.get("license") or "").strip() if role == "doctor" else None
    gender = data.get("gender") if role == "patient" else None
    age = data.get("age") if role == "patient" else None
    idcard = (data.get("idcard") or "").strip() if role == "patient" else None

    execute(
        """INSERT INTO users
           (username, password, role, name, phone, status,
            department, license, gender, age, idcard, create_time)
           VALUES (%s, %s, %s, %s, %s, 'active', %s, %s, %s, %s, %s, %s)""",
        (
            username, sha256_pwd(password), role, name, phone,
            department, license_no, gender, age, idcard,
            time.strftime("%Y/%m/%d %H:%M:%S"),
        ),
    )
    return ok(None, "注册成功")


# ============ 药材接口 ============
@app.route("/api/herbs", methods=["GET"])
def list_herbs():
    user, err = require_login()
    if err:
        return err
    keyword = (request.args.get("q") or "").strip()
    if keyword:
        like = f"%{keyword}%"
        rows = query(
            """SELECT * FROM herbs
               WHERE name LIKE %s OR code LIKE %s OR category LIKE %s OR origin LIKE %s
               ORDER BY created_at DESC, code ASC""",
            (like, like, like, like),
        )
    else:
        rows = query("SELECT * FROM herbs ORDER BY created_at DESC, code ASC")
    return ok([herb_to_camel(r) for r in rows])


@app.route("/api/herbs", methods=["POST"])
def add_herb():
    user, err = require_login()
    if err:
        return err
    if user["role"] == "patient":
        return fail("无权限：病人角色为只读，不能添加药材", code=403, http=403)

    d = request.get_json(silent=True) or {}
    code = (d.get("code") or "").strip()
    name = (d.get("name") or "").strip()
    category = (d.get("category") or "").strip()
    origin = (d.get("origin") or "").strip()
    storage = (d.get("storage") or "").strip()
    unit = (d.get("unit") or "").strip()
    description = (d.get("description") or "").strip()

    try:
        price = float(d.get("price"))
    except (TypeError, ValueError):
        price = 0
    try:
        quantity = int(d.get("quantity"))
    except (TypeError, ValueError):
        quantity = 0
    try:
        warning_threshold = int(d.get("warningThreshold")) or DEFAULT_WARNING_THRESHOLD
    except (TypeError, ValueError):
        warning_threshold = DEFAULT_WARNING_THRESHOLD

    if not code or not name or not category or not origin or not unit:
        return fail("请填写所有必填字段")
    if query("SELECT 1 FROM herbs WHERE code = %s", (code,), one=True):
        return fail("已存在相同编码的药材，请使用其他编码")

    execute(
        """INSERT INTO herbs
           (code, name, category, origin, storage, unit, price, quantity, warning_threshold, description)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (code, name, category, origin, storage, unit, price, quantity, warning_threshold, description),
    )
    add_log(code, name, "add", [
        {"field": f, "label": FIELD_LABELS.get(f, f), "oldValue": None, "newValue": v}
        for f, v in {
            "code": code, "name": name, "category": category, "origin": origin,
            "storage": storage, "unit": unit, "price": price, "quantity": quantity,
            "warningThreshold": warning_threshold, "description": description,
        }.items()
    ], user["username"], user["name"])
    return ok(None, "药材添加成功")


@app.route("/api/herbs/<code>", methods=["PUT"])
def update_herb(code):
    user, err = require_login()
    if err:
        return err
    if user["role"] == "patient":
        return fail("无权限：病人角色为只读，不能修改药材", code=403, http=403)

    old = query("SELECT * FROM herbs WHERE code = %s", (code,), one=True)
    if not old:
        return fail("药材不存在")

    d = request.get_json(silent=True) or {}
    new_data = {
        "code": code,
        "name": (d.get("name") or old["name"]).strip(),
        "category": (d.get("category") or old["category"] or "").strip(),
        "origin": (d.get("origin") or old["origin"] or "").strip(),
        "storage": d.get("storage") if d.get("storage") is not None else old["storage"],
        "unit": (d.get("unit") or old["unit"] or "").strip(),
        "description": d.get("description") if d.get("description") is not None else old["description"],
    }
    try:
        new_data["price"] = float(d.get("price", old["price"]))
    except (TypeError, ValueError):
        new_data["price"] = old["price"]
    try:
        new_data["quantity"] = int(d.get("quantity", old["quantity"]))
    except (TypeError, ValueError):
        new_data["quantity"] = old["quantity"]
    try:
        new_data["warningThreshold"] = int(d.get("warningThreshold", old["warning_threshold"])) or DEFAULT_WARNING_THRESHOLD
    except (TypeError, ValueError):
        new_data["warningThreshold"] = old["warning_threshold"]

    execute(
        """UPDATE herbs SET name=%s, category=%s, origin=%s, storage=%s, unit=%s,
           price=%s, quantity=%s, warning_threshold=%s, description=%s WHERE code=%s""",
        (
            new_data["name"], new_data["category"], new_data["origin"], new_data["storage"],
            new_data["unit"], new_data["price"], new_data["quantity"],
            new_data["warningThreshold"], new_data["description"], code,
        ),
    )

    # 计算字段变更并写日志
    changes = []
    field_map = {
        "name": "药材名称", "category": "类别", "origin": "产地", "storage": "储存条件",
        "unit": "单位", "price": "单价", "quantity": "库存数量",
        "warningThreshold": "预警阈值", "description": "描述",
    }
    for f, label in field_map.items():
        old_val = old["name"] if f == "name" else (
            old["category"] if f == "category" else
            old["origin"] if f == "origin" else
            old["storage"] if f == "storage" else
            old["unit"] if f == "unit" else
            old["price"] if f == "price" else
            old["quantity"] if f == "quantity" else
            old["warning_threshold"] if f == "warningThreshold" else
            old["description"]
        )
        if str(old_val) != str(new_data[f]):
            changes.append({"field": f, "label": label, "oldValue": old_val, "newValue": new_data[f]})

    if changes:
        add_log(code, new_data["name"], "edit", changes, user["username"], user["name"])
    return ok(None, "药材更新成功")


@app.route("/api/herbs/<code>", methods=["DELETE"])
def delete_herb(code):
    user, err = require_login()
    if err:
        return err
    if user["role"] == "patient":
        return fail("无权限：病人角色为只读，不能删除药材", code=403, http=403)

    old = query("SELECT * FROM herbs WHERE code = %s", (code,), one=True)
    if not old:
        return fail("药材不存在")
    execute("DELETE FROM herbs WHERE code = %s", (code,))
    delete_changes = [
        {"field": f, "label": label, "oldValue": v, "newValue": None}
        for f, label, v in [
            ("code", "编码", old["code"]), ("name", "药材名称", old["name"]),
            ("category", "类别", old["category"]), ("origin", "产地", old["origin"]),
            ("storage", "储存条件", old["storage"]), ("unit", "单位", old["unit"]),
            ("price", "单价", old["price"]), ("quantity", "库存数量", old["quantity"]),
            ("warningThreshold", "预警阈值", old["warning_threshold"]),
            ("description", "描述", old["description"]),
        ]
    ]
    add_log(code, old["name"], "delete", delete_changes, user["username"], user["name"])
    return ok(None, "药材删除成功")


@app.route("/api/herbs/<code>/adjust", methods=["POST"])
def adjust_herb(code):
    user, err = require_login()
    if err:
        return err
    if user["role"] == "patient":
        return fail("无权限：病人角色为只读，不能调整库存", code=403, http=403)

    d = request.get_json(silent=True) or {}
    try:
        amount = int(d.get("amount"))
    except (TypeError, ValueError):
        return fail("请输入调整数量")

    old = query("SELECT * FROM herbs WHERE code = %s", (code,), one=True)
    if not old:
        return fail("药材不存在")
    new_qty = old["quantity"] + amount
    if new_qty < 0:
        return fail("调整后库存不能为负数")

    execute("UPDATE herbs SET quantity = %s WHERE code = %s", (new_qty, code))
    add_log(code, old["name"], "edit", [
        {"field": "quantity", "label": "库存数量", "oldValue": old["quantity"], "newValue": new_qty}
    ], user["username"], user["name"])
    return ok({"code": code, "quantity": new_qty}, "库存调整成功")


# ============ 用户接口（仅管理员） ============
@app.route("/api/users", methods=["GET"])
def list_users():
    _, err = require_admin()
    if err:
        return err
    keyword = (request.args.get("keyword") or "").strip()
    role = (request.args.get("role") or "").strip()

    sql = "SELECT * FROM users WHERE 1=1"
    args = []
    if keyword:
        sql += " AND (username LIKE %s OR name LIKE %s)"
        like = f"%{keyword}%"
        args += [like, like]
    if role:
        sql += " AND role = %s"
        args.append(role)
    sql += " ORDER BY create_time DESC, username ASC"

    rows = query(sql, args)
    return ok([user_to_camel(r) for r in rows])


@app.route("/api/users", methods=["POST"])
def add_user():
    _, err = require_admin()
    if err:
        return err
    d = request.get_json(silent=True) or {}
    username = (d.get("username") or "").strip()
    password = d.get("password") or ""
    name = (d.get("name") or "").strip()
    role = d.get("role") or ""
    phone = (d.get("phone") or "").strip()
    status = d.get("status") or "active"

    if not username or not password or not name or not role:
        return fail("请填写所有必填字段")
    if role not in ("admin", "doctor", "patient"):
        return fail("角色不合法")
    if query("SELECT 1 FROM users WHERE username = %s", (username,), one=True):
        return fail("用户名已存在，请更换用户名")

    execute(
        """INSERT INTO users
           (username, password, role, name, phone, status,
            department, license, gender, age, create_time)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            username, sha256_pwd(password), role, name, phone, status,
            (d.get("department") or "").strip() if role == "doctor" else None,
            (d.get("license") or "").strip() if role == "doctor" else None,
            d.get("gender") if role == "patient" else None,
            d.get("age") if role == "patient" else None,
            time.strftime("%Y/%m/%d %H:%M:%S"),
        ),
    )
    return ok(None, "用户添加成功")


@app.route("/api/users/<username>", methods=["PUT"])
def update_user(username):
    _, err = require_admin()
    if err:
        return err
    old = query("SELECT * FROM users WHERE username = %s", (username,), one=True)
    if not old:
        return fail("用户不存在")

    d = request.get_json(silent=True) or {}
    new_pwd = d.get("password")
    if new_pwd:
        pwd = sha256_pwd(new_pwd)
    else:
        pwd = old["password"]

    role = d.get("role") or old["role"]
    if role not in ("admin", "doctor", "patient"):
        return fail("角色不合法")

    execute(
        """UPDATE users SET password=%s, role=%s, name=%s, phone=%s, status=%s,
           department=%s, license=%s, gender=%s, age=%s, idcard=%s
           WHERE username=%s""",
        (
            pwd, role,
            (d.get("name") or old["name"]).strip(),
            d.get("phone") if d.get("phone") is not None else old["phone"],
            d.get("status") or old["status"],
            (d.get("department") or "").strip() if role == "doctor" else (d.get("department") if d.get("department") is not None else old["department"]),
            (d.get("license") or "").strip() if role == "doctor" else (d.get("license") if d.get("license") is not None else old["license"]),
            d.get("gender") if role == "patient" else None,
            d.get("age") if role == "patient" else None,
            (d.get("idcard") or "").strip() if role == "patient" else None,
            username,
        ),
    )
    return ok(None, "用户更新成功")


@app.route("/api/users/<username>", methods=["DELETE"])
def delete_user(username):
    _, err = require_admin()
    if err:
        return err
    if username == "admin":
        return fail("不能删除系统内置管理员账号")
    affected = execute("DELETE FROM users WHERE username = %s", (username,))
    if not affected:
        return fail("用户不存在")
    return ok(None, "用户删除成功")


# ============ 日志接口（仅管理员） ============
@app.route("/api/logs", methods=["GET"])
def list_logs():
    _, err = require_admin()
    if err:
        return err

    herb = (request.args.get("herb") or "").strip()
    action = (request.args.get("action") or "").strip()
    time_filter = (request.args.get("time") or "").strip()
    keyword = (request.args.get("keyword") or "").strip()

    sql = "SELECT * FROM operation_logs WHERE 1=1"
    args = []
    if herb:
        sql += " AND herb_name = %s"
        args.append(herb)
    if action:
        sql += " AND action = %s"
        args.append(action)
    if time_filter:
        now = time.time() * 1000
        ranges = {
            "today": now - 24 * 3600 * 1000,
            "week": now - 7 * 24 * 3600 * 1000,
            "month": now - 30 * 24 * 3600 * 1000,
            "quarter": now - 90 * 24 * 3600 * 1000,
        }
        if time_filter in ranges:
            sql += " AND timestamp >= %s"
            args.append(ranges[time_filter])
    if keyword:
        like = f"%{keyword}%"
        sql += " AND (herb_name LIKE %s OR operator LIKE %s OR operator_name LIKE %s)"
        args += [like, like, like]
    sql += " ORDER BY timestamp DESC LIMIT 2000"

    rows = query(sql, args)
    return ok([log_to_camel(r) for r in rows])


# ============ 仪表盘统计 ============
@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    user, err = require_login()
    if err:
        return err

    herbs = query("SELECT * FROM herbs ORDER BY created_at DESC, code ASC")
    herb_list = [herb_to_camel(r) for r in herbs]

    total_quantity = sum(h["quantity"] or 0 for h in herb_list)
    low_stock = [h for h in herb_list if (h["quantity"] or 0) <= (h["warningThreshold"] or DEFAULT_WARNING_THRESHOLD)]

    return ok({
        "herbs": herb_list,
        "totalCount": len(herb_list),
        "totalQuantity": total_quantity,
        "lowStock": low_stock,
        "logs": [log_to_camel(r) for r in query(
            "SELECT * FROM operation_logs ORDER BY timestamp DESC LIMIT 500"
        )],
    })


FIELD_LABELS = {
    "name": "药材名称", "category": "类别", "origin": "产地", "storage": "储存条件",
    "unit": "单位", "price": "单价", "quantity": "库存数量", "description": "描述",
    "warningThreshold": "预警阈值",
}


if __name__ == "__main__":
    print("本草智管平台后端启动中 ...")
    print(f"前端目录: {os.path.abspath(FRONTEND_DIR)}")
    print("访问地址: http://127.0.0.1:5000")
    # host="0.0.0.0" 表示允许局域网/公网访问；仅本机访问可改回 "127.0.0.1"
    # 端口优先取环境变量 PORT（Railway/Render 等平台会自动注入），本机默认 5000
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
