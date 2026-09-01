#!/usr/bin/env bash
# 下载 vcshort 二进制到 bin/ 目录
# 用法：./download.sh
set -e

cd "$(dirname "$0")"

VERSION="v0.1.0"
URL="https://github.com/itrxiAi/vc-short-plugin/releases/download/${VERSION}/vcshort"

if [ -f "bin/vcshort" ]; then
  echo "bin/vcshort 已存在，跳过下载"
  ./bin/vcshort --help >/dev/null 2>&1 && echo "✅ 可执行" || { echo "⚠️ 文件损坏，重新下载"; rm -f bin/vcshort; }
  [ -f "bin/vcshort" ] && exit 0
fi

echo "==> 下载 vcshort ${VERSION}（约 137MB）"
mkdir -p bin
curl -L --progress-bar -o bin/vcshort "$URL"
chmod +x bin/vcshort

echo ""
echo "✅ 下载完成: bin/vcshort"
./bin/vcshort --help >/dev/null 2>&1 && echo "✅ 验证通过" || { echo "❌ 下载失败或文件损坏，请重试"; exit 1; }
