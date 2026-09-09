# -*- coding: utf-8 -*-
"""
数据库验证脚本：直连 MySQL，展示 herb_management_system 数据库的
表结构、记录数与当前数据，用于确认前端 ↔ Python ↔ MySQL 已打通。

用法：python verify_db.py
"""
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, __file__ and __file__.rsplit("\\", 1)[0] or ".")

from db import query

print("=" * 60)
print("  本草智管平台 - 数据库验证")
print("  连接: MySQL 8.0 @ 127.0.0.1:3306")
print("  数据库: herb_management_system")
print("=" * 60)

# 1. 三张表是否就绪
print("\n[1] 数据表")
for r in query(
    "SHOW TABLE STATUS FROM herb_management_system"
):
    print(f"  - {r['Name']:<16} 约 {r['Rows']} 行")

# 2. 用户表
print("\n[2] users 用户表")
for r in query("SELECT username, role, name, phone, status, create_time FROM users ORDER BY create_time"):
    print(f"  {r['username']:<10} {r['role']:<8} {r['name']:<10} {r['phone'] or '-':<13} {r['status']}  注册:{r['create_time']}")

# 3. 药材表
print("\n[3] herbs 药材表")
for r in query("SELECT code, name, category, origin, quantity, unit, price, warning_threshold FROM herbs ORDER BY created_at"):
    print(f"  {r['code']:<24} {r['name']:<8} {r['category'] or '-':<10} {r['origin'] or '-':<12} "
          f"库存:{r['quantity']}{r['unit'] or ''}  单价:¥{r['price']}  预警阈值:{r['warning_threshold']}")

# 4. 日志表
print("\n[4] operation_logs 操作日志表")
rows = query("SELECT id, herb_name, action, operator, time_str FROM operation_logs ORDER BY id")
for r in rows:
    print(f"  #{r['id']:<3} {r['herb_name']:<8} {r['action']:<6} 操作人:{r['operator']:<8} {r['time_str']}")
print(f"  （共 {len(rows)} 条日志）")

print("\n[5] 结论")
n_users = len(query("SELECT 1 FROM users"))
n_herbs = len(query("SELECT 1 FROM herbs"))
n_logs = len(rows)
if n_users >= 3:
    print("  ✔ 数据库连接正常，3 张表已就绪，默认账号已写入")
    print(f"  ✔ users={n_users}  herbs={n_herbs}  logs={n_logs}")
    if n_herbs > 0:
        print("  ✔ 药材数据真实存储在 MySQL（非浏览器 localStorage）")
    else:
        print("  （当前没有药材数据，可在页面「药材管理」中添加后再验证）")
else:
    print("  ✘ 用户表数据异常，请重新执行 python init_db.py")
print("=" * 60)
