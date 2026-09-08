#!/usr/bin/env bash
# vc-short-plugin 安装脚本（macOS / Linux）
# 用法（一行命令安装）：
#   curl -fsSL https://raw.githubusercontent.com/itrxiAi/vc-short-plugin/main/install.sh | bash
# 或本地运行：
#   bash install.sh
set -e

VERSION="v0.1.0"
REPO="itrxiAi/vc-short-plugin"
BASE_URL="https://github.com/${REPO}/releases/download/${VERSION}"
ZIP_URL="https://github.com/${REPO}/archive/refs/heads/main.zip"

INSTALL_DIR="${HOME}/.vcshort"
BIN_DIR="${INSTALL_DIR}/bin"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   vc-short-plugin 安装程序           ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ========== 检测 OS ==========
case "$(uname -s)" in
  Darwin*) OS="macos"; BIN_NAME="vcshort" ;;
  Linux*)  OS="linux"; BIN_NAME="vcshort" ;;
  *) echo "❌ 不支持的系统: $(uname -s)"; exit 1 ;;
esac

echo "==> 检测到系统: ${OS}"

# ========== 1. 创建安装目录 ==========
echo "==> [1/4] 创建安装目录: ${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}"
mkdir -p "${BIN_DIR}"

# ========== 2. 下载插件文件 ==========
echo "==> [2/4] 下载插件文件..."
TMP_DIR=$(mktemp -d)
trap "rm -rf ${TMP_DIR}" EXIT

ZIP_PATH="${TMP_DIR}/vc-short-plugin.zip"
curl -fsSL -o "${ZIP_PATH}" "${ZIP_URL}"

# 解压
EXTRACT_DIR="${TMP_DIR}/extract"
mkdir -p "${EXTRACT_DIR}"
if command -v unzip >/dev/null 2>&1; then
  unzip -q "${ZIP_PATH}" -d "${EXTRACT_DIR}"
else
  echo "❌ 需要 unzip 命令，请先安装：brew install unzip / apt install unzip"
  exit 1
fi

# 仓库 zip 解压后是 vc-short-plugin-main/ 子目录
SOURCE_DIR="${EXTRACT_DIR}/vc-short-plugin-main"
if [ ! -d "${SOURCE_DIR}" ]; then
  # 兜底：找第一个子目录
  SOURCE_DIR=$(ls -d "${EXTRACT_DIR}"/*/ | head -1)
fi

# 复制插件文件到安装目录
for item in skills .devin-plugin .claude-plugin plugin.json AGENTS.md; do
  if [ -e "${SOURCE_DIR}/${item}" ]; then
    rm -rf "${INSTALL_DIR}/${item}"
    cp -r "${SOURCE_DIR}/${item}" "${INSTALL_DIR}/${item}"
  fi
done

echo "✅ 插件文件已安装"

# ========== 3. 下载二进制 ==========
echo "==> [3/4] 下载 vcshort 二进制..."
BIN_PATH="${BIN_DIR}/${BIN_NAME}"
URL="${BASE_URL}/vcshort-${OS}"

curl -fsSL -o "${BIN_PATH}" "${URL}"
chmod +x "${BIN_PATH}"

if "${BIN_PATH}" --help >/dev/null 2>&1; then
  echo "✅ 二进制验证通过"
else
  echo "❌ 二进制验证失败，文件可能损坏"
  rm -f "${BIN_PATH}"
  exit 1
fi

# ========== 4. 加入 PATH ==========
echo "==> [4/4] 配置 PATH..."

# 检测 shell 配置文件
detect_shell_rc() {
  case "${SHELL}" in
    */zsh)  echo "${HOME}/.zshrc" ;;
    */bash) echo "${HOME}/.bashrc" ;;
    *) echo "${HOME}/.profile" ;;
  esac
}

SHELL_RC=$(detect_shell_rc)
PATH_LINE="export PATH=\"${BIN_DIR}:\$PATH\""

# 检查是否已在 PATH 中
case ":${PATH}:" in
  *":${BIN_DIR}:"*)
    echo "✅ PATH 已包含 ${BIN_DIR}"
    ;;
  *)
    # 检查是否已在 shell 配置文件中
    if [ -f "${SHELL_RC}" ] && grep -q "${BIN_DIR}" "${SHELL_RC}" 2>/dev/null; then
      echo "✅ PATH 配置已存在于 ${SHELL_RC}"
    else
      echo "" >> "${SHELL_RC}"
      echo "# vcshort" >> "${SHELL_RC}"
      echo "${PATH_LINE}" >> "${SHELL_RC}"
      echo "✅ 已将 ${BIN_DIR} 加入 ${SHELL_RC}"
      echo "   请重新打开终端或运行: source ${SHELL_RC}"
    fi
    ;;
esac

# ========== 安装到平台 ==========
install_devin() {
  echo "==> Installing to Devin..."
  if command -v devin >/dev/null 2>&1; then
    devin plugins install --local "${INSTALL_DIR}"
    echo "✅ Devin plugin installed"
  else
    echo "⚠️ devin not found, skipped"
    echo "   After installing Devin CLI, run:"
    echo "   devin plugins install --local ${INSTALL_DIR}"
  fi
}

install_claude() {
  echo "==> 安装到 Claude Code..."
  local target="${HOME}/.claude/plugins/vc-short"
  mkdir -p "${HOME}/.claude/plugins"
  if [ -L "${target}" ] || [ -d "${target}" ]; then
    rm -rf "${target}"
  fi
  ln -sf "${INSTALL_DIR}" "${target}"
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
  ln -sf "${INSTALL_DIR}" "${target}"
  echo "✅ 已链接到 ${target}"
  echo "   重启 Cursor 或运行 Developer: Reload Window 后生效"
}

echo ""
echo "选择安装到哪个 agent："
echo "  1) Devin CLI"
echo "  2) Claude Code"
echo "  3) Cursor"
echo "  4) 全部安装"
echo "  5) 跳过（仅安装 CLI）"
echo ""
read -p "请输入序号 [1-5]: " choice

case "${choice}" in
  1) install_devin ;;
  2) install_claude ;;
  3) install_cursor ;;
  4) install_devin; install_claude; install_cursor ;;
  5) echo "跳过插件安装" ;;
  *) echo "❌ 无效选择"; exit 1 ;;
esac

echo ""
echo "✅ 安装完成！"
echo "   安装目录: ${INSTALL_DIR}"
echo "   验证: 重新打开终端后运行 vcshort --help"
