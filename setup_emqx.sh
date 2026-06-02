#!/usr/bin/env bash
set -euo pipefail

# ============================================
# EMQX 安装脚本 — Ubuntu 24.04 / Docker
# - 自动安装 Docker（如未安装）
# - 启动 EMQX 容器，开机自启
# - 创建 MQTT 用户 admin/123456
# - 关闭匿名登录
# ============================================

MQTT_PORT=1883
DASH_PORT=18083
DASH_USER=admin
DASH_PASS=123456
MQTT_USER=admin
MQTT_PASS=123456
EMQX_IMAGE=emqx/emqx:latest
CONTAINER_NAME=emqx

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "[ERROR] $*" >&2; exit 1; }

# --- 检查 root ---
if [ "$EUID" -ne 0 ]; then
  error "请用 sudo 运行此脚本"
fi

# --- 1. 安装 Docker ---
if ! command -v docker &>/dev/null; then
  info "安装 Docker..."
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable docker
  systemctl start docker
  info "Docker 安装完毕"
else
  info "Docker 已安装"
fi

# --- 2. 启动 EMQX ---
info "拉取 EMQX 镜像..."
docker pull $EMQX_IMAGE

# 清理旧容器
docker rm -f $CONTAINER_NAME 2>/dev/null || true

info "启动 EMQX 容器..."
docker run -d \
  --name $CONTAINER_NAME \
  --restart always \
  -p $MQTT_PORT:1883 \
  -p $DASH_PORT:18083 \
  -v emqx-data:/opt/emqx/data \
  $EMQX_IMAGE

# --- 3. 等待就绪 ---
info "等待 EMQX 启动..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:$DASH_PORT/api/v5/login >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

# --- 4. 登录获取 token ---
TOKEN=$(curl -sf -X POST http://localhost:$DASH_PORT/api/v5/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$DASH_USER\",\"password\":\"public\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null) || {
    error "EMQX Dashboard 登录失败，请检查 http://localhost:$DASH_PORT"
}

# --- 5. 创建认证 + 添加用户 + 关闭匿名 ---
info "创建内置数据库认证..."
curl -sf -X POST http://localhost:$DASH_PORT/api/v5/authentication \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "mechanism": "password_based",
    "backend": "built_in_database",
    "enable": true,
    "password_hash_algorithm": {"name": "sha256"}
  }' >/dev/null

info "添加 MQTT 用户 $MQTT_USER..."
curl -sf -X POST http://localhost:$DASH_PORT/api/v5/authentication/password_based:built_in_database/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"$MQTT_USER\", \"password\": \"$MQTT_PASS\"}" >/dev/null

# 修改 Dashboard 密码
info "修改 Dashboard 密码..."
docker exec $CONTAINER_NAME emqx_ctl admins passwd $DASH_USER $DASH_PASS >/dev/null

# --- 6. 验证 ---
info "验证连接..."
docker run --rm --network host \
  eclipse-mosquitto:latest \
  mosquitto_pub -h localhost -p $MQTT_PORT \
    -u $MQTT_USER -P $MQTT_PASS \
    -t "test" -m "ok" -q 1 2>/dev/null && \
  info "MQTT 连接测试通过" || \
  warn "MQTT 连接测试失败，请检查配置"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  EMQX 安装完成${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "  MQTT 地址:  localhost:$MQTT_PORT"
echo "  MQTT 用户:  $MQTT_USER / $MQTT_PASS"
echo "  Dashboard:  http://localhost:$DASH_PORT"
echo "  Dashboard:  $DASH_USER / $DASH_PASS"
echo "  匿名登录:   已关闭"
echo "  开机自启:   docker --restart always"
echo ""
echo "  测试命令:"
echo "    mosquitto_pub -h localhost -p $MQTT_PORT \\"
echo "      -u $MQTT_USER -P $MQTT_PASS -t test -m hello"
echo ""
