# vc-short-plugin 安装脚本（Windows PowerShell）
# 用法（一行命令安装）：
#   irm https://raw.githubusercontent.com/itrxiAi/vc-short-plugin/main/install.ps1 | iex
# 或本地运行：
#   powershell -ExecutionPolicy Bypass -File install.ps1
$ErrorActionPreference = "Stop"

$Version = "v0.1.0"
$Repo = "itrxiAi/vc-short-plugin"
$BaseUrl = "https://github.com/$Repo/releases/download/$Version"
$ZipUrl = "https://github.com/$Repo/archive/refs/heads/main.zip"

# ========== 安装目录 ==========
$InstallDir = "$env:USERPROFILE\.vcshort"
$BinDir = "$InstallDir\bin"
$BinName = "vcshort.exe"

Write-Host ""
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   vc-short-plugin 安装程序           ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ========== 1. 创建安装目录 ==========
Write-Host "==> [1/4] 创建安装目录: $InstallDir" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

# ========== 2. 下载插件文件 ==========
Write-Host "==> [2/4] 下载插件文件..." -ForegroundColor Cyan
$zipPath = "$env:TEMP\vc-short-plugin.zip"
$extractDir = "$env:TEMP\vc-short-plugin-extract"

try {
    Invoke-WebRequest -Uri $ZipUrl -OutFile $zipPath -ProgressAction Continue
} catch {
    Write-Host "❌ 下载插件文件失败: $_" -ForegroundColor Red
    exit 1
}

# 解压
if (Test-Path $extractDir) {
    Remove-Item -Recurse -Force $extractDir
}
Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

# 复制插件文件到安装目录（仓库 zip 解压后是 vc-short-plugin-main/ 子目录）
$sourceDir = Get-ChildItem -Directory $extractDir | Select-Object -First 1
$pluginFiles = @("skills", ".devin-plugin", ".claude-plugin", "plugin.json", "AGENTS.md")
foreach ($item in $pluginFiles) {
    $src = Join-Path $sourceDir.FullName $item
    if (Test-Path $src) {
        $dst = Join-Path $InstallDir $item
        if (Test-Path $dst) {
            Remove-Item -Recurse -Force $dst
        }
        Copy-Item -Recurse -Force $src $dst
    }
}

# 清理临时文件
Remove-Item -Force $zipPath -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $extractDir -ErrorAction SilentlyContinue
Write-Host "✅ 插件文件已安装" -ForegroundColor Green

# ========== 3. 下载二进制 ==========
Write-Host "==> [3/4] 下载 vcshort 二进制..." -ForegroundColor Cyan
$binPath = "$BinDir\$BinName"
$url = "$BaseUrl/vcshort-windows"

try {
    Invoke-WebRequest -Uri $url -OutFile $binPath -ProgressAction Continue
} catch {
    Write-Host "❌ 下载二进制失败: $_" -ForegroundColor Red
    Write-Host "   请检查 Release $Version 是否已发布" -ForegroundColor Yellow
    exit 1
}

# 验证
if (& $binPath --help 2>$null) {
    Write-Host "✅ 二进制验证通过" -ForegroundColor Green
} else {
    Write-Host "❌ 二进制验证失败，文件可能损坏" -ForegroundColor Red
    Remove-Item -Force $binPath -ErrorAction SilentlyContinue
    exit 1
}

# ========== 4. 加入 PATH ==========
Write-Host "==> [4/4] 配置 PATH..." -ForegroundColor Cyan
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$BinDir", "User")
    Write-Host "✅ 已将 $BinDir 加入用户 PATH" -ForegroundColor Green
    Write-Host "   请重新打开终端使 PATH 生效" -ForegroundColor Yellow
} else {
    Write-Host "✅ PATH 已包含 $BinDir" -ForegroundColor Green
}

# ========== 安装到平台 ==========
Write-Host ""
Write-Host "选择安装到哪个 agent："
Write-Host "  1) Devin CLI"
Write-Host "  2) Claude Code"
Write-Host "  3) Cursor"
Write-Host "  4) 全部安装"
Write-Host "  5) 跳过（仅安装 CLI）"
Write-Host ""
$choice = Read-Host "请输入序号 [1-5]"

function Install-Devin {
    Write-Host "==> 安装到 Devin CLI..." -ForegroundColor Cyan
    if (Get-Command devin -ErrorAction SilentlyContinue) {
        & devin plugins install $InstallDir
        Write-Host "✅ Devin 插件安装完成" -ForegroundColor Green
    } else {
        Write-Host "⚠️ 未找到 devin 命令，跳过" -ForegroundColor Yellow
        Write-Host "   安装 Devin CLI 后运行: devin plugins install $InstallDir"
    }
}

function Install-Claude {
    Write-Host "==> 安装到 Claude Code..." -ForegroundColor Cyan
    $targetDir = "$env:USERPROFILE\.claude\plugins"
    $target = Join-Path $targetDir "vc-short"
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    if (Test-Path $target) {
        Remove-Item -Recurse -Force $target
    }
    cmd /c mklink /J "$target" "$InstallDir" | Out-Null
    Write-Host "✅ 已链接到 $target" -ForegroundColor Green
    Write-Host "   重启 Claude Code 后生效"
}

function Install-Cursor {
    Write-Host "==> 安装到 Cursor..." -ForegroundColor Cyan
    $targetDir = "$env:USERPROFILE\.cursor\plugins\local"
    $target = Join-Path $targetDir "vc-short"
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    if (Test-Path $target) {
        Remove-Item -Recurse -Force $target
    }
    cmd /c mklink /J "$target" "$InstallDir" | Out-Null
    Write-Host "✅ 已链接到 $target" -ForegroundColor Green
    Write-Host "   重启 Cursor 或运行 Developer: Reload Window 后生效"
}

switch ($choice) {
    "1" { Install-Devin }
    "2" { Install-Claude }
    "3" { Install-Cursor }
    "4" { Install-Devin; Install-Claude; Install-Cursor }
    "5" { Write-Host "跳过插件安装" -ForegroundColor Yellow }
    default { Write-Host "❌ 无效选择" -ForegroundColor Red; exit 1 }
}

Write-Host ""
Write-Host "✅ 安装完成！" -ForegroundColor Green
Write-Host "   安装目录: $InstallDir"
Write-Host "   验证: 重新打开终端后运行 vcshort --help"
