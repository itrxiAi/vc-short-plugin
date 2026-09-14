#!/usr/bin/env bash
# 本地组装便携插件包（与 .github/workflows/build.yml 同逻辑）
# 用法：./build.sh [aarch64-apple-darwin|x86_64-apple-darwin]
# 产物：dist/vc-short-plugin/（可整目录上传 WorkBuddy 技能包，或打 zip 发布）
set -e

cd "$(dirname "$0")"

PBS_PLATFORM="${1:-aarch64-apple-darwin}"
OUT="dist/vc-short-plugin"

echo "==> 解析便携 Python 下载地址（python-build-standalone: ${PBS_PLATFORM}）"
mkdir -p runtime
curl -fsSL -o runtime/pbs.json https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest
URL=$(PBS_PLATFORM="$PBS_PLATFORM" python3 -c "
import json, os
rel = json.load(open('runtime/pbs.json'))
plat = os.environ['PBS_PLATFORM']
assets = [a for a in rel['assets']
          if a['name'].startswith('cpython-3.12')
          and a['name'].endswith('install_only.tar.gz')
          and plat in a['name']
          and 'freethreaded' not in a['name']]
assert assets, 'no matching python-build-standalone asset'
assets.sort(key=lambda a: ('pgo' not in a['name'], 'shared' not in a['name']))
print(assets[0]['browser_download_url'])
")
echo "==> $URL"
curl -fsSL -o runtime/python.tar.gz "$URL"
rm -rf runtime/python
tar -xzf runtime/python.tar.gz -C runtime

PY="runtime/python/bin/python3"
[ -f runtime/python/python.exe ] && PY="runtime/python/python.exe"

echo "==> 安装运行时依赖到便携 Python"
"$PY" -m ensurepip --upgrade
"$PY" -m pip install --no-cache-dir -r requirements.txt

echo "==> 瘦身（移除 pip/ensurepip/idlelib 等非运行时组件）"
SP="$(dirname "$PY")/../lib/python3.12/site-packages"
[ -d "$SP" ] || SP="runtime/python/Lib/site-packages"
rm -rf "$SP/pip" "$SP/setuptools" "$SP/wheel" "$SP/pip-"*.dist-info "$SP/setuptools-"*.dist-info "$SP/wheel-"*.dist-info
rm -rf runtime/python/lib/python3.12/ensurepip runtime/python/lib/python3.12/idlelib \
       runtime/python/lib/python3.12/lib2to3 runtime/python/lib/python3.12/pydoc_data \
       runtime/python/lib/python3.12/tkinter runtime/python/lib/python3.12/turtledemo \
       runtime/python/lib/python3.12/test runtime/python/lib/python3.12/__pycache__
rm -rf runtime/python/Lib/ensurepip runtime/python/Lib/idlelib \
       runtime/python/Lib/lib2to3 runtime/python/Lib/pydoc_data \
       runtime/python/Lib/tkinter runtime/python/Lib/turtledemo \
       runtime/python/Lib/test runtime/python/Lib/__pycache__

echo "==> 组装插件包到 ${OUT}"
rm -rf "$OUT"
mkdir -p "$OUT/bin"
cp -r skills src agents plugin.json AGENTS.md .claude-plugin .devin-plugin .codebuddy-plugin "$OUT/"
cp bin/vcshort bin/vcshort.bat "$OUT/bin/"
cp -r runtime/python "$OUT/python"
chmod +x "$OUT/bin/vcshort"

echo "==> 验证"
"$OUT/bin/vcshort" --help >/dev/null
"$OUT/bin/vcshort" config-list --help >/dev/null

echo ""
echo "✅ 组装完成: ${OUT}"
echo "   测试: ${OUT}/bin/vcshort --help"
echo "   打 zip: (cd dist && zip -qry vcshort-macos.zip vc-short-plugin)"
