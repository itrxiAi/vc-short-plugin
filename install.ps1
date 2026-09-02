# vc-short-plugin 安装脚本（Windows PowerShell）
# 用法：powershell -ExecutionPolicy Bypass -File install.ps1
$ErrorActionPreference = "Stop"

$PluginRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $PluginRoot

$Version = "v0.1.0"
$BaseUrl = "https://github.com/itrxiAi/vc-short-plugin/releases/download/$Version"
$BinName = "vcshort.exe"

# ========== 下载二进制 ==========
function Download-Binary {
    Write-Host "==> 下载 vcshort $Version (windows)..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Force -Path "bin" | Out-Null
    $url = "$BaseUrl/vcshort-windows"
    $output = "bin\$BinName"
    try {
        Invoke-WebRequest -Uri $url -OutFile $output -ProgressAction Continue
    } catch {
        Write-Host "❌ 下载失败: $_" -ForegroundColor Red
        Remove-Item -Force $output -ErrorAction SilentlyContinue
        exit 1
    }
    if (& ".\bin\$BinName" --help 2>$null) {
        Write-Host "✅ 下载验证通过" -ForegroundColor Green
    } else {
        Write-Host "❌ 下载失败或文件损坏，请重试" -ForegroundColor Red
        Remove-Item -Force $output -ErrorAction SilentlyContinue
        exit 1
    }
}

if (Test-Path "bin\$BinName") {
    Write-Host "==> bin\$BinName 已存在"
    if (& ".\bin\$BinName" --help 2>$null) {
        Write-Host "✅ 可执行，跳过下载" -ForegroundColor Green
    } else {
        Write-Host "⚠️ 文件损坏，重新下载" -ForegroundColor Yellow
        Remove-Item -Force "bin\$BinName"
        Download-Binary
    }
} else {
    Download-Binary
}

# ========== 加入 PATH ==========
function Install-ToPath {
    $targetDir = "$env:USERPROFILE\.local\bin"
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    $target = Join-Path $targetDir $BinName
    Copy-Item -Force "bin\$BinName" $target
    Write-Host "✅ 已复制到 $target" -ForegroundColor Green

    # 检查是否在 PATH 中
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$targetDir*") {
        [Environment]::SetEnvironmentVariable("Path", "$userPath;$targetDir", "User")
        Write-Host "✅ 已将 $targetDir 加入用户 PATH" -ForegroundColor Green
        Write-Host "   请重新打开终端使 PATH 生效" -ForegroundColor Yellow
    }
}

# ========== 安装到平台 ==========
function Install-Devin {
    Write-Host "==> 安装到 Devin CLI..." -ForegroundColor Cyan
    if (Get-Command devin -ErrorAction SilentlyContinue) {
        & devin plugins install $PluginRoot
        Write-Host "✅ Devin 插件安装完成" -ForegroundColor Green
    } else {
        Write-Host "❌ 未找到 devin 命令，请先安装 Devin CLI" -ForegroundColor Red
        Write-Host "   https://docs.devin.ai"
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
    # Windows 不支持 symlink，用 junction
    cmd /c mklink /J "$target" "$PluginRoot" | Out-Null
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
    cmd /c mklink /J "$target" "$PluginRoot" | Out-Null
    Write-Host "✅ 已链接到 $target" -ForegroundColor Green
    Write-Host "   重启 Cursor 或运行 Developer: Reload Window 后生效"
}

# ========== 主菜单 ==========
Write-Host ""
Write-Host "选择安装到哪个 agent："
Write-Host "  1) Devin CLI"
Write-Host "  2) Claude Code"
Write-Host "  3) Cursor"
Write-Host "  4) 全部安装"
Write-Host ""
$choice = Read-Host "请输入序号 [1-4]"

switch ($choice) {
    "1" { Install-ToPath; Install-Devin }
    "2" { Install-ToPath; Install-Claude }
    "3" { Install-ToPath; Install-Cursor }
    "4" { Install-ToPath; Install-Devin; Install-Claude; Install-Cursor }
    default { Write-Host "❌ 无效选择" -ForegroundColor Red; exit 1 }
}

Write-Host ""
Write-Host "✅ 安装完成！" -ForegroundColor Green
Write-Host "   验证：vcshort --help"
