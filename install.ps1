$ErrorActionPreference = "Stop"
# vc-short-plugin 安装脚本（Windows PowerShell）
# 用法（一行命令安装）：
#   irm https://raw.githubusercontent.com/itrxiAi/vc-short-plugin/main/install.ps1 | iex
# 或本地运行：
#   powershell -ExecutionPolicy Bypass -File install.ps1

# 强制 UTF-8 输出，避免中文乱码（Windows PowerShell 5.1 默认 cp1252）
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$Version = "v0.1.0"
$Repo = "itrxiAi/vc-short-plugin"
$BaseUrl = "https://github.com/$Repo/releases/download/$Version"
$ZipUrl = "https://github.com/$Repo/archive/refs/heads/main.zip"

# ========== 安装目录 ==========
$InstallDir = "$env:USERPROFILE\.vcshort"
$BinDir = "$InstallDir\bin"
$BinName = "vcshort.exe"

Write-Host ""
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "   vc-short-plugin installer" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

# ========== 1. 创建安装目录 ==========
Write-Host "==> [1/4] Install dir: $InstallDir" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

# ========== 2. 下载插件文件 ==========
Write-Host "==> [2/4] Download plugin files..." -ForegroundColor Cyan
$zipPath = "$env:TEMP\vc-short-plugin.zip"
$extractDir = "$env:TEMP\vc-short-plugin-extract"

try {
    Invoke-WebRequest -Uri $ZipUrl -OutFile $zipPath
} catch {
    Write-Host "[ERROR] Download failed: $_" -ForegroundColor Red
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
Write-Host "[OK] Plugin files installed" -ForegroundColor Green

# ========== 3. 下载二进制 ==========
Write-Host "==> [3/4] Download vcshort binary..." -ForegroundColor Cyan
$binPath = "$BinDir\$BinName"
$url = "$BaseUrl/vcshort-windows"

try {
    Invoke-WebRequest -Uri $url -OutFile $binPath
} catch {
    Write-Host "[ERROR] Binary download failed: $_" -ForegroundColor Red
    Write-Host "   Please check Release $Version exists" -ForegroundColor Yellow
    exit 1
}

# 验证
if (& $binPath --help 2>$null) {
    Write-Host "[OK] Binary verified" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Binary verification failed" -ForegroundColor Red
    Remove-Item -Force $binPath -ErrorAction SilentlyContinue
    exit 1
}

# ========== 4. 加入 PATH ==========
Write-Host "==> [4/4] Configure PATH..." -ForegroundColor Cyan
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$BinDir", "User")
    Write-Host "[OK] Added $BinDir to PATH" -ForegroundColor Green
    Write-Host "   Reopen terminal to take effect" -ForegroundColor Yellow
} else {
    Write-Host "[OK] PATH already contains $BinDir" -ForegroundColor Green
}

# ========== 安装到平台 ==========
Write-Host ""
Write-Host "Install to which agent?"
Write-Host "  1) Devin CLI"
Write-Host "  2) Claude Code"
Write-Host "  3) Cursor"
Write-Host "  4) All"
Write-Host "  5) Skip (CLI only)"
Write-Host ""
$choice = Read-Host "Choice [1-5]"

function Install-Devin {
    Write-Host "==> Installing to Devin CLI..." -ForegroundColor Cyan
    if (Get-Command devin -ErrorAction SilentlyContinue) {
        & devin plugins install $InstallDir
        Write-Host "[OK] Devin plugin installed" -ForegroundColor Green
    } else {
        Write-Host "[WARN] devin not found, skipped" -ForegroundColor Yellow
        Write-Host "   After installing Devin CLI: devin plugins install $InstallDir"
    }
}

function Install-Claude {
    Write-Host "==> Installing to Claude Code..." -ForegroundColor Cyan
    $targetDir = "$env:USERPROFILE\.claude\plugins"
    $target = Join-Path $targetDir "vc-short"
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    if (Test-Path $target) {
        Remove-Item -Recurse -Force $target
    }
    cmd /c mklink /J "$target" "$InstallDir" | Out-Null
    Write-Host "[OK] Linked to $target" -ForegroundColor Green
    Write-Host "   Restart Claude Code to take effect"
}

function Install-Cursor {
    Write-Host "==> Installing to Cursor..." -ForegroundColor Cyan
    $targetDir = "$env:USERPROFILE\.cursor\plugins\local"
    $target = Join-Path $targetDir "vc-short"
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    if (Test-Path $target) {
        Remove-Item -Recurse -Force $target
    }
    cmd /c mklink /J "$target" "$InstallDir" | Out-Null
    Write-Host "[OK] Linked to $target" -ForegroundColor Green
    Write-Host "   Restart Cursor or run Developer: Reload Window"
}

switch ($choice) {
    "1" { Install-Devin }
    "2" { Install-Claude }
    "3" { Install-Cursor }
    "4" { Install-Devin; Install-Claude; Install-Cursor }
    "5" { Write-Host "Skipped" -ForegroundColor Yellow }
    default { Write-Host "[ERROR] Invalid choice" -ForegroundColor Red; exit 1 }
}

Write-Host ""
Write-Host "[OK] Installation complete!" -ForegroundColor Green
Write-Host "   Install dir: $InstallDir"
Write-Host "   Verify: reopen terminal, run vcshort --help"
