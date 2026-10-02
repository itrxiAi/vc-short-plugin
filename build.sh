#!/usr/bin/env bash
# 本地组装插件包（用户需自行安装系统 Python 3.10+）
# 用法：./build.sh
# 产物：dist/vc-short-plugin/（可整目录上传 WorkBuddy 技能包，或打 zip 发布）
set -e

cd "$(dirname "$0")"
OUT="dist/vc-short-plugin"

echo "==> 检查系统 Python"
PY=""
for cmd in python3 python python3.12 python3.11 python3.10; do
  if command -v "$cmd" >/dev/null 2>&1; then
    PY="$(command -v "$cmd")"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "错误：未找到系统 Python。请先安装 Python 3.10+（https://www.python.org/downloads/）"
  exit 1
fi
echo "使用: $PY"

echo "==> 组装插件包到 ${OUT}"
rm -rf "$OUT"
mkdir -p "$OUT/bin"
cp -r skills src agents plugin.json AGENTS.md .claude-plugin .devin-plugin .codebuddy-plugin requirements.txt "$OUT/"
cp bin/vcshort bin/vcshort.bat "$OUT/bin/"
chmod +x "$OUT/bin/vcshort"

echo "==> 验证启动器"
"$OUT/bin/vcshort" --help >/dev/null
"$OUT/bin/vcshort" config-list --help >/dev/null

echo ""
echo "✅ 组装完成: ${OUT}"
echo "   用户安装要求：系统 Python 3.10+，并运行 pip install -r requirements.txt"
echo "   测试: ${OUT}/bin/vcshort --help"
echo "   打 zip: (cd dist && zip -qry vcshort.zip vc-short-plugin)"
