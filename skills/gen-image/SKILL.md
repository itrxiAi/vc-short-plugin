---
name: gen-image
description: 生成图片资产（角色/服装/道具/场景），调用 doubao-seedream API 生成并保存到 assets 目录
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

## 定位 vcshort 可执行文件

本插件自带 CLI 工具 `vcshort`，位于插件根目录的 `bin/vcshort`。首次调用先定位：
```bash
devin skills show vc-short:gen-image
```
`Base directory` 向上两级即为插件根目录，可执行文件在 `<插件根>/bin/vcshort`。

## 前置条件

- 项目的 `config.yaml` 中已填写 `api.api_key`（火山引擎方舟 API Key）
- 用户已在某个视频项目目录中（含 `config.yaml` 和 `assets/` 结构）

## 输入参数

需要从用户获取以下信息，缺失的必须逐个确认：

| 参数 | 说明 | 示例 |
|------|------|------|
| **项目路径** | 项目根目录的绝对路径 | `/Users/.../末日求生` |
| **资产类型** | `character` / `costume` / `prop` / `scene` | `character` |
| **资产名称** | 角色名/场景名（中文，对应 assets 目录名） | `小帅` |
| **形态名** | 角色形态名（仅 type=character，可选，默认 默认） | `女装` |
| **提示词** | 图片生成的描述文本 | `20岁青年，短发，瘦削，穿旧夹克，动漫3D风格` |

> **角色自动追加"全身照"**：脚本会自动在角色提示词后追加"全身照"，确保上下身一致，用户提示词中无需重复写。

## 执行步骤

### 1. 收集参数

逐个检查参数是否已提供。**任何一个缺失都必须向用户确认**，不要使用默认值。

- 如果用户只说了"生成一个角色"但没给名称和提示词 → 先问名称，再问提示词
- 如果用户没指定项目路径 → 询问是哪个项目

### 2. 检查图片是否已存在

检查对应目录下是否已有同名图片文件（场景支持多张，不检查）：

- **角色** → `assets/characters/<角色名>/<角色名>.png` 或 `<角色名>-<形态>.png`
- **服装** → `assets/costumes/<服装名>.png`
- **道具** → `assets/props/<道具名>.png`

如果已存在，告知用户并让其选择：
1. 换一个名字
2. 覆盖（加 `--force` 参数）

### 3. 调用生成脚本

```bash
<插件根>/bin/vcshort gen-image <项目路径> \
  --type <类型> \
  --name <名称> \
  --prompt "<提示词>" \
  --size 2K
```

角色多形态时追加 `--form <形态名>`：
```bash
<插件根>/bin/vcshort gen-image <项目路径> \
  --type character \
  --name <角色名> \
  --form <形态名> \
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
| `character` | `assets/characters/<角色名>/` | 默认形态 `<角色名>.png`，其他形态 `<角色名>-<形态>.png` |
| `costume` | `assets/costumes/` | `<服装名>.png` |
| `prop` | `assets/props/` | `<道具名>.png` |
| `scene` | `assets/scenes/<场景名>/` | `<N>.png`（数字递增，支持多张） |

## 错误处理

- **API Key 未配置** → 提示用户在 `config.yaml` 的 `api.api_key` 中填入火山引擎 API Key
- **网络错误** → 提示重试
- **图片已存在** → 让用户改名或覆盖
- **项目路径不存在** → 提示用户检查路径
