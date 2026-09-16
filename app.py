import re
# -*- coding: utf-8 -*-
"""
本草智管平台 - 后端服务（Flask + MySQL）
4号模块：处方管理 + 数据看板

启动方式：
    cd backend
    python app.py
浏览器访问 http://127.0.0.1:5000
"""
import hashlib
import json
import os
import time

from flask import Flask, jsonify, request, send_from_directory

from db import execute, query, is_mysql

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 前端目录自适应：标准结构为 ../frontend；PaaS 平铺部署（HTML 与 app.py 同目录）时直接用 BASE_DIR
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")
if not os.path.isdir(FRONTEND_DIR):
    FRONTEND_DIR = BASE_DIR
DEFAULT_WARNING_THRESHOLD = 200

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")


# ============ 工具函数 ============
def sha256_pwd(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def ok(data=None, message="success"):
    return jsonify({"code": 0, "message": message, "data": data})


def fail(message, code=1, http=200):
    return jsonify({"code": code, "message": message, "data": None}), http


def get_current_user():
    username = request.headers.get("X-User", "").strip()
    if not username:
        return None
    return query("SELECT * FROM users WHERE username = %s", (username,), one=True)


def require_login():
    user = get_current_user()
    if not user:
        return None, fail("未登录或账号不存在", code=401, http=401)
    if user["status"] != "active":
        return None, fail("该账号已被禁用", code=403, http=403)
    return user, None


def require_admin():
    user, err = require_login()
    if err:
        return None, err
    if user["role"] != "admin":
        return None, fail("无权限：仅管理员可执行此操作", code=403, http=403)
    return user, None


def require_doctor_or_admin():
    user, err = require_login()
    if err:
        return None, err
    if user["role"] not in ("admin", "doctor"):
        return None, fail("无权限：仅医生或管理员可执行此操作", code=403, http=403)
    return user, None


def herb_to_camel(row):
    return {
        "code": row["code"], "name": row["name"], "category": row["category"],
        "origin": row["origin"], "storage": row["storage"], "unit": row["unit"],
        "price": float(row["price"]) if row["price"] is not None else None,
        "quantity": row["quantity"], "warningThreshold": row["warning_threshold"],
        "description": row["description"],
    }


def prescription_to_camel(row, items=None):
    return {
        "id": row["id"],
        "prescriptionNo": row["prescription_no"],
        "patientName": row["patient_name"],
        "patientPhone": row["patient_phone"],
        "patientGender": row["patient_gender"],
        "patientAge": row["patient_age"],
        "doctorUsername": row["doctor_username"],
        "doctorName": row["doctor_name"],
        "department": row["department"],
        "diagnosis": row["diagnosis"],
        "advice": row["advice"],
        "totalAmount": float(row["total_amount"]) if row["total_amount"] is not None else 0,
        "status": row["status"],
        "auditRemark": row["audit_remark"],
        "auditor": row["auditor"],
        "auditorName": row["auditor_name"],
        "auditTime": row["audit_time"],
        "dispenser": row["dispenser"],
        "dispenserName": row["dispenser_name"],
        "dispenseTime": row["dispense_time"],
        "createdAt": str(row["created_at"]) if row["created_at"] else None,
        "items": items or [],
    }


def item_to_camel(row):
    return {
        "id": row["id"],
        "herbCode": row["herb_code"],
        "herbName": row["herb_name"],
        "dosage": row["dosage"],
        "usage": row["usage"],
        "quantity": row["quantity"],
        "price": float(row["price"]) if row["price"] is not None else 0,
        "subtotal": float(row["subtotal"]) if row["subtotal"] is not None else 0,
    }


def add_log(herb_code, herb_name, action, changes, operator, operator_name):
    execute(
        """INSERT INTO operation_logs
           (herb_code, herb_name, action, changes, operator, operator_name, timestamp, time_str)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (herb_code, herb_name, action, json.dumps(changes, ensure_ascii=False, default=str),
         operator, operator_name, int(time.time() * 1000), time.strftime("%Y/%m/%d %H:%M:%S")),
    )


def add_stock_transaction(herb_code, herb_name, tx_type, quantity, reference_type=None,
                          reference_id=None, remark=None, operator=None, operator_name=None):
    """记录库存流水"""
    herb = query("SELECT quantity FROM herbs WHERE code = %s", (herb_code,), one=True)
    balance = herb["quantity"] if herb else 0
    execute(
        """INSERT INTO stock_transactions
           (herb_code, herb_name, type, quantity, balance_after, reference_type, reference_id,
            remark, operator, operator_name, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (herb_code, herb_name, tx_type, quantity, balance, reference_type, reference_id,
         remark, operator, operator_name, time.strftime("%Y/%m/%d %H:%M:%S")),
    )


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
    if user["status"] == "pending":
        return fail("账号正在审核中，请等待管理员审核通过后再登录")
    return ok({"username": user["username"], "role": user["role"], "name": user["name"], "phone": user["phone"]})


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
    if role not in ("doctor", "patient"):
        return fail("仅支持患者和医生注册，管理员请联系系统管理员创建")
    if role == "doctor":
        department = (data.get("department") or "").strip()
        license_no = (data.get("license") or "").strip()
        if not department or not license_no:
            return fail("医生注册需填写所属科室和执业医师证号")
    if query("SELECT 1 FROM users WHERE username = %s", (username,), one=True):
        return fail("用户名已存在")
    department = (data.get("department") or "").strip() if role == "doctor" else None
    license_no = (data.get("license") or "").strip() if role == "doctor" else None
    # 患者直接激活，医生待审核
    user_status = "active" if role == "patient" else "pending"
    execute(
        """INSERT INTO users (username, password, role, name, phone, status, department, license, gender, age, idcard, create_time)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (username, sha256_pwd(password), role, name, phone, user_status, department, license_no,
         data.get("gender"), data.get("age"), data.get("idcard"), time.strftime("%Y/%m/%d %H:%M:%S")),
    )
    if role == "patient":
        return ok(None, "注册成功，请使用账号登录")
    else:
        return ok(None, "注册成功，您的账号正在审核中，请等待管理员审核通过后再登录")


# ============ 药材接口 ============
@app.route("/api/herbs", methods=["GET"])
def list_herbs():
    user, err = require_login()
    if err:
        return err
    keyword = (request.args.get("q") or "").strip()
    if keyword:
        like = f"%{keyword}%"
        rows = query("""SELECT * FROM herbs WHERE name LIKE %s OR code LIKE %s OR category LIKE %s
                         ORDER BY created_at DESC, code ASC""", (like, like, like))
    else:
        rows = query("SELECT * FROM herbs ORDER BY created_at DESC, code ASC")
    return ok([herb_to_camel(r) for r in rows])


@app.route("/api/herbs", methods=["POST"])
def add_herb():
    user, err = require_login()
    if err:
        return err
    if user["role"] == "patient":
        return fail("无权限：病人角色为只读", code=403, http=403)
    d = request.get_json(silent=True) or {}
    code = (d.get("code") or "").strip()
    name = (d.get("name") or "").strip()
    if not code or not name:
        return fail("请填写药材编码和名称")
    if query("SELECT 1 FROM herbs WHERE code = %s", (code,), one=True):
        return fail("已存在相同编码的药材")
    execute(
        """INSERT INTO herbs (code, name, category, origin, storage, unit, price, quantity, warning_threshold, description)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (code, name, d.get("category"), d.get("origin"), d.get("storage"), d.get("unit"),
         d.get("price", 0), d.get("quantity", 0), d.get("warningThreshold", 200), d.get("description")),
    )
    return ok(None, "药材添加成功")


@app.route("/api/herbs/<code>", methods=["PUT"])
def update_herb(code):
    user, err = require_login()
    if err:
        return err
    if user["role"] == "patient":
        return fail("无权限：病人角色为只读", code=403, http=403)
    d = request.get_json(silent=True) or {}
    old = query("SELECT * FROM herbs WHERE code = %s", (code,), one=True)
    if not old:
        return fail("药材不存在")
    execute(
        """UPDATE herbs SET name=%s, category=%s, origin=%s, storage=%s, unit=%s,
           price=%s, quantity=%s, warning_threshold=%s, description=%s WHERE code=%s""",
        (d.get("name", old["name"]), d.get("category", old["category"]), d.get("origin", old["origin"]),
         d.get("storage", old["storage"]), d.get("unit", old["unit"]),
         d.get("price", old["price"]), d.get("quantity", old["quantity"]),
         d.get("warningThreshold", old["warning_threshold"]), d.get("description", old["description"]), code),
    )
    return ok(None, "药材更新成功")


@app.route("/api/herbs/<code>", methods=["DELETE"])
def delete_herb(code):
    user, err = require_login()
    if err:
        return err
    if user["role"] == "patient":
        return fail("无权限：病人角色为只读", code=403, http=403)
    old = query("SELECT * FROM herbs WHERE code = %s", (code,), one=True)
    if not old:
        return fail("药材不存在")
    execute("DELETE FROM herbs WHERE code = %s", (code,))
    return ok(None, "药材删除成功")


# ============ 用户接口 ============
@app.route("/api/users", methods=["GET"])
def list_users():
    _, err = require_admin()
    if err:
        return err
    rows = query("SELECT * FROM users ORDER BY create_time DESC")
    return ok([{
        "username": r["username"], "role": r["role"], "name": r["name"], "phone": r["phone"],
        "status": r["status"], "department": r["department"], "license": r["license"],
        "gender": r["gender"], "age": r["age"], "createTime": r["create_time"],
    } for r in rows])


@app.route("/api/users/pending", methods=["GET"])
def list_pending_users():
    _, err = require_admin()
    if err:
        return err
    rows = query("SELECT * FROM users WHERE status = 'pending' ORDER BY create_time DESC")
    return ok([{
        "username": r["username"], "role": r["role"], "name": r["name"], "phone": r["phone"],
        "status": r["status"], "department": r["department"], "license": r["license"],
        "gender": r["gender"], "age": r["age"], "createTime": r["create_time"],
    } for r in rows])


@app.route("/api/users/<username>/approve", methods=["POST"])
def approve_user(username):
    _, err = require_admin()
    if err:
        return err
    user = query("SELECT * FROM users WHERE username = %s", (username,), one=True)
    if not user:
        return fail("用户不存在")
    if user["status"] != "pending":
        return fail("该用户不是待审核状态")
    execute("UPDATE users SET status = 'active' WHERE username = %s", (username,))
    return ok(None, "审核通过，用户已激活")


@app.route("/api/users/<username>/reject", methods=["POST"])
def reject_user(username):
    _, err = require_admin()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    user = query("SELECT * FROM users WHERE username = %s", (username,), one=True)
    if not user:
        return fail("用户不存在")
    if user["status"] != "pending":
        return fail("该用户不是待审核状态")
    # 拒绝后删除用户（或改为inactive，这里选择删除避免垃圾数据）
    execute("DELETE FROM users WHERE username = %s", (username,))
    return ok(None, "已拒绝该注册申请" + (f"，原因：{reason}" if reason else ""))


@app.route("/api/users/<username>/toggle-status", methods=["POST"])
def toggle_user_status(username):
    _, err = require_admin()
    if err:
        return err
    user = query("SELECT * FROM users WHERE username = %s", (username,), one=True)
    if not user:
        return fail("用户不存在")
    if user["role"] == "admin" and user["username"] == "admin":
        return fail("不能禁用超级管理员账号")
    new_status = "inactive" if user["status"] == "active" else "active"
    execute("UPDATE users SET status = %s WHERE username = %s", (new_status, username))
    return ok({"status": new_status}, "已" + ("禁用" if new_status == "inactive" else "启用") + "该账号")


# ============ 日志接口 ============
@app.route("/api/logs", methods=["GET"])
def list_logs():
    _, err = require_admin()
    if err:
        return err
    rows = query("SELECT * FROM operation_logs ORDER BY timestamp DESC LIMIT 500")
    return ok([{
        "id": f"log_{r['id']}", "herbCode": r["herb_code"], "herbName": r["herb_name"],
        "action": r["action"], "operator": r["operator"], "operatorName": r["operator_name"],
        "timestamp": r["timestamp"], "timeStr": r["time_str"],
    } for r in rows])


# ============ 仪表盘 ============
@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    user, err = require_login()
    if err:
        return err
    herbs = query("SELECT * FROM herbs ORDER BY created_at DESC")
    herb_list = [herb_to_camel(r) for r in herbs]
    total_quantity = sum(h["quantity"] or 0 for h in herb_list)
    low_stock = [h for h in herb_list if (h["quantity"] or 0) <= (h["warningThreshold"] or 200)]
    return ok({
        "herbs": herb_list, "totalCount": len(herb_list),
        "totalQuantity": total_quantity, "lowStock": low_stock,
    })


# ============ 处方接口（4号核心） ============
STATUS_MAP = {"pending": "待审核", "approved": "已审核", "rejected": "已拒绝", "dispensed": "已发药"}


@app.route("/api/prescriptions", methods=["GET"])
def list_prescriptions():
    user, err = require_login()
    if err:
        return err
    status = (request.args.get("status") or "").strip()
    keyword = (request.args.get("keyword") or "").strip()
    doctor = (request.args.get("doctor") or "").strip()

    sql = "SELECT * FROM prescriptions WHERE 1=1"
    args = []
    if status and status in STATUS_MAP:
        sql += " AND status = %s"
        args.append(status)
    if keyword:
        like = f"%{keyword}%"
        sql += " AND (patient_name LIKE %s OR prescription_no LIKE %s OR diagnosis LIKE %s)"
        args += [like, like, like]
    # 医生只能看自己的处方
    if user["role"] == "doctor":
        sql += " AND doctor_username = %s"
        args.append(user["username"])
    elif doctor:
        sql += " AND doctor_username = %s"
        args.append(doctor)
    sql += " ORDER BY created_at DESC LIMIT 200"

    rows = query(sql, args)
    result = []
    for r in rows:
        items = query("SELECT * FROM prescription_items WHERE prescription_id = %s ORDER BY id", (r["id"],))
        result.append(prescription_to_camel(r, [item_to_camel(i) for i in items]))
    return ok(result)


@app.route("/api/prescriptions/<int:rx_id>", methods=["GET"])
def get_prescription(rx_id):
    user, err = require_login()
    if err:
        return err
    row = query("SELECT * FROM prescriptions WHERE id = %s", (rx_id,), one=True)
    if not row:
        return fail("处方不存在")
    if user["role"] == "doctor" and row["doctor_username"] != user["username"]:
        return fail("无权限查看他人处方", code=403, http=403)
    items = query("SELECT * FROM prescription_items WHERE prescription_id = %s ORDER BY id", (rx_id,))
    return ok(prescription_to_camel(row, [item_to_camel(i) for i in items]))


@app.route("/api/prescriptions", methods=["POST"])
def create_prescription():
    user, err = require_doctor_or_admin()
    if err:
        return err
    d = request.get_json(silent=True) or {}
    patient_name = (d.get("patientName") or "").strip()
    items = d.get("items") or []
    if not patient_name:
        return fail("请填写患者姓名")
    if not items or len(items) == 0:
        return fail("请至少添加一味药材")

    # 生成处方编号
    rx_no = "RX" + time.strftime("%Y%m%d%H%M%S")
    total = 0
    for item in items:
        try:
            dosage_val = float(str(item.get("dosage", "0")).replace("g", "").replace("G", ""))
        except (ValueError, TypeError):
            dosage_val = 0
        qty = int(item.get("quantity", 1))
        price = float(item.get("price", 0))
        total += dosage_val * qty * price

    _, rx_id = execute(
        """INSERT INTO prescriptions
           (prescription_no, patient_name, patient_phone, patient_gender, patient_age,
            doctor_username, doctor_name, department, diagnosis, advice, total_amount, status)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending')""",
        (rx_no, patient_name, d.get("patientPhone"), d.get("patientGender"), d.get("patientAge"),
         user["username"], user["name"], d.get("department") or user.get("department"),
         d.get("diagnosis"), d.get("advice"), round(total, 2)),
    )
    for item in items:
        try:
            dosage_val = float(str(item.get("dosage", "0")).replace("g", "").replace("G", ""))
        except (ValueError, TypeError):
            dosage_val = 0
        qty = int(item.get("quantity", 1))
        price = float(item.get("price", 0))
        subtotal = round(dosage_val * qty * price, 2)
        execute(
            """INSERT INTO prescription_items
               (prescription_id, herb_code, herb_name, dosage, `usage`, quantity, price, subtotal)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (rx_id, item.get("herbCode"), item.get("herbName"), item.get("dosage"),
             item.get("usage"), qty, price, subtotal),
        )
    return ok({"id": rx_id, "prescriptionNo": rx_no}, "处方创建成功，等待审核")


@app.route("/api/prescriptions/<int:rx_id>/audit", methods=["PUT"])
def audit_prescription(rx_id):
    user, err = require_admin()
    if err:
        return err
    d = request.get_json(silent=True) or {}
    action = (d.get("action") or "").strip()  # approve / reject
    remark = (d.get("remark") or "").strip()
    if action not in ("approve", "reject"):
        return fail("审核操作不合法")
    row = query("SELECT * FROM prescriptions WHERE id = %s", (rx_id,), one=True)
    if not row:
        return fail("处方不存在")
    if row["status"] != "pending":
        return fail("该处方已审核，不能重复审核")
    new_status = "approved" if action == "approve" else "rejected"
    execute(
        "UPDATE prescriptions SET status=%s, audit_remark=%s, auditor=%s, auditor_name=%s, audit_time=%s WHERE id=%s",
        (new_status, remark, user["username"], user["name"], time.strftime("%Y/%m/%d %H:%M:%S"), rx_id),
    )
    return ok(None, f"处方已{'通过' if action == 'approve' else '拒绝'}")


@app.route("/api/prescriptions/<int:rx_id>/dispense", methods=["PUT"])
def dispense_prescription(rx_id):
    user, err = require_login()
    if err:
        return err
    if user["role"] == "patient":
        return fail("无权限：病人不能发药", code=403, http=403)
    row = query("SELECT * FROM prescriptions WHERE id = %s", (rx_id,), one=True)
    if not row:
        return fail("处方不存在")
    if row["status"] != "approved":
        return fail("只有已审核的处方才能发药")
    items = query("SELECT * FROM prescription_items WHERE prescription_id = %s", (rx_id,))
    # 扣减库存
    for item in items:
        herb = query("SELECT * FROM herbs WHERE code = %s", (item["herb_code"],), one=True)
        if herb:
            try:
                dosage_val = float(str(item["dosage"]).replace("g", ""))
            except (ValueError, TypeError):
                dosage_val = 0
            deduct = int(dosage_val * item["quantity"])
            new_qty = max(0, herb["quantity"] - deduct)
            execute("UPDATE herbs SET quantity=%s WHERE code=%s", (new_qty, item["herb_code"]))
            add_stock_transaction(
                item["herb_code"], item["herb_name"], "out", -deduct,
                reference_type="prescription", reference_id=str(rx_id),
                remark=f"处方发药扣减: {row['prescription_no']}",
                operator=user["username"], operator_name=user["name"]
            )
    execute(
        "UPDATE prescriptions SET status='dispensed', dispenser=%s, dispenser_name=%s, dispense_time=%s WHERE id=%s",
        (user["username"], user["name"], time.strftime("%Y/%m/%d %H:%M:%S"), rx_id),
    )
    return ok(None, "处方发药成功，库存已扣减")


@app.route("/api/prescriptions/<int:rx_id>", methods=["DELETE"])
def delete_prescription(rx_id):
    user, err = require_admin()
    if err:
        return err
    row = query("SELECT * FROM prescriptions WHERE id = %s", (rx_id,), one=True)
    if not row:
        return fail("处方不存在")
    if row["status"] == "dispensed":
        return fail("已发药的处方不能删除")
    execute("DELETE FROM prescription_items WHERE prescription_id = %s", (rx_id,))
    execute("DELETE FROM prescriptions WHERE id = %s", (rx_id,))
    return ok(None, "处方删除成功")


# ============ 数据统计接口（4号核心 - ECharts数据看板） ============
@app.route("/api/stats/overview", methods=["GET"])
def stats_overview():
    user, err = require_login()
    if err:
        return err
    # 处方统计
    total_rx = query("SELECT COUNT(*) as cnt FROM prescriptions", one=True)["cnt"]
    pending_rx = query("SELECT COUNT(*) as cnt FROM prescriptions WHERE status='pending'", one=True)["cnt"]
    approved_rx = query("SELECT COUNT(*) as cnt FROM prescriptions WHERE status='approved'", one=True)["cnt"]
    dispensed_rx = query("SELECT COUNT(*) as cnt FROM prescriptions WHERE status='dispensed'", one=True)["cnt"]
    rejected_rx = query("SELECT COUNT(*) as cnt FROM prescriptions WHERE status='rejected'", one=True)["cnt"]
    total_amount = query("SELECT COALESCE(SUM(total_amount),0) as amt FROM prescriptions WHERE status IN ('approved','dispensed')", one=True)["amt"]

    # 药材统计
    total_herbs = query("SELECT COUNT(*) as cnt FROM herbs", one=True)["cnt"]
    total_stock = query("SELECT COALESCE(SUM(quantity),0) as qty FROM herbs", one=True)["qty"]
    low_stock = query("SELECT COUNT(*) as cnt FROM herbs WHERE quantity <= warning_threshold", one=True)["cnt"]

    # 用户统计
    total_users = query("SELECT COUNT(*) as cnt FROM users", one=True)["cnt"]
    doctor_count = query("SELECT COUNT(*) as cnt FROM users WHERE role='doctor'", one=True)["cnt"]

    return ok({
        "prescriptions": {"total": total_rx, "pending": pending_rx, "approved": approved_rx,
                           "dispensed": dispensed_rx, "rejected": rejected_rx,
                           "totalAmount": float(total_amount)},
        "herbs": {"total": total_herbs, "totalStock": total_stock, "lowStock": low_stock},
        "users": {"total": total_users, "doctors": doctor_count},
    })


@app.route("/api/stats/prescription-trend", methods=["GET"])
def stats_prescription_trend():
    user, err = require_login()
    if err:
        return err
    days = int(request.args.get("days", 7))
    import datetime
    today = datetime.date.today()
    start_date = (today - datetime.timedelta(days=days - 1)).strftime("%Y-%m-%d")
    # 兼容 MySQL 和 SQLite：用日期字符串比较
    rows = query("""
        SELECT DATE(created_at) as dt, COUNT(*) as cnt, COALESCE(SUM(total_amount),0) as amt
        FROM prescriptions
        WHERE DATE(created_at) >= %s
        GROUP BY DATE(created_at)
        ORDER BY dt ASC
    """, (start_date,))
    date_map = {str(r["dt"]): {"count": r["cnt"], "amount": float(r["amt"])} for r in rows}
    import datetime
    dates = []
    counts = []
    amounts = []
    today = datetime.date.today()
    for i in range(days - 1, -1, -1):
        d = today - datetime.timedelta(days=i)
        ds = d.strftime("%Y-%m-%d")
        dates.append(ds)
        counts.append(date_map.get(ds, {}).get("count", 0))
        amounts.append(round(date_map.get(ds, {}).get("amount", 0), 2))
    return ok({"dates": dates, "counts": counts, "amounts": amounts})


@app.route("/api/stats/status-distribution", methods=["GET"])
def stats_status_distribution():
    user, err = require_login()
    if err:
        return err
    rows = query("SELECT status, COUNT(*) as cnt FROM prescriptions GROUP BY status")
    return ok([{"name": STATUS_MAP.get(r["status"], r["status"]), "value": r["cnt"]} for r in rows])


@app.route("/api/stats/herb-consumption", methods=["GET"])
def stats_herb_consumption():
    user, err = require_login()
    if err:
        return err
    # 已发药处方中的药材消耗排行
    rows = query("""
        SELECT pi.herb_name, SUM(CAST(REPLACE(pi.dosage,'g','') AS REAL) * pi.quantity) as total_usage
        FROM prescription_items pi
        JOIN prescriptions p ON pi.prescription_id = p.id
        WHERE p.status = 'dispensed'
        GROUP BY pi.herb_name
        ORDER BY total_usage DESC
        LIMIT 10
    """)
    return ok([{"name": r["herb_name"], "value": float(r["total_usage"])} for r in rows])


@app.route("/api/stats/doctor-workload", methods=["GET"])
def stats_doctor_workload():
    user, err = require_login()
    if err:
        return err
    rows = query("""
        SELECT doctor_name, COUNT(*) as cnt, COALESCE(SUM(total_amount),0) as amt
        FROM prescriptions
        WHERE doctor_name IS NOT NULL
        GROUP BY doctor_name
        ORDER BY cnt DESC
    """)
    return ok([{"name": r["doctor_name"], "count": r["cnt"], "amount": float(r["amt"])} for r in rows])


@app.route("/api/stats/category-distribution", methods=["GET"])
def stats_category_distribution():
    user, err = require_login()
    if err:
        return err
    rows = query("""
        SELECT category, COUNT(*) as cnt, COALESCE(SUM(quantity),0) as qty
        FROM herbs
        WHERE category IS NOT NULL AND category != ''
        GROUP BY category
        ORDER BY cnt DESC
    """)
    return ok([{"name": r["category"], "count": r["cnt"], "stock": r["qty"]} for r in rows])


# ============ 供应商管理 API ============
@app.route("/api/suppliers", methods=["GET"])
def list_suppliers():
    user, err = require_login()
    if err:
        return err
    keyword = (request.args.get("q") or "").strip()
    if keyword:
        like = f"%{keyword}%"
        rows = query("SELECT * FROM suppliers WHERE name LIKE %s OR contact_person LIKE %s ORDER BY id DESC", (like, like))
    else:
        rows = query("SELECT * FROM suppliers ORDER BY id DESC")
    return ok([{
        "id": r["id"], "name": r["name"], "contactPerson": r["contact_person"],
        "phone": r["phone"], "address": r["address"], "description": r["description"],
        "status": r["status"], "createdAt": str(r["created_at"]) if r["created_at"] else None,
    } for r in rows])


@app.route("/api/suppliers", methods=["POST"])
def add_supplier():
    user, err = require_admin()
    if err:
        return err
    d = request.get_json(silent=True) or {}
    name = (d.get("name") or "").strip()
    if not name:
        return fail("请填写供应商名称")
    execute(
        """INSERT INTO suppliers (name,contact_person,phone,address,description,status)
           VALUES (%s,%s,%s,%s,%s,%s)""",
        (name, d.get("contactPerson"), d.get("phone"), d.get("address"),
         d.get("description"), d.get("status", "active"))
    )
    return ok(None, "供应商添加成功")


@app.route("/api/suppliers/<int:sid>", methods=["PUT"])
def update_supplier(sid):
    user, err = require_admin()
    if err:
        return err
    d = request.get_json(silent=True) or {}
    old = query("SELECT * FROM suppliers WHERE id = %s", (sid,), one=True)
    if not old:
        return fail("供应商不存在")
    execute(
        """UPDATE suppliers SET name=%s, contact_person=%s, phone=%s, address=%s,
           description=%s, status=%s WHERE id=%s""",
        (d.get("name", old["name"]), d.get("contactPerson", old["contact_person"]),
         d.get("phone", old["phone"]), d.get("address", old["address"]),
         d.get("description", old["description"]), d.get("status", old["status"]), sid)
    )
    return ok(None, "供应商更新成功")


@app.route("/api/suppliers/<int:sid>", methods=["DELETE"])
def delete_supplier(sid):
    user, err = require_admin()
    if err:
        return err
    execute("DELETE FROM suppliers WHERE id = %s", (sid,))
    return ok(None, "供应商删除成功")


# ============ 采购管理 API ============
PO_STATUS_MAP = {"pending": "待审核", "approved": "已审核", "completed": "已入库", "rejected": "已拒绝", "cancelled": "已取消"}


@app.route("/api/purchase-orders", methods=["GET"])
def list_purchase_orders():
    user, err = require_login()
    if err:
        return err
    status = (request.args.get("status") or "").strip()
    keyword = (request.args.get("keyword") or "").strip()
    sql = "SELECT * FROM purchase_orders WHERE 1=1"
    args = []
    if status and status in PO_STATUS_MAP:
        sql += " AND status = %s"
        args.append(status)
    if keyword:
        like = f"%{keyword}%"
        sql += " AND (order_no LIKE %s OR supplier_name LIKE %s)"
        args += [like, like]
    sql += " ORDER BY created_at DESC LIMIT 200"
    rows = query(sql, args)
    result = []
    for r in rows:
        items = query("SELECT * FROM purchase_items WHERE purchase_id = %s ORDER BY id", (r["id"],))
        result.append({
            "id": r["id"], "orderNo": r["order_no"], "supplierId": r["supplier_id"],
            "supplierName": r["supplier_name"], "totalAmount": float(r["total_amount"]) if r["total_amount"] else 0,
            "status": r["status"], "statusText": PO_STATUS_MAP.get(r["status"], r["status"]),
            "remark": r["remark"], "creator": r["creator"], "creatorName": r["creator_name"],
            "auditor": r["auditor"], "auditorName": r["auditor_name"], "auditTime": r["audit_time"],
            "inStockTime": r["in_stock_time"], "createdAt": str(r["created_at"]) if r["created_at"] else None,
            "items": [{
                "id": i["id"], "herbCode": i["herb_code"], "herbName": i["herb_name"],
                "quantity": i["quantity"], "unit": i["unit"], "price": float(i["price"]) if i["price"] else 0,
                "subtotal": float(i["subtotal"]) if i["subtotal"] else 0,
                "receivedQuantity": i["received_quantity"],
            } for i in items],
        })
    return ok(result)


@app.route("/api/purchase-orders/<int:po_id>", methods=["GET"])
def get_purchase_order(po_id):
    user, err = require_login()
    if err:
        return err
    row = query("SELECT * FROM purchase_orders WHERE id = %s", (po_id,), one=True)
    if not row:
        return fail("采购单不存在")
    items = query("SELECT * FROM purchase_items WHERE purchase_id = %s ORDER BY id", (po_id,))
    return ok({
        "id": row["id"], "orderNo": row["order_no"], "supplierId": row["supplier_id"],
        "supplierName": row["supplier_name"], "totalAmount": float(row["total_amount"]) if row["total_amount"] else 0,
        "status": row["status"], "statusText": PO_STATUS_MAP.get(row["status"], row["status"]),
        "remark": row["remark"], "creator": row["creator"], "creatorName": row["creator_name"],
        "auditor": row["auditor"], "auditorName": row["auditor_name"], "auditTime": row["audit_time"],
        "inStockTime": row["in_stock_time"], "createdAt": str(row["created_at"]) if row["created_at"] else None,
        "items": [{
            "id": i["id"], "herbCode": i["herb_code"], "herbName": i["herb_name"],
            "quantity": i["quantity"], "unit": i["unit"], "price": float(i["price"]) if i["price"] else 0,
            "subtotal": float(i["subtotal"]) if i["subtotal"] else 0,
            "receivedQuantity": i["received_quantity"],
        } for i in items],
    })


@app.route("/api/purchase-orders", methods=["POST"])
def create_purchase_order():
    user, err = require_login()
    if err:
        return err
    if user["role"] == "patient":
        return fail("无权限：病人不能创建采购单", code=403, http=403)
    d = request.get_json(silent=True) or {}
    items = d.get("items") or []
    supplier_id = d.get("supplierId")
    supplier_name = d.get("supplierName") or ""
    if not items or len(items) == 0:
        return fail("请至少添加一味药材")
    if not supplier_name and not supplier_id:
        return fail("请选择供应商")
    if supplier_id and not supplier_name:
        sup = query("SELECT name FROM suppliers WHERE id = %s", (supplier_id,), one=True)
        supplier_name = sup["name"] if sup else ""

    po_no = "PO" + time.strftime("%Y%m%d%H%M%S")
    total = 0
    for item in items:
        total += float(item.get("quantity", 0)) * float(item.get("price", 0))

    _, po_id = execute(
        """INSERT INTO purchase_orders
           (order_no,supplier_id,supplier_name,total_amount,status,remark,creator,creator_name)
           VALUES (%s,%s,%s,%s,'pending',%s,%s,%s)""",
        (po_no, supplier_id, supplier_name, round(total, 2), d.get("remark"),
         user["username"], user["name"])
    )
    for item in items:
        qty = int(item.get("quantity", 0))
        price = float(item.get("price", 0))
        subtotal = round(qty * price, 2)
        execute(
            """INSERT INTO purchase_items
               (purchase_id,herb_code,herb_name,quantity,unit,price,subtotal,received_quantity)
               VALUES (%s,%s,%s,%s,%s,%s,%s,0)""",
            (po_id, item.get("herbCode"), item.get("herbName"), qty,
             item.get("unit", "g"), price, subtotal)
        )
    return ok({"id": po_id, "orderNo": po_no}, "采购单创建成功，等待审核")


@app.route("/api/purchase-orders/<int:po_id>/audit", methods=["PUT"])
def audit_purchase_order(po_id):
    user, err = require_admin()
    if err:
        return err
    d = request.get_json(silent=True) or {}
    action = (d.get("action") or "").strip()
    if action not in ("approve", "reject"):
        return fail("审核操作不合法")
    row = query("SELECT * FROM purchase_orders WHERE id = %s", (po_id,), one=True)
    if not row:
        return fail("采购单不存在")
    if row["status"] != "pending":
        return fail("该采购单已审核，不能重复审核")
    new_status = "approved" if action == "approve" else "rejected"
    execute(
        "UPDATE purchase_orders SET status=%s, auditor=%s, auditor_name=%s, audit_time=%s WHERE id=%s",
        (new_status, user["username"], user["name"], time.strftime("%Y/%m/%d %H:%M:%S"), po_id)
    )
    return ok(None, f"采购单已{'通过' if action == 'approve' else '拒绝'}")


@app.route("/api/purchase-orders/<int:po_id>/in-stock", methods=["PUT"])
def purchase_order_in_stock(po_id):
    user, err = require_login()
    if err:
        return err
    if user["role"] == "patient":
        return fail("无权限：病人不能执行入库", code=403, http=403)
    row = query("SELECT * FROM purchase_orders WHERE id = %s", (po_id,), one=True)
    if not row:
        return fail("采购单不存在")
    if row["status"] != "approved":
        return fail("只有已审核的采购单才能入库")
    items = query("SELECT * FROM purchase_items WHERE purchase_id = %s", (po_id,))
    # 入库：增加库存
    for item in items:
        herb = query("SELECT * FROM herbs WHERE code = %s", (item["herb_code"],), one=True)
        if herb:
            new_qty = herb["quantity"] + item["quantity"]
            execute("UPDATE herbs SET quantity=%s WHERE code=%s", (new_qty, item["herb_code"]))
            add_stock_transaction(
                item["herb_code"], item["herb_name"], "in", item["quantity"],
                reference_type="purchase", reference_id=str(po_id),
                remark=f"采购入库: {row['order_no']}",
                operator=user["username"], operator_name=user["name"]
            )
        execute("UPDATE purchase_items SET received_quantity = %s WHERE id = %s",
                (item["quantity"], item["id"]))
    execute(
        "UPDATE purchase_orders SET status='completed', in_stock_time=%s WHERE id=%s",
        (time.strftime("%Y/%m/%d %H:%M:%S"), po_id)
    )
    return ok(None, "采购入库成功，库存已更新")


@app.route("/api/purchase-orders/<int:po_id>", methods=["DELETE"])
def delete_purchase_order(po_id):
    user, err = require_admin()
    if err:
        return err
    row = query("SELECT * FROM purchase_orders WHERE id = %s", (po_id,), one=True)
    if not row:
        return fail("采购单不存在")
    if row["status"] == "completed":
        return fail("已入库的采购单不能删除")
    execute("DELETE FROM purchase_items WHERE purchase_id = %s", (po_id,))
    execute("DELETE FROM purchase_orders WHERE id = %s", (po_id,))
    return ok(None, "采购单删除成功")


# ============ 库存流水 API ============
@app.route("/api/stock-transactions", methods=["GET"])
def list_stock_transactions():
    user, err = require_login()
    if err:
        return err
    herb_code = (request.args.get("herbCode") or "").strip()
    tx_type = (request.args.get("type") or "").strip()
    sql = "SELECT * FROM stock_transactions WHERE 1=1"
    args = []
    if herb_code:
        sql += " AND herb_code = %s"
        args.append(herb_code)
    if tx_type:
        sql += " AND type = %s"
        args.append(tx_type)
    sql += " ORDER BY created_at DESC LIMIT 500"
    rows = query(sql, args)
    return ok([{
        "id": r["id"], "herbCode": r["herb_code"], "herbName": r["herb_name"],
        "type": r["type"], "typeText": "入库" if r["type"] == "in" else "出库" if r["type"] == "out" else r["type"],
        "quantity": r["quantity"], "balanceAfter": r["balance_after"],
        "referenceType": r["reference_type"], "referenceId": r["reference_id"],
        "remark": r["remark"], "operator": r["operator"], "operatorName": r["operator_name"],
        "createdAt": str(r["created_at"]) if r["created_at"] else None,
    } for r in rows])


# ============ 库存预警 API ============
@app.route("/api/stock/warnings", methods=["GET"])
def stock_warnings():
    user, err = require_login()
    if err:
        return err
    rows = query("""
        SELECT * FROM herbs
        WHERE quantity <= warning_threshold
        ORDER BY (quantity * 1.0 / warning_threshold) ASC
    """)
    return ok([{
        "code": r["code"], "name": r["name"], "category": r["category"],
        "quantity": r["quantity"], "warningThreshold": r["warning_threshold"],
        "unit": r["unit"], "price": float(r["price"]) if r["price"] else 0,
        "shortage": max(0, r["warning_threshold"] - r["quantity"]),
        "status": "critical" if r["quantity"] == 0 else "warning",
    } for r in rows])


# ============ 智能补货推荐 API ============
@app.route("/api/stock/replenish-suggestions", methods=["GET"])
def replenish_suggestions():
    user, err = require_login()
    if err:
        return err
    days = int(request.args.get("days", 30))
    # 基于历史消耗计算日均消耗量
    import datetime
    start_date = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")

    # 获取所有药材
    herbs = query("SELECT * FROM herbs ORDER BY code")
    suggestions = []

    for herb in herbs:
        # 统计该药材在指定时间段内的消耗量（从已发药处方中计算）
        rows = query("""
            SELECT COALESCE(SUM(CAST(REPLACE(pi.dosage,'g','') AS REAL) * pi.quantity), 0) as total_usage
            FROM prescription_items pi
            JOIN prescriptions p ON pi.prescription_id = p.id
            WHERE p.status = 'dispensed'
              AND pi.herb_code = %s
              AND DATE(p.dispense_time) >= %s
        """, (herb["code"], start_date))
        total_usage = float(rows[0]["total_usage"]) if rows else 0
        daily_avg = round(total_usage / days, 1) if days > 0 else 0

        # 计算可维持天数
        days_remaining = round(herb["quantity"] / daily_avg, 1) if daily_avg > 0 else 999

        # 建议补货量 = 30天消耗量 - 当前库存（如果为正）
        suggest_qty = max(0, int(daily_avg * 30) - herb["quantity"])

        # 优先级判断
        if herb["quantity"] <= 0:
            priority = "critical"
        elif days_remaining <= 7:
            priority = "high"
        elif days_remaining <= 15:
            priority = "medium"
        elif suggest_qty > 0:
            priority = "low"
        else:
            continue

        suggestions.append({
            "code": herb["code"], "name": herb["name"], "category": herb["category"],
            "currentStock": herb["quantity"], "warningThreshold": herb["warning_threshold"],
            "dailyAvgUsage": daily_avg, "daysRemaining": days_remaining,
            "suggestedQuantity": suggest_qty, "unit": herb["unit"],
            "price": float(herb["price"]) if herb["price"] else 0,
            "estimatedCost": round(suggest_qty * float(herb["price"] or 0), 2),
            "priority": priority,
        })

    # 按优先级排序
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    suggestions.sort(key=lambda x: (priority_order.get(x["priority"], 9), x["daysRemaining"]))

    return ok({
        "days": days,
        "totalSuggestions": len(suggestions),
        "totalEstimatedCost": round(sum(s["estimatedCost"] for s in suggestions), 2),
        "items": suggestions,
    })


# ============ 采购统计 API ============
@app.route("/api/stats/purchase-overview", methods=["GET"])
def stats_purchase_overview():
    user, err = require_login()
    if err:
        return err
    total_po = query("SELECT COUNT(*) as cnt FROM purchase_orders", one=True)["cnt"]
    pending_po = query("SELECT COUNT(*) as cnt FROM purchase_orders WHERE status='pending'", one=True)["cnt"]
    completed_po = query("SELECT COUNT(*) as cnt FROM purchase_orders WHERE status='completed'", one=True)["cnt"]
    total_amount = query("SELECT COALESCE(SUM(total_amount),0) as amt FROM purchase_orders WHERE status='completed'", one=True)["amt"]
    total_in = query("SELECT COALESCE(SUM(quantity),0) as qty FROM stock_transactions WHERE type='in'", one=True)["qty"]
    total_out = query("SELECT COALESCE(SUM(ABS(quantity)),0) as qty FROM stock_transactions WHERE type='out'", one=True)["qty"]
    return ok({
        "purchaseOrders": {"total": total_po, "pending": pending_po, "completed": completed_po,
                           "totalAmount": float(total_amount)},
        "stockFlow": {"totalIn": total_in, "totalOut": total_out},
    })


# ============ 智能诊疗助手 API ============

# 症状关键词映射（用于症状咨询）
SYMPTOM_MAP = {
    "感冒": {"keywords": ["感冒", "着凉", "伤风", "流鼻涕", "鼻塞", "打喷嚏"],
             "herbs": ["柴胡", "黄芩", "甘草"], "formulas": ["小柴胡汤"],
             "advice": "感冒初期可多饮温水，注意休息。若症状持续或加重，请及时就医。"},
    "咳嗽": {"keywords": ["咳嗽", "干咳", "咳痰", "止咳"],
             "herbs": ["甘草", "黄芩"], "formulas": [],
             "advice": "咳嗽期间避免辛辣刺激食物，保持室内空气湿润。久咳不愈请就医检查。"},
    "失眠": {"keywords": ["失眠", "睡不着", "睡眠差", "多梦", "易醒"],
             "herbs": ["茯苓", "白芍"], "formulas": ["逍遥散"],
             "advice": "睡前避免使用电子设备，可尝试温水泡脚。长期失眠建议就医调理。"},
    "消化不良": {"keywords": ["消化不良", "胃胀", "腹胀", "食少", "食欲不振", "没胃口"],
                 "herbs": ["白术", "茯苓", "党参", "甘草"], "formulas": ["四君子汤"],
                 "advice": "饮食宜清淡易消化，少食多餐，避免生冷油腻。"},
    "乏力": {"keywords": ["乏力", "疲劳", "没力气", "精神差", "倦怠", "气虚"],
             "herbs": ["黄芪", "党参", "白术", "甘草"], "formulas": ["四君子汤", "补中益气汤"],
             "advice": "注意休息，避免过度劳累，适当补充营养。持续乏力建议体检排查。"},
    "月经不调": {"keywords": ["月经不调", "经期不准", "痛经", "月经量少", "闭经"],
                 "herbs": ["当归", "川芎", "白芍", "柴胡"], "formulas": ["四物汤", "逍遥散"],
                 "advice": "经期注意保暖，避免生冷食物和剧烈运动。建议妇科就诊调理。"},
    "头晕": {"keywords": ["头晕", "眩晕", "头昏", "头疼", "头痛"],
             "herbs": ["当归", "白芍", "川芎", "柴胡"], "formulas": ["四物汤", "逍遥散"],
             "advice": "头晕时注意休息，避免突然起身。频繁头晕建议测量血压并就医。"},
    "出汗多": {"keywords": ["出汗多", "自汗", "盗汗", "容易出汗"],
               "herbs": ["黄芪", "白术", "白芍"], "formulas": ["玉屏风散"],
               "advice": "注意补充水分和电解质，避免高温环境。异常出汗建议就医排查。"},
    "便秘": {"keywords": ["便秘", "大便干", "排便困难"],
             "herbs": ["当归", "白术"], "formulas": [],
             "advice": "多吃蔬菜水果，增加膳食纤维，适量运动，养成规律排便习惯。"},
    "水肿": {"keywords": ["水肿", "浮肿", "腿肿", "脸肿"],
             "herbs": ["茯苓", "白术"], "formulas": ["五苓散"],
             "advice": "减少盐分摄入，避免久站久坐。持续水肿建议就医检查心肾功能。"},
    "焦虑抑郁": {"keywords": ["焦虑", "抑郁", "情绪差", "心情不好", "烦躁", "易怒"],
                 "herbs": ["柴胡", "白芍", "当归", "茯苓"], "formulas": ["逍遥散"],
                 "advice": "保持良好作息，适当运动，多与亲友交流。严重时建议寻求专业心理帮助。"},
}

# 十八反十九畏（配伍禁忌）
COMPATIBILITY_TABOO = {
    "十八反": [
        ("甘草", "海藻"), ("甘草", "京大戟"), ("甘草", "红大戟"), ("甘草", "甘遂"), ("甘草", "芫花"),
        ("乌头", "半夏"), ("乌头", "瓜蒌"), ("乌头", "贝母"), ("乌头", "白蔹"), ("乌头", "白及"),
        ("藜芦", "人参"), ("藜芦", "丹参"), ("藜芦", "玄参"), ("藜芦", "苦参"), ("藜芦", "细辛"),
        ("藜芦", "芍药"),
    ],
    "十九畏": [
        ("硫黄", "朴硝"), ("水银", "砒霜"), ("狼毒", "密陀僧"), ("巴豆", "牵牛"),
        ("丁香", "郁金"), ("牙硝", "三棱"), ("川乌", "犀角"), ("草乌", "犀角"),
        ("人参", "五灵脂"), ("官桂", "石脂"),
    ],
}


def detect_intent(message):
    """意图识别：基于关键词匹配"""
    msg = message.strip()

    # 问候类
    if any(w in msg for w in ["你好", "您好", "hi", "hello", "在吗", "在不在", "嗨"]):
        return "greeting"

    # 帮助类
    if any(w in msg for w in ["帮助", "怎么用", "功能", "能做什么", "你是谁"]):
        return "help"

    # 配伍禁忌查询
    if any(w in msg for w in ["配伍", "禁忌", "相克", "不能一起", "相反", "相畏", "十八反", "十九畏"]):
        return "compatibility"

    # 方剂查询
    if any(w in msg for w in ["方剂", "汤", "散", "丸", "丹", "方子", "药方"]):
        return "formula"

    # 症状咨询
    for symptom, info in SYMPTOM_MAP.items():
        if any(kw in msg for kw in info["keywords"]):
            return "symptom"

    # 处方查询（患者端）
    if any(w in msg for w in ["我的处方", "处方", "开药", "药方查询", "我的药"]):
        return "prescription"

    # 药材知识查询（默认）
    # 检查是否包含已知药材名（支持模糊匹配）
    all_herbs = query("SELECT herb_name FROM herb_knowledge")
    herb_names = [h["herb_name"] for h in all_herbs] if all_herbs else []
    for name in herb_names:
        # 精确匹配：药材名在消息中
        if name in msg:
            return "herb"
        # 模糊匹配：消息中的关键词是药材名的子串（如"枸杞"匹配"枸杞子"）
        # 提取消息中的关键词（去掉常见疑问词）
        keywords = re.sub(r'[有什么功效主治怎么吃用量禁忌什么的吗呢？?，。、]', ' ', msg).split()
        for kw in keywords:
            if len(kw) >= 2 and kw in name:
                return "herb"

    # 如果包含"功效"、"主治"、"用量"等药材查询关键词，也默认按药材处理
    if any(w in msg for w in ["功效", "主治", "用量", "怎么吃", "禁忌", "作用", "性味", "归经", "药材"]):
        return "herb"

    return "unknown"


def query_herb_knowledge(herb_name):
    """查询药材知识"""
    herb = query("SELECT * FROM herb_knowledge WHERE herb_name = %s", (herb_name,), one=True)
    if not herb:
        # 模糊匹配
        herb = query("SELECT * FROM herb_knowledge WHERE herb_name LIKE %s", (f"%{herb_name}%",), one=True)
    return herb


def format_herb_card(herb):
    """格式化药材知识卡片"""
    if not herb:
        return None
    return {
        "type": "herb_card",
        "herbCode": herb.get("herb_code"),
        "name": herb.get("herb_name"),
        "category": herb.get("category"),
        "nature": herb.get("nature"),
        "flavor": herb.get("flavor"),
        "meridian": herb.get("meridian"),
        "effects": herb.get("effects"),
        "indications": herb.get("indications"),
        "dosage": herb.get("dosage"),
        "usage": herb.get("usage"),
        "contraindications": herb.get("contraindications"),
        "compatibility": herb.get("compatibility"),
    }


def query_formula(formula_name):
    """查询方剂"""
    formula = query("SELECT * FROM formulas WHERE name = %s", (formula_name,), one=True)
    if not formula:
        formula = query("SELECT * FROM formulas WHERE name LIKE %s", (f"%{formula_name}%",), one=True)
    return formula


def format_formula_card(formula):
    """格式化方剂卡片"""
    if not formula:
        return None
    return {
        "type": "formula_card",
        "name": formula.get("name"),
        "category": formula.get("category"),
        "source": formula.get("source"),
        "composition": formula.get("composition"),
        "effects": formula.get("effects"),
        "indications": formula.get("indications"),
        "usage": formula.get("usage"),
        "contraindications": formula.get("contraindications"),
    }


def check_compatibility(herb_list):
    """检查配伍禁忌"""
    found_taboo = []
    herb_set = set(herb_list)

    for a, b in COMPATIBILITY_TABOO["十八反"]:
        if a in herb_set and b in herb_set:
            found_taboo.append({"type": "十八反", "herbA": a, "herbB": b,
                                "warning": f"{a}与{b}属于十八反，不宜同用"})

    for a, b in COMPATIBILITY_TABOO["十九畏"]:
        if a in herb_set and b in herb_set:
            found_taboo.append({"type": "十九畏", "herbA": a, "herbB": b,
                                "warning": f"{a}与{b}属于十九畏，不宜同用"})

    return found_taboo


@app.route("/api/chat", methods=["POST"])
def chat():
    """智能问答主接口"""
    user, err = require_login()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return fail("请输入您的问题")

    intent = detect_intent(message)
    reply = ""
    cards = []
    warnings = []

    if intent == "greeting":
        role_name = "管理员" if user["role"] == "admin" else ("医生" if user["role"] == "doctor" else "患者")
        reply = f"您好！我是本草智管智能诊疗助手。\n\n"
        reply += f"当前登录身份：{role_name}（{user['name']}）\n\n"
        reply += "我可以为您提供以下服务：\n"
        reply += "• 查询药材功效、用法、禁忌\n"
        reply += "• 咨询常见症状的调理建议\n"
        reply += "• 查询经典方剂的组成和用法\n"
        reply += "• 检查药材配伍禁忌\n"
        if user["role"] in ["admin", "doctor"]:
            reply += "• 处方辅助与临床参考\n"
        if user["role"] == "patient":
            reply += "• 查询您的处方记录\n"
        reply += "\n您可以直接输入问题，例如：\n"
        reply += "「黄芪有什么功效」\n"
        reply += "「最近失眠怎么办」\n"
        reply += "「四君子汤的组成是什么」"

    elif intent == "help":
        reply = "【智能助手使用指南】\n\n"
        reply += "1. 药材查询：直接输入药材名，如「黄芪」「当归」\n"
        reply += "2. 功效查询：如「黄芪有什么功效」「当归主治什么」\n"
        reply += "3. 用法用量：如「黄芪怎么吃」「茯苓用量多少」\n"
        reply += "4. 禁忌查询：如「黄芪有什么禁忌」「什么人不能吃当归」\n"
        reply += "5. 症状咨询：如「感冒了怎么办」「失眠怎么调理」\n"
        reply += "6. 方剂查询：如「四君子汤组成」「四物汤功效」\n"
        reply += "7. 配伍禁忌：如「甘草和甘遂能一起用吗」「十八反是什么」\n"
        if user["role"] == "patient":
            reply += "8. 处方查询：输入「我的处方」查看您的处方记录\n"
        reply += "\n提示：本助手提供的信息仅供参考，不能替代专业医师诊断。"

    elif intent == "herb":
        # 提取药材名（支持模糊匹配）
        all_herbs = query("SELECT herb_name FROM herb_knowledge")
        herb_names = [h["herb_name"] for h in all_herbs] if all_herbs else []
        matched_herb = None
        # 第一轮：精确匹配
        for name in herb_names:
            if name in message:
                matched_herb = name
                break
        # 第二轮：模糊匹配（消息中的关键词是药材名的子串）
        if not matched_herb:
            keywords = re.sub(r'[有什么功效主治怎么吃用量禁忌什么的吗呢？?，。、]', ' ', message).split()
            best_match = None
            best_match_len = 0
            for name in herb_names:
                for kw in keywords:
                    if len(kw) >= 2 and kw in name and len(kw) > best_match_len:
                        best_match = name
                        best_match_len = len(kw)
            if best_match:
                matched_herb = best_match

        if matched_herb:
            herb = query_herb_knowledge(matched_herb)
            if herb:
                card = format_herb_card(herb)
                cards.append(card)
                reply = f"为您查询到【{matched_herb}】的详细信息：\n\n"
                reply += f"【分类】{herb.get('category', '未知')}\n"
                reply += f"【性味】{herb.get('nature', '')}，{herb.get('flavor', '')}\n"
                reply += f"【归经】{herb.get('meridian', '')}\n"
                reply += f"【功效】{herb.get('effects', '')}\n"
                reply += f"【主治】{herb.get('indications', '')}\n"
                reply += f"【用量】{herb.get('dosage', '')}\n"
                reply += f"【用法】{herb.get('usage', '')}\n"
                if herb.get('contraindications'):
                    warnings.append(f"【禁忌】{herb['contraindications']}")
            else:
                reply = f"抱歉，暂未收录【{matched_herb}】的详细知识。"
        else:
            reply = "请明确您想查询的药材名称。"

    elif intent == "symptom":
        matched_symptom = None
        for symptom, info in SYMPTOM_MAP.items():
            if any(kw in message for kw in info["keywords"]):
                matched_symptom = symptom
                break

        if matched_symptom:
            info = SYMPTOM_MAP[matched_symptom]
            reply = f"针对【{matched_symptom}】的调理建议：\n\n"
            reply += f"【推荐药材】{', '.join(info['herbs'])}\n"
            if info["formulas"]:
                reply += f"【参考方剂】{', '.join(info['formulas'])}\n"
                # 添加方剂卡片
                for fname in info["formulas"]:
                    formula = query_formula(fname)
                    if formula:
                        cards.append(format_formula_card(formula))
            reply += f"\n【日常建议】{info['advice']}\n\n"
            reply += "⚠️ 以上建议仅供参考，具体用药请遵医嘱。如症状持续或加重，请及时就医。"
            warnings.append("本建议仅供健康参考，不能替代专业医疗诊断。")
        else:
            reply = "抱歉，暂未收录该症状的相关信息。建议您咨询专业医师。"

    elif intent == "formula":
        # 提取方剂名（支持模糊匹配）
        all_formulas = query("SELECT name FROM formulas")
        formula_names = [f["name"] for f in all_formulas] if all_formulas else []
        matched_formula = None
        # 第一轮：精确匹配
        for name in formula_names:
            if name in message:
                matched_formula = name
                break
        # 第二轮：模糊匹配
        if not matched_formula:
            keywords = re.sub(r'[有什么功效组成怎么吃用量禁忌什么的吗呢？?，。、]', ' ', message).split()
            best_match = None
            best_match_len = 0
            for name in formula_names:
                for kw in keywords:
                    if len(kw) >= 2 and kw in name and len(kw) > best_match_len:
                        best_match = name
                        best_match_len = len(kw)
            if best_match:
                matched_formula = best_match

        if matched_formula:
            formula = query_formula(matched_formula)
            if formula:
                card = format_formula_card(formula)
                cards.append(card)
                reply = f"为您查询到【{matched_formula}】的详细信息：\n\n"
                reply += f"【分类】{formula.get('category', '未知')}\n"
                reply += f"【出处】{formula.get('source', '')}\n"
                reply += f"【组成】{formula.get('composition', '')}\n"
                reply += f"【功效】{formula.get('effects', '')}\n"
                reply += f"【主治】{formula.get('indications', '')}\n"
                reply += f"【用法】{formula.get('usage', '')}\n"
                if formula.get('contraindications'):
                    warnings.append(f"【禁忌】{formula['contraindications']}")
            else:
                reply = f"抱歉，暂未收录【{matched_formula}】的详细信息。"
        else:
            reply = "请明确您想查询的方剂名称。"

    elif intent == "compatibility":
        if "十八反" in message:
            reply = "【十八反歌诀】\n\n"
            reply += "本草明言十八反，半蒌贝蔹及攻乌，\n"
            reply += "藻戟遂芫俱战草，诸参辛芍叛藜芦。\n\n"
            reply += "【具体内容】\n"
            reply += "• 甘草反：海藻、京大戟、红大戟、甘遂、芫花\n"
            reply += "• 乌头反：半夏、瓜蒌、贝母、白蔹、白及\n"
            reply += "• 藜芦反：人参、丹参、玄参、苦参、细辛、芍药\n"
        elif "十九畏" in message:
            reply = "【十九畏歌诀】\n\n"
            reply += "硫黄畏朴硝，水银畏砒霜，狼毒畏密陀僧，\n"
            reply += "巴豆畏牵牛，丁香畏郁金，川乌、草乌畏犀角，\n"
            reply += "牙硝畏三棱，官桂畏石脂，人参畏五灵脂。\n\n"
            reply += "【具体内容】\n"
            reply += "• 硫黄畏朴硝\n• 水银畏砒霜\n• 狼毒畏密陀僧\n"
            reply += "• 巴豆畏牵牛\n• 丁香畏郁金\n• 川乌、草乌畏犀角\n"
            reply += "• 牙硝畏三棱\n• 官桂畏石脂\n• 人参畏五灵脂"
        else:
            # 检查是否提到具体药材
            all_herbs = query("SELECT herb_name FROM herb_knowledge")
            herb_names = [h["herb_name"] for h in all_herbs] if all_herbs else []
            mentioned = [name for name in herb_names if name in message]

            if len(mentioned) >= 2:
                taboos = check_compatibility(mentioned)
                if taboos:
                    reply = f"⚠️ 检测到配伍禁忌！\n\n"
                    for t in taboos:
                        reply += f"• {t['warning']}\n"
                    reply += "\n以上药材组合属于配伍禁忌，请勿自行配伍使用。"
                    warnings.extend([t["warning"] for t in taboos])
                else:
                    reply = f"经查询，{', '.join(mentioned)} 之间未发现十八反、十九畏类配伍禁忌。\n\n"
                    reply += "但具体用药仍需根据病情和体质，在医师指导下使用。"
            elif len(mentioned) == 1:
                herb = query_herb_knowledge(mentioned[0])
                if herb and herb.get("compatibility"):
                    reply = f"【{mentioned[0]}】的配伍参考：\n\n{herb['compatibility']}"
                else:
                    reply = f"暂未收录【{mentioned[0]}】的详细配伍信息。"
            else:
                reply = "【配伍禁忌查询】\n\n"
                reply += "您可以输入两种或多种药材，我来帮您检查是否存在配伍禁忌。\n\n"
                reply += "例如：「甘草和甘遂能一起用吗」\n\n"
                reply += "也可以查询：\n"
                reply += "• 输入「十八反」查看十八反详细内容\n"
                reply += "• 输入「十九畏」查看十九畏详细内容"

    elif intent == "prescription":
        if user["role"] == "patient":
            # 患者查询自己的处方
            prescriptions = query(
                "SELECT * FROM prescriptions WHERE patient_name = %s OR patient_phone = %s ORDER BY id DESC LIMIT 5",
                (user["name"], user.get("phone", ""))
            )
            if prescriptions:
                reply = f"为您查询到 {len(prescriptions)} 条处方记录：\n\n"
                for i, p in enumerate(prescriptions, 1):
                    status_map = {"pending": "待审核", "approved": "已审核", "rejected": "已驳回", "dispensed": "已发药"}
                    reply += f"{i}. 处方号：{p['prescription_no']}\n"
                    reply += f"   诊断：{p.get('diagnosis', '')}\n"
                    reply += f"   医生：{p.get('doctor_name', '')}\n"
                    reply += f"   状态：{status_map.get(p['status'], p['status'])}\n"
                    reply += f"   时间：{p.get('created_at', '')}\n\n"
            else:
                reply = "暂未查询到您的处方记录。"
        else:
            reply = "处方查询功能：患者登录后可查询自己的处方记录。\n\n"
            reply += "医护人员可在「处方管理」页面查看和管理所有处方。"

    else:
        # 未知意图，尝试模糊匹配药材
        all_herbs = query("SELECT herb_name FROM herb_knowledge")
        herb_names = [h["herb_name"] for h in all_herbs] if all_herbs else []
        matched = [name for name in herb_names if name in message]

        if matched:
            herb = query_herb_knowledge(matched[0])
            if herb:
                cards.append(format_herb_card(herb))
                reply = f"为您查询到【{matched[0]}】的信息：\n\n"
                reply += f"【功效】{herb.get('effects', '')}\n"
                reply += f"【主治】{herb.get('indications', '')}\n"
                reply += f"【用量】{herb.get('dosage', '')}\n"
                if herb.get('contraindications'):
                    warnings.append(f"【禁忌】{herb['contraindications']}")
                reply += "\n您可以继续追问更详细的信息。"
        else:
            reply = "抱歉，我暂时无法理解您的问题。\n\n"
            reply += "您可以尝试以下方式提问：\n"
            reply += "• 「黄芪有什么功效」\n"
            reply += "• 「感冒了怎么办」\n"
            reply += "• 「四君子汤组成」\n"
            reply += "• 「十八反是什么」\n"
            reply += "• 输入「帮助」查看完整使用指南"

    # 保存对话历史
    try:
        execute("""INSERT INTO chat_history (username, role, user_message, assistant_reply, intent)
                   VALUES (%s,%s,%s,%s,%s)""",
                (user["username"], user["role"], message, reply, intent))
    except Exception:
        pass  # 历史记录保存失败不影响主流程

    return ok({
        "reply": reply,
        "intent": intent,
        "cards": cards,
        "warnings": warnings,
    })


@app.route("/api/herbs/<code>/knowledge", methods=["GET"])
def herb_knowledge_detail(code):
    """药材知识详情"""
    user, err = require_login()
    if err:
        return err
    herb = query("SELECT * FROM herb_knowledge WHERE herb_code = %s", (code,), one=True)
    if not herb:
        herb = query("SELECT * FROM herb_knowledge WHERE herb_name = %s", (code,), one=True)
    if not herb:
        return fail("未找到该药材知识")
    return ok(format_herb_card(herb))


@app.route("/api/formulas", methods=["GET"])
def list_formulas():
    """方剂库查询"""
    user, err = require_login()
    if err:
        return err
    keyword = request.args.get("keyword", "").strip()
    if keyword:
        formulas = query("SELECT * FROM formulas WHERE name LIKE %s OR effects LIKE %s OR indications LIKE %s",
                         (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"))
    else:
        formulas = query("SELECT * FROM formulas ORDER BY id")
    return ok({"total": len(formulas), "items": formulas})


@app.route("/api/chat/history", methods=["GET"])
def chat_history():
    """对话历史查询"""
    user, err = require_login()
    if err:
        return err
    limit = int(request.args.get("limit", 20))
    history = query("SELECT * FROM chat_history WHERE username = %s ORDER BY id DESC LIMIT %s",
                    (user["username"], limit))
    return ok({"total": len(history), "items": history})


@app.route("/api/assistant/prescription-help", methods=["POST"])
def prescription_help():
    """医护端处方辅助：根据诊断推荐药材和方剂"""
    user, err = require_login()
    if err:
        return err
    if user["role"] not in ["admin", "doctor"]:
        return fail("仅医护人员可使用处方辅助功能")

    data = request.get_json(silent=True) or {}
    diagnosis = (data.get("diagnosis") or "").strip()
    if not diagnosis:
        return fail("请输入诊断信息")

    # 基于诊断关键词匹配
    suggestions = {"herbs": [], "formulas": [], "notes": []}

    # 气虚相关
    if any(w in diagnosis for w in ["气虚", "乏力", "倦怠", "食少", "便溏", "气血两虚", "气血不足", "气血亏虚"]):
        suggestions["herbs"].extend(["黄芪", "党参", "白术", "茯苓", "甘草"])
        suggestions["formulas"].append("四君子汤")
        if any(w in diagnosis for w in ["下陷", "脱肛", "子宫脱垂"]):
            suggestions["formulas"].append("补中益气汤")

    # 血虚相关
    if any(w in diagnosis for w in ["血虚", "萎黄", "眩晕", "心悸", "月经不调", "气血两虚", "气血不足", "气血亏虚"]):
        suggestions["herbs"].extend(["当归", "白芍", "川芎"])
        suggestions["formulas"].append("四物汤")
        if "气血" in diagnosis or ("气虚" in diagnosis and "血虚" in diagnosis):
            suggestions["formulas"].append("当归补血汤")

    # 肝郁相关
    if any(w in diagnosis for w in ["肝郁", "胁痛", "抑郁", "焦虑", "月经不调"]):
        suggestions["herbs"].extend(["柴胡", "白芍", "当归", "茯苓", "白术"])
        suggestions["formulas"].append("逍遥散")

    # 水湿相关
    if any(w in diagnosis for w in ["水肿", "痰饮", "小便不利", "泄泻"]):
        suggestions["herbs"].extend(["茯苓", "白术"])
        suggestions["formulas"].append("五苓散")

    # 表虚自汗
    if any(w in diagnosis for w in ["自汗", "表虚", "易感冒"]):
        suggestions["herbs"].extend(["黄芪", "白术"])
        suggestions["formulas"].append("玉屏风散")

    # 少阳证
    if any(w in diagnosis for w in ["寒热往来", "胸胁苦满", "默默不欲饮食", "心烦喜呕"]):
        suggestions["herbs"].extend(["柴胡", "黄芩"])
        suggestions["formulas"].append("小柴胡汤")

    # 去重
    suggestions["herbs"] = list(dict.fromkeys(suggestions["herbs"]))
    suggestions["formulas"] = list(dict.fromkeys(suggestions["formulas"]))

    # 获取药材详情
    herb_details = []
    for hname in suggestions["herbs"]:
        herb = query_herb_knowledge(hname)
        if herb:
            herb_details.append({
                "name": herb["herb_name"], "dosage": herb.get("dosage"),
                "effects": herb.get("effects"), "contraindications": herb.get("contraindications")
            })

    # 获取方剂详情
    formula_details = []
    for fname in suggestions["formulas"]:
        formula = query_formula(fname)
        if formula:
            formula_details.append(format_formula_card(formula))

    # 检查配伍禁忌
    taboos = check_compatibility(suggestions["herbs"])

    suggestions["notes"].append("以上推荐基于经典方剂和常用配伍，仅供临床参考。")
    suggestions["notes"].append("实际处方请结合患者具体病情、体质、舌脉等综合判断。")
    if taboos:
        suggestions["notes"].append("⚠️ 注意：推荐药材中存在配伍禁忌，请谨慎配伍！")

    return ok({
        "diagnosis": diagnosis,
        "suggestedHerbs": herb_details,
        "suggestedFormulas": formula_details,
        "compatibilityWarnings": taboos,
        "notes": suggestions["notes"],
    })


if __name__ == "__main__":
    print("=" * 50)
    print("  本草智管平台 - 4号模块（处方管理 + 数据看板）")
    print("=" * 50)
    print(f"前端目录: {os.path.abspath(FRONTEND_DIR)}")
    print("访问地址: http://127.0.0.1:5000")
    print("默认账号: admin/123456 (管理员)")
    print("          doctor/123456 (医生)")
    print("          patient/123456 (病人)")
    print("=" * 50)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
