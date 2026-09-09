# 本草智管平台（前端 + Python + MySQL 全栈版）

本草智管平台原为纯前端项目（数据存浏览器 localStorage），本版本将其接入 MySQL
数据库：Python Flask 提供 REST API，前端所有数据读写改为调用后端接口。

## 技术架构

```
前端 (HTML/Tailwind)  --fetch-->  Flask 后端 (Python)  --pymysql-->  MySQL 8.0
```

- 前端：`frontend/`（index / dashboard / herbs / users / logs 五个页面）
- 后端：`backend/app.py`（REST API + 托管前端静态页面）
- 数据库：`backend/init_db.py`（建库建表 + 默认账号）

## 快速启动

```bash
# 1. 首次运行：初始化数据库（建库 herb_management_system + 三张表 + 默认账号）
cd backend
python init_db.py

# 2. 启动后端服务
python app.py
```

浏览器访问 **http://127.0.0.1:5000**

Windows 下也可以直接双击 `start.bat`（先手动执行一次 init_db.py）。

## 默认账号

| 用户名 | 密码 | 角色 |
|---|---|---|
| admin | 123456 | 管理员（可管理用户/日志/药材） |
| doctor | 123456 | 医生（可增改药材） |
| patient | 123456 | 病人（只读） |

## 数据库表

- `users`：用户（username 主键，密码 SHA256 存储）
- `herbs`：药材（code 主键，含库存、预警阈值等）
- `operation_logs`：操作日志（记录药材增删改，含字段级变更明细）

## 主要 API

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | /api/login | 登录 | 公开 |
| POST | /api/register | 注册（管理员需密钥 admin123） | 公开 |
| GET | /api/herbs?q= | 药材列表/搜索 | 登录 |
| POST | /api/herbs | 新增药材 | 登录（病人除外） |
| PUT | /api/herbs/<code> | 编辑药材 | 登录（病人除外） |
| DELETE | /api/herbs/<code> | 删除药材 | 登录（病人除外） |
| POST | /api/herbs/<code>/adjust | 快速调库 | 登录（病人除外） |
| GET | /api/users?keyword=&role= | 用户列表 | 管理员 |
| POST | /api/users | 添加用户 | 管理员 |
| PUT | /api/users/<username> | 编辑用户 | 管理员 |
| DELETE | /api/users/<username> | 删除用户 | 管理员 |
| GET | /api/logs?herb=&action=&time=&keyword= | 操作日志 | 管理员 |
| GET | /api/dashboard | 仪表盘统计 | 登录 |

接口统一返回 `{"code": 0, "message": "...", "data": ...}`，code 非 0 表示失败。
除登录/注册外，请求需携带请求头 `X-User: <当前登录用户名>`。

## 数据库连接配置

连接参数集中在 `backend/db.py` 的 `DB_CONFIG` 和 `backend/init_db.py` 的
`ROOT_CONFIG`（host/port/user/password）。如 MySQL 密码变更，两处同步修改。

## 注意事项

- 必须通过 `http://127.0.0.1:5000` 访问（不能直接双击 HTML 文件，否则接口跨域失败）。
- 原 `Downloads\本草智管` 目录下的页面为改造前的版本，未做改动。
