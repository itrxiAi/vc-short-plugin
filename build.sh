#!/usr/bin/env bash
# 本地构建 vcshort wheel 并验证
set -e

cd "$(dirname "$0")"

echo "==> 检查系统 Python"
PY=""
for cmd in python3 python python3.12 python3.11 python3.10; do
  if command -v "$cmd" >/dev/null 2>&1; then
    PY="$(command -v "$cmd")"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "错误：未找到系统 Python。请先安装 Python 3.10+"
  exit 1
fi
echo "使用: $PY"

echo "==> 安装构建工具"
"$PY" -m pip install -q build

echo "==> 构建 wheel / sdist"
rm -rf dist build
"$PY" -m build

echo "==> 本地安装验证"
"$PY" -m pip install -q --force-reinstall dist/vcshort-*.whl
vcshort --help >/dev/null
vcshort config-list --help >/dev/null

echo ""
echo "✅ 构建完成: dist/"
echo "   发布到 PyPI: python -m twine upload dist/*"
echo "   或 GitHub Actions 自动发布（见 .github/workflows/publish.yml）"
