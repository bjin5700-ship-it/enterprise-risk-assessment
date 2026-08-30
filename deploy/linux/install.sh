#!/bin/bash
# Linux 生产环境一键安装脚本（Ubuntu/Debian/CentOS 通用思路）
# 用法: sudo bash deploy/linux/install.sh /opt/erm

set -e
INSTALL_DIR="${1:-/opt/erm}"
APP_USER="${ERM_USER:-erm}"
PORT="${ERM_PORT:-8088}"

echo "=== 企业风险动态评估系统 — Linux 部署 ==="
echo "安装目录: $INSTALL_DIR"

if ! command -v python3 &>/dev/null; then
  echo "请先安装 Python 3.10+: apt install python3 python3-venv python3-pip"
  exit 1
fi

# 复制项目（若已在目标目录可跳过）
SCRIPT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
if [ "$(realpath "$SCRIPT_DIR")" != "$(realpath "$INSTALL_DIR")" ]; then
  mkdir -p "$INSTALL_DIR"
  rsync -a --exclude '__pycache__' --exclude '.git' "$SCRIPT_DIR/" "$INSTALL_DIR/"
fi

cd "$INSTALL_DIR"
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

mkdir -p web_app/data web_app/exports web_app/uploads

# 环境文件
if [ ! -f web_app/.env ]; then
  cp deploy/env.example web_app/.env
  echo "请编辑 $INSTALL_DIR/web_app/.env 设置 ERM_PUBLIC_URL 和 ERM_SECRET_KEY"
fi

# systemd 服务
sed "s|/opt/erm|$INSTALL_DIR|g; s|8088|$PORT|g" deploy/linux/erm.service > /tmp/erm.service
if [ -d /etc/systemd/system ]; then
  cp /tmp/erm.service /etc/systemd/system/erm.service
  systemctl daemon-reload
  systemctl enable erm
  echo "已注册 systemd 服务: systemctl start erm"
fi

echo ""
echo "=== 下一步 ==="
echo "1. 编辑 $INSTALL_DIR/web_app/.env"
echo "2. systemctl start erm && systemctl status erm"
echo "3. 配置 Nginx: 参考 deploy/linux/nginx-erm.conf"
echo "4. 防火墙: ufw allow 80/tcp && ufw allow 443/tcp"
