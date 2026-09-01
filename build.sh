#!/usr/bin/env bash
# 打包 vcshort 为单文件可执行程序
# 用法：./build.sh
set -e

cd "$(dirname "$0")"

echo "==> 安装依赖"
pip install -r requirements.txt

echo "==> 清理旧产物"
rm -rf build dist
rm -f bin/vcshort

echo "==> 运行 PyInstaller"
pyinstaller vcshort.spec --clean

echo "==> 复制到 bin/"
mkdir -p bin
cp dist/vcshort bin/vcshort

echo ""
echo "✅ 打包完成: bin/vcshort"
echo "   测试: ./bin/vcshort --help"
