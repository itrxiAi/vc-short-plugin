---
name: gen-character
description: 生成角色资产（图片+音色），调用 doubao-seedream 生成图片，调用豆包 TTS 生成音色
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

# 生成角色资产

## 前置条件

运行 `install.sh`（macOS/Linux）或 `install.ps1`（Windows）安装后，`vcshort` 已在 PATH 中，直接调用 `vcshort <command> ...`。

- 项目的 `config.yaml` 中已填写 `api.api_key`（火山引擎方舟 API Key）
- `config.yaml` 中已填写 `tts.app_id` 和 `tts.access_key`（火山引擎语音合成凭证）

## 输入参数

需要从用户获取以下信息，缺失的必须逐个确认：

| 参数 | 说明 | 示例 |
|------|------|------|
| **项目路径** | 项目根目录的绝对路径 | `/Users/.../末日求生` |
| **角色名** | 角色名（中文，对应 assets 目录名） | `小帅` |
| **性别** | `male` 或 `female` | `male` |
| **形态名** | 角色形态名（可选，默认 默认） | `女装` |
| **提示词** | 图片生成的描述文本 | `20岁青年，短发，瘦削，穿旧夹克` |

> **角色自动追加"全身照"和"纯白背景"**：脚本会自动在角色提示词后追加，确保上下身一致且背景干净，用户提示词中无需重复写。

## 执行步骤

### 1. 收集参数

逐个检查参数是否已提供。**任何一个缺失都必须向用户确认**，不要使用默认值。

- 如果用户只说了"生成一个角色"但没给名称和提示词 → 先问名称，再问性别，再问提示词
- 如果用户没指定项目路径 → 询问是哪个项目

### 2. 检查角色是否已存在

检查对应目录下是否已有同名图片文件：

- **角色** → `assets/characters/<角色名>/<角色名>.png` 或 `<角色名>-<形态>.png`

如果已存在，告知用户并让其选择：
1. 换一个名字
2. 覆盖（加 `--force` 参数）

### 3. 调用生成脚本

```bash
vcshort gen-image <项目路径> \
  --type character \
  --name <角色名> \
  --gender <male|female> \
  --prompt "<提示词>" \
  --size 2K
```

角色多形态时追加 `--form <形态名>`：
```bash
vcshort gen-image <项目路径> \
  --type character \
  --name <角色名> \
  --form <形态名> \
  --gender <male|female> \
  --prompt "<提示词>" \
  --size 2K
```

- 如果用户要求覆盖，追加 `--force`
- 如果不需要自动生成音色，追加 `--no-voice`
- 如果 `config.yaml` 中指定了不同的 image_model，追加 `--model <模型ID>`

脚本会自动完成：
1. 调用 doubao-seedream API 生成角色图片
2. 保存到 `assets/characters/<角色名>/<角色名>.png`
3. 根据性别从豆包 2.0 音色池随机选一个音色
4. 调用火山引擎 TTS API 生成参考音频
5. 保存到 `assets/characters/<角色名>/<角色名>.mp3`

### 4. 确认结果

脚本执行完成后：
- 向用户展示生成结果（图片路径 + 音色名 + 音频路径）
- 询问用户是否满意
  - 图片不满意 → 加 `--force` 重新生成
  - 音色不满意 → 单独用 `/vc-short:gen-voice` 重新生成音色

```bash
vcshort gen-voice <项目路径> \
  --name <角色名> \
  --gender <male|female> \
  --force
```

## 文件结构

```
assets/characters/<角色名>/
  <角色名>.png          # 角色图片（默认形态）
  <角色名>-<形态>.png    # 其他形态
  <角色名>.mp3          # 音色参考音频
  voice.json            # 音色元数据（记录使用的音色和已用列表）
```

## 类型与目录映射

| 参数 | 目录 | 文件命名 |
|---------|------|---------|
| 角色 | `assets/characters/<角色名>/` | 默认形态 `<角色名>.png`，其他形态 `<角色名>-<形态>.png` |

## 错误处理

- **API Key 未配置** → 提示用户在 `config.yaml` 的 `api.api_key` 中填入火山引擎 API Key
- **TTS 凭证未配置** → 提示在 `config.yaml` 的 `tts.app_id` 和 `tts.access_key` 中填入语音合成凭证
- **网络错误** → 提示重试
- **图片已存在** → 让用户改名或覆盖
- **音色已存在** → 提示加 `--force` 重新生成
- **项目路径不存在** → 提示用户检查路径
