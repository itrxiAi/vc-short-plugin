---
name: gen-image
description: 生成图片资产（服装/道具/场景），调用 doubao-seedream API 生成并保存到 assets 目录
allowed-tools:
  - read
  - write
  - edit
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

# 生成图片资产

> **角色生成请用 `/vc-short:gen-character`**，本工作流仅用于服装/道具/场景。

## 前置条件

运行 `install.sh`（macOS/Linux）或 `install.ps1`（Windows）安装后，`vcshort` 已在 PATH 中，直接调用 `vcshort <command> ...`。

- 项目的 `config.yaml` 中已填写 `api.api_key`（火山引擎方舟 API Key）
- 用户已在某个视频项目目录中（含 `config.yaml` 和 `assets/` 结构）

## 输入参数

需要从用户获取以下信息，缺失的必须逐个确认：

| 参数 | 说明 | 示例 |
|------|------|------|
| **项目路径** | 项目根目录的绝对路径 | `/Users/.../末日求生` |
| **资产类型** | `costume` / `prop` / `scene` | `scene` |
| **资产名称** | 资产名称（中文，对应 assets 目录名） | `废弃学校操场` |
| **提示词** | 图片生成的描述文本 | `废弃学校操场，末日废墟氛围，搭满帐篷` |

> **场景自动追加"不要出现人物"**：脚本会自动在场景提示词后追加"不要出现人物"，避免干扰后续图生视频。

## 执行步骤

### 1. 收集参数

逐个检查参数是否已提供。**任何一个缺失都必须向用户确认**，不要使用默认值。

- 如果用户没指定项目路径 → 询问是哪个项目

### 2. 检查图片是否已存在

检查对应目录下是否已有同名图片文件（场景支持多张，不检查）：

- **服装** → `assets/costumes/<服装名>.png`
- **道具** → `assets/props/<道具名>.png`

如果已存在，告知用户并让其选择：
1. 换一个名字
2. 覆盖（加 `--force` 参数）

### 3. 调用生成脚本

```bash
vcshort gen-image <项目路径> \
  --type <类型> \
  --name <名称> \
  --prompt "<提示词>" \
  --size 2K
```

- 如果用户要求覆盖，追加 `--force`
- 如果 `config.yaml` 中指定了不同的 image_model，追加 `--model <模型ID>`

### 4. 确认结果

脚本执行完成后：
- 向用户展示生成结果（图片路径）
- 询问用户是否满意，不满意可重新生成

## 类型与目录映射

| 类型参数 | 目录 | 文件命名 |
|---------|------|---------|
| `costume` | `assets/costumes/` | `<服装名>.png` |
| `prop` | `assets/props/` | `<道具名>.png` |
| `scene` | `assets/scenes/<场景名>/` | `<N>.png`（数字递增，支持多张） |

## 错误处理

- **API Key 未配置** → 提示用户在 `config.yaml` 的 `api.api_key` 中填入火山引擎 API Key
- **网络错误** → 提示重试
- **图片已存在** → 让用户改名或覆盖
- **项目路径不存在** → 提示用户检查路径
