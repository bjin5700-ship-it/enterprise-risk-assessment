# OpenClaw 部署指令（复制全文发给 OpenClaw）

---

## 任务：部署「企业风险动态评估系统」到云服务器，供外地客户远程访问

### 一、背景

- **项目名称**：企业风险动态评估系统（ERM）
- **本地源码路径**（开发机）：`D:\_Work\02_Documents\信息搜集表格\`
- **技术栈**：Python 3.10+ / Flask / Waitress(Gunicorn) / 端口 8088
- **部署文档**：项目内 `DEPLOY.md`（请先阅读）
- **功能约束**：Web 仅 4 个导航模块（仪表盘 / 数据录入 / 评估报告 / 解决方案），不得改 UI 结构

### 二、部署前请向我确认（若信息未提供则先询问）

1. **服务器系统**：Windows Server / Ubuntu Linux？
2. **服务器访问方式**：SSH / RDP / OpenClaw 是否已有 shell 权限？
3. **安装路径**：
   - Windows 建议：`D:\apps\erm\`
   - Linux 建议：`/opt/erm/`
4. **公网访问方式**（二选一）：
   - A. 有域名：`https://erm.xxxx.com`（推荐，需 HTTPS）
   - B. 暂无域名：临时 `http://公网IP:8088`（需安全组放行 8088）
5. **源码如何上服务器**：本地上传 / git / scp / 我已在服务器放好路径？

### 三、必须上传的目录与文件

将整个 `信息搜集表格` 文件夹部署到服务器，**至少包含**：

```
信息搜集表格/
├── risk_*.py, data_integration.py, erp_oauth.py, sync_scheduler.py 等所有根目录 .py
├── 企业风险*.xlsx          ← Excel 模板（文件名含「企业风险」，缺一不可）
├── requirements.txt
├── system_audit.py
├── DEPLOY.md
├── deploy/                 ← 含 windows/ linux/ env.example
└── web_app/
    ├── app.py, run_production.py, wsgi.py, bootstrap.py, server_config.py
    ├── templates/, static/
    └── data/               ← 可空目录，运行时写入；勿删已有数据
```

### 四、执行步骤（按顺序，每步汇报结果）

#### Step 1 — 环境检查

```bash
# Windows
py -3 --version
py -3 -m pip --version

# Linux
python3 --version
python3 -m pip --version
```

要求：Python ≥ 3.10

#### Step 2 — 安装依赖

```bash
cd <安装路径>/信息搜集表格    # 或部署后的 erm 根目录
py -3 -m pip install -r requirements.txt          # Windows
# Linux:
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

#### Step 3 — 创建生产配置 `web_app/.env`

复制 `deploy/env.example` → `web_app/.env`，并写入（**向我确认域名后再填**）：

```ini
ERM_PUBLIC_URL=https://erm.你的域名.com
ERM_ENV=production
ERM_HOST=0.0.0.0
ERM_PORT=8088
ERM_SECRET_KEY=<生成随机32位以上字符串>
ERM_THREADS=8
ERM_SCHEDULER_INTERVAL=60
```

生成密钥示例（Linux）：
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

#### Step 4 — 启动应用（生产模式）

**Windows：**
```bat
cd web_app
set ERM_ENV=production
py -3 run_production.py
```
或编辑并运行 `deploy\windows\生产环境启动.bat`（需先改其中的 ERM_PUBLIC_URL 和 ERM_SECRET_KEY）

**Linux（推荐 systemd 持久化）：**
```bash
sudo bash deploy/linux/install.sh /opt/erm
sudo nano /opt/erm/web_app/.env
sudo systemctl start erm
sudo systemctl enable erm
sudo systemctl status erm
```

**Linux 手动验证：**
```bash
cd web_app
export $(grep -v '^#' .env | xargs)
gunicorn -w 1 -b 0.0.0.0:8088 --timeout 120 wsgi:application
```

#### Step 5 — 防火墙 / 安全组

- **云安全组**：放行 80、443（有 Nginx/HTTPS 时）；临时测试可放行 8088
- **Windows 本机防火墙**（若直接暴露 8088）：
  ```powershell
  cd <安装路径>\deploy\windows
  .\open-firewall.ps1 -Port 8088
  ```
- **Linux ufw**：
  ```bash
  sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
  # 临时: sudo ufw allow 8088/tcp
  ```

#### Step 6 — Nginx + HTTPS（有域名时必须做）

参考 `deploy/linux/nginx-erm.conf`：

1. 域名 A 记录 → 服务器公网 IP
2. 安装 Nginx，反代 `127.0.0.1:8088`
3. 申请 SSL：
   ```bash
   sudo apt install certbot python3-certbot-nginx -y
   sudo certbot --nginx -d erm.你的域名.com
   ```
4. 确认 `ERM_PUBLIC_URL` 与最终 HTTPS 地址一致

Windows 可用 Nginx for Windows 或 IIS 反向代理，逻辑相同。

#### Step 7 — 验证（全部通过才算部署成功）

```bash
# 1. 健康检查
curl http://127.0.0.1:8088/ping
# 期望: {"ok":true,"service":"enterprise-risk-assessment"}

# 2. 全量巡检（在项目根目录）
py -3 system_audit.py
# 期望: ALL PASSED

# 3. 浏览器验证四页面可打开
#    /  /data-entry  /report  /solution

# 4. 功能冒烟：数据录入 → 填企业名称 → 运行风险评估 → 仪表盘有分数
```

#### Step 8 — 持久化与备份（生产必做）

- Linux：确认 `systemctl status erm` 为 active，重启服务器后再 curl /ping
- Windows：建议用 NSSM 或「任务计划程序」将 `run_production.py` 设为开机自启
- 备份目录：`web_app/data/`（history.json、kpi_timeseries.json 等）

### 五、交付物（完成后汇报给我）

请返回以下信息：

1. 客户访问 URL（最终 HTTPS 地址或临时 IP:端口）
2. `curl /ping` 与 `system_audit.py` 输出摘要
3. systemd / 进程状态（是否在运行）
4. 是否已配置 HTTPS
5. 未解决问题或需我手动确认的配置项

### 六、禁止事项

- 不要修改四模块导航结构
- 不要将 `.env`、密钥、SMTP 密码提交到公开 git
- 不要用 Flask 开发服务器 (`app.run`) 做生产长期运行，必须用 Waitress 或 Gunicorn
- 部署时不要覆盖已有 `web_app/data/` 里的客户档案（若存在先备份）

### 七、故障排查速查

| 现象 | 检查 |
|------|------|
| 外网打不开 | 安全组、防火墙、Nginx、进程是否监听 0.0.0.0:8088 |
| 404 / 旧 API | 8088 端口是否被旧进程占用，先 kill 再重启 |
| OAuth 失败 | ERM_PUBLIC_URL 是否与浏览器地址完全一致 |
| 模板加载失败 | 根目录是否有「企业风险」.xlsx |

---

**开始执行。若缺少服务器 IP、域名、系统类型、安装路径，请先向我提问再动手。**
