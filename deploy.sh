#!/usr/bin/env bash
set -euo pipefail

echo "========================================"
echo "  Docx-Formatter 一键部署脚本"
echo "========================================"
echo ""

# 检查依赖
command -v docker >/dev/null 2>&1 || { echo "❌ Docker 未安装，请先安装 Docker"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "❌ Docker Compose 未安装，请先安装 Docker Compose"; exit 1; }

echo "✅ Docker 检查通过"
echo ""

# 启用 BuildKit 以支持缓存挂载，加速重复构建
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# 构建并启动
echo "🔨 开始构建镜像并启动服务..."
docker compose up --build -d

echo ""
echo "✅ 部署完成！"
echo ""
echo "📄 服务地址: http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "常用命令:"
echo "  查看日志: docker compose logs -f"
echo "  停止服务: docker compose down"
echo "  重启服务: docker compose restart"
