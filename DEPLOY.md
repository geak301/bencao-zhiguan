# 本草智管平台 - 云服务器部署指南

目标：把"前端 + Python 后端 + MySQL 数据库"整体部署到云服务器，
别人无需访问你的电脑，随时通过公网地址注册使用。

## 原理说明

一个可对外访问的网站 = 数据库 + 后端程序 + 前端页面 + 公网入口，四者缺一不可。
浏览器无法直连数据库，所以必须有一台**服务器**同时运行 MySQL 和后端程序。
"上传数据库"指的是把数据库建到服务器上，并把本机数据导入进去。

## 方案对比

| 方案 | 成本 | 稳定性 | 适合场景 |
|---|---|---|---|
| A. 云服务器（阿里云/腾讯云） | 学生机约 ¥10-100/年 | 高 | 正式上线、课程长期展示 |
| B. 免费 PaaS 平台（Railway/Render） | 免费额度 | 中 | 临时演示、不想花钱 |
| C. 局域网 + 内网穿透 | 免费 | 低（URL 会变） | 一次性演示 |

推荐方案 A。下面以方案 A 为主。

---

## 方案 A：云服务器部署（推荐）

### 第 1 步：买服务器

- 阿里云 / 腾讯云 / 华为云，选 **云服务器 ECS/CVM**，学生认证可买学生机
- 系统选 **Ubuntu 22.04** 或 **CentOS 7/8**（本文以 Ubuntu 为例）
- 配置：2核2G 起步即可
- 记下服务器的**公网 IP** 和登录密码

### 第 2 步：上传项目

把整个 `new-chat-3` 项目文件夹上传到服务器。推荐工具：
- **WinSCP**（图形界面，拖拽上传）或 **scp 命令**

```
scp -r new-chat-3 root@<公网IP>:~/
```

### 第 3 步：服务器上安装环境

SSH 登录服务器后执行：

```bash
# 安装 MySQL
sudo apt update
sudo apt install -y mysql-server
sudo systemctl enable mysql && sudo systemctl start mysql

# 安装 Python 3 + pip
sudo apt install -y python3 python3-pip python3-venv

# 安装项目依赖
cd ~/new-chat-3/backend
pip3 install flask pymysql --break-system-packages
```

### 第 4 步：导入数据库

两种方式任选：

**方式 1：直接导入本机导出的备份（数据全带过去）**

先把 `herb_db_backup.sql` 上传到服务器（已在项目根目录），然后：

```bash
mysql -uroot -p < herb_db_backup.sql
# 输入服务器 MySQL 的 root 密码（首次安装按提示设置）
```

**方式 2：重新建库（数据从零开始，用页面注册）**

```bash
cd ~/new-chat-3/backend
python3 init_db.py
```

> 方式 1 导入后，本机的 3 个账号、药材、日志全部在服务器上。
> 用方式 1 时注意：备份文件里的表结构和数据会完整恢复，无需再跑 init_db.py。

### 第 5 步：改数据库连接配置

编辑服务器上的 `backend/db.py` 和 `backend/init_db.py`：

```python
DB_CONFIG = {
    "host": "127.0.0.1",          # 服务器本机，不用改
    "user": "root",
    "password": "<服务器MySQL密码>",   # 改成服务器的 MySQL 密码
    "database": "herb_management_system",
    ...
}
```

### 第 6 步：启动服务（后台常驻）

```bash
cd ~/new-chat-3/backend
nohup python3 app.py > app.log 2>&1 &
```

### 第 7 步：开放防火墙/安全组（最关键）

**云服务器安全组**（在云控制台操作）：
- 入方向添加规则：**TCP 5000 端口，来源 0.0.0.0/0（所有人）**

**服务器系统防火墙**（如有）：

```bash
sudo ufw allow 5000/tcp
```

### 第 8 步：验证

- 本机浏览器访问 `http://<公网IP>:5000`，能打开登录页即成功
- 用手机 4G/5G 网络（不走 WiFi）访问同一个地址，验证外网可通
- 让别人注册一个账号，然后你登录 admin 在"用户管理"里能看到新账号

### 停止/重启服务

```bash
# 查看
ps aux | grep app.py
# 停止
kill <进程号>
# 重启
nohup python3 app.py > app.log 2>&1 &
```

---

## 方案 B：免费 PaaS 平台（Railway / Render）

以 Railway 为例（有免费额度，自带 MySQL 插件）：

1. 注册 railway.app，新建项目
2. 添加 **MySQL** 插件，记下连接信息（host/port/user/password/database）
3. 把项目推送到 GitHub，Railway 从仓库部署
4. 部署命令：`cd backend && pip install -r requirements.txt && python app.py`
5. 环境变量配置 MySQL 连接信息（替代直接改 db.py）
6. 平台自动分配公网域名

注意：免费版域名随机、冷启动慢、国内访问可能慢；需要修改 `app.py` 支持从环境变量读数据库配置。

---

## 方案 C：内网穿透（不换服务器，临时分享）

你的电脑保持开机，运行内网穿透工具把 5000 端口映射到公网：

```
ngrok http 5000        # 生成 https://xxxx.ngrok-free.app
```

别人访问生成的公网地址即可。优点：零部署成本；缺点：免费 URL 每次变化、速度一般、需要电脑一直开机。

---

## 安全提醒

1. 部署后**立刻修改 MySQL root 密码**，不要用 `Z8023502z!` 或任何简单密码
2. 公网开放后任何人可注册，如需限制可后续加邀请码/白名单
3. `db.py` 里的数据库密码不要提交到公开 GitHub 仓库（可用环境变量替代）
4. 演示结束可用 `kill` 停掉服务，或安全组删除 5000 规则
