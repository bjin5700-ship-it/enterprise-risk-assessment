# 服务器部署指南

本文说明如何将「企业风险动态评估系统」部署到云服务器，供外地客户通过浏览器访问。

---

## 一、部署架构

```
客户浏览器  →  HTTPS (443)  →  Nginx  →  Waitress/Gunicorn (8088)  →  Flask 应用
                                    ↑
                              域名 + SSL 证书
```

- **应用端口**：内网 `8088`（不直接暴露公网亦可）
- **对外访问**：`https://erm.您的域名.com`
- **四模块不变**：仪表盘 / 数据录入 / 评估报告 / 解决方案

---

## 二、服务器要求

| 项目 | 建议 |
|------|------|
| 系统 | Windows Server 2019+ 或 Ubuntu 22.04+ |
| CPU/内存 | 2 核 / 4GB 起 |
| Python | 3.10 或 3.12 |
| 磁盘 | 20GB+（含报告导出、档案数据） |
| 网络 | 公网 IP + 域名（推荐） |

---

## 三、上传项目

将整个 `信息搜集表格` 文件夹上传到服务器，例如：

- Windows：`D:\apps\erm\`
- Linux：`/opt/erm/`

**必须包含：**

- 根目录所有 `risk_*.py`、`data_integration.py` 等 Python 模块
- 根目录 Excel 模板（文件名含「企业风险」的 `.xlsx`）
- `web_app/` 目录（含 `app.py`、`templates`、`static`、`data`）

---

## 四、安装依赖

```bash
cd /opt/erm          # 或 Windows 下项目根目录
py -3 -m pip install -r requirements.txt   # Windows
# Linux:
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

---

## 五、配置环境变量

复制 `deploy/env.example` 为 `web_app/.env` 并修改：

```ini
ERM_PUBLIC_URL=https://erm.yourcompany.com
ERM_ENV=production
ERM_HOST=0.0.0.0
ERM_PORT=8088
ERM_SECRET_KEY=随机长字符串至少32位
ERM_THREADS=8
```

| 变量 | 说明 |
|------|------|
| `ERM_PUBLIC_URL` | **必填**。客户访问的完整 URL，OAuth 回调依赖此项 |
| `ERM_SECRET_KEY` | **必填**。Flask 会话密钥，生产环境勿用默认值 |
| `ERM_PORT` | 应用监听端口，默认 8088 |

---

## 六、启动方式

### 方式 A：Windows 服务器（最简单）

1. 编辑 `deploy\windows\生产环境启动.bat` 中的 `ERM_PUBLIC_URL` 和 `ERM_SECRET_KEY`
2. 双击运行，或配置为 Windows 服务（任务计划程序 / NSSM）
3. 防火墙放行 **8088**（若直接访问）或 **80/443**（若用 IIS/Nginx 反代）

### 方式 B：Linux + systemd（推荐）

```bash
sudo bash deploy/linux/install.sh /opt/erm
sudo nano /opt/erm/web_app/.env    # 填写域名与密钥
sudo systemctl start erm
sudo systemctl status erm
```

### 方式 C：手动生产启动

```bash
cd web_app
export ERM_ENV=production
export ERM_PUBLIC_URL=https://erm.yourcompany.com
py -3 run_production.py              # Windows / 跨平台 Waitress
# 或 Linux:
gunicorn -w 1 -b 0.0.0.0:8088 --timeout 120 wsgi:application
```

---

## 七、Nginx + HTTPS（推荐给客户使用）

1. 域名 A 记录指向服务器公网 IP
2. 安装 Nginx，参考 `deploy/linux/nginx-erm.conf`
3. 申请免费 SSL：

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d erm.yourcompany.com
```

4. 客户访问：`https://erm.yourcompany.com`

**Windows** 可用 IIS 反向代理，或安装 Nginx for Windows，配置同理。

---

## 八、防火墙与安全

### 云厂商安全组（必做）

| 端口 | 用途 |
|------|------|
| 80 | HTTP（跳转 HTTPS） |
| 443 | HTTPS 客户访问 |
| 8088 | 可选，仅内网/Nginx 反代时可不对外开放 |
| 3389/RDP | 仅管理员 IP 白名单（Windows 远程） |
| 22 | 仅管理员 IP 白名单（Linux SSH） |

### 安全建议

1. **务必使用 HTTPS**，避免评估数据明文传输
2. 当前版本**无登录鉴权**，建议：
   - 安全组 IP 白名单（仅客户公司出口 IP），或
   - Nginx 基础认证（`auth_basic`），或
   - 后续接入企业 SSO
3. 定期备份 `web_app/data/`（档案、KPI 时序、通知配置）
4. 勿将 `.env`、SMTP 密码、OAuth Secret 提交到公开仓库

---

## 九、验证部署

```bash
curl http://127.0.0.1:8088/ping
# 应返回: {"ok":true,"service":"enterprise-risk-assessment"}

# 完整巡检（在服务器项目根目录）
py -3 system_audit.py
```

浏览器打开公网地址，确认四个导航模块均可访问并完成一次「运行风险评估」。

---

## 十、常见问题

**Q：客户打不开页面？**  
检查：安全组 443 是否开放、域名解析、Nginx 是否运行、`systemctl status erm`。

**Q：OAuth ERP 回调失败？**  
确认 `ERM_PUBLIC_URL` 与浏览器地址一致（含 https），且在 ERP 控制台登记相同回调 URL。

**Q：重启后数据丢失？**  
数据在 `web_app/data/`，部署时不要覆盖该目录；升级前备份。

**Q：多客户共用一台服务器？**  
当前为单租户部署；不同企业共用同一实例时，用「企业名称」区分档案即可。若需强隔离，建议每客户独立实例或子域名。

---

## 十一、目录速查

```
信息搜集表格/
├── deploy/
│   ├── env.example          # 环境变量模板
│   ├── windows/生产环境启动.bat
│   └── linux/               # systemd + nginx 配置
├── web_app/
│   ├── .env                 # 生产配置（自行创建）
│   ├── run_production.py    # Waitress 生产入口
│   ├── wsgi.py              # Gunicorn 入口
│   └── data/                # 运行时数据（需备份）
├── requirements.txt
├── system_audit.py          # 部署后巡检
└── DEPLOY.md                # 本文档
```

部署完成后，将 **https://您的域名** 发给客户即可在外地使用。
