#!/usr/bin/env bash
# vc-short-plugin 安装脚本（macOS / Linux）
# 用法：bash install.sh
set -e

cd "$(dirname "$0")"
PLUGIN_ROOT="$(pwd)"

VERSION="v0.1.0"
BASE_URL="https://github.com/itrxiAi/vc-short-plugin/releases/download/${VERSION}"

# ========== 检测 OS ==========
case "$(uname -s)" in
  Darwin*) OS="macos"; BIN_NAME="vcshort" ;;
  Linux*)  OS="linux"; BIN_NAME="vcshort" ;;
  *) echo "❌ 不支持的系统: $(uname -s)"; exit 1 ;;
esac

echo "==> 检测到系统: ${OS}"

# ========== 下载二进制 ==========
download_binary() {
  echo "==> 下载 vcshort ${VERSION} (${OS})..."
  mkdir -p bin
  local url="${BASE_URL}/vcshort-${OS}"
  curl -L --progress-bar -o "bin/${BIN_NAME}" "$url"
  chmod +x "bin/${BIN_NAME}"
  if ./bin/"${BIN_NAME}" --help >/dev/null 2>&1; then
    echo "✅ 下载验证通过"
  else
    echo "❌ 下载失败或文件损坏，请重试"
    rm -f "bin/${BIN_NAME}"
    exit 1
  fi
}

if [ -f "bin/${BIN_NAME}" ]; then
  echo "==> bin/${BIN_NAME} 已存在"
  if ./bin/"${BIN_NAME}" --help >/dev/null 2>&1; then
    echo "✅ 可执行，跳过下载"
  else
    echo "⚠️ 文件损坏，重新下载"
    rm -f "bin/${BIN_NAME}"
    download_binary
  fi
else
  download_binary
fi

# ========== 加入 PATH ==========
install_to_path() {
  local target="/usr/local/bin/vcshort"
  if [ -w "/usr/local/bin" ]; then
    ln -sf "${PLUGIN_ROOT}/bin/${BIN_NAME}" "${target}"
    echo "✅ 已链接到 ${target}"
  else
    echo "⚠️ /usr/local/bin 无写权限，尝试 ~/.local/bin"
    mkdir -p "${HOME}/.local/bin"
    ln -sf "${PLUGIN_ROOT}/bin/${BIN_NAME}" "${HOME}/.local/bin/vcshort"
    echo "✅ 已链接到 ${HOME}/.local/bin/vcshort"
    # 检查是否在 PATH 中
    case ":${PATH}:" in
      *":${HOME}/.local/bin:"*) ;;
      *) echo "⚠️ 请将 ~/.local/bin 加入 PATH：" ;;
         echo "   echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc" ;;
    esac
  fi
}

# ========== 安装到平台 ==========
install_devin() {
  echo "==> 安装到 Devin CLI..."
  if command -v devin >/dev/null 2>&1; then
    devin plugins install "${PLUGIN_ROOT}"
    echo "✅ Devin 插件安装完成"
  else
    echo "❌ 未找到 devin 命令，请先安装 Devin CLI"
    echo "   https://docs.devin.ai"
  fi
}

install_claude() {
  echo "==> 安装到 Claude Code..."
  local target="${HOME}/.claude/plugins/vc-short"
  mkdir -p "${HOME}/.claude/plugins"
  if [ -L "${target}" ] || [ -d "${target}" ]; then
    rm -rf "${target}"
  fi
  ln -sf "${PLUGIN_ROOT}" "${target}"
  echo "✅ 已链接到 ${target}"
  echo "   重启 Claude Code 后生效"
}

install_cursor() {
  echo "==> 安装到 Cursor..."
  local target="${HOME}/.cursor/plugins/local/vc-short"
  mkdir -p "${HOME}/.cursor/plugins/local"
  if [ -L "${target}" ] || [ -d "${target}" ]; then
    rm -rf "${target}"
  fi
  ln -sf "${PLUGIN_ROOT}" "${target}"
  echo "✅ 已链接到 ${target}"
  echo "   重启 Cursor 或运行 Developer: Reload Window 后生效"
}

# ========== 主菜单 ==========
echo ""
echo "选择安装到哪个 agent："
echo "  1) Devin CLI"
echo "  2) Claude Code"
echo "  3) Cursor"
echo "  4) 全部安装"
echo ""
read -p "请输入序号 [1-4]: " choice

case "${choice}" in
  1) install_to_path; install_devin ;;
  2) install_to_path; install_claude ;;
  3) install_to_path; install_cursor ;;
  4) install_to_path; install_devin; install_claude; install_cursor ;;
  *) echo "❌ 无效选择"; exit 1 ;;
esac

echo ""
echo "✅ 安装完成！"
echo "   验证：vcshort --help"
