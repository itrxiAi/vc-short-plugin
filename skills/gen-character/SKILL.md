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

- `vcshort` 通过 pip 安装（`pip install vcshort`），安装后命令会加入 PATH：
  - 任意 shell：`vcshort <command> ...`
- 下文 `vcshort <command>` 均指该命令
- 若命令不存在：请运行 `pip install --upgrade vcshort` 重新安装

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
| **参考图** | 可选，风格参考图路径（多张逗号分隔），保风格一致，形象按提示词走 | `assets/characters/陈青源/陈青源.png` |
| **面部参考图** | 可选，`--face-image`，抽卡脸裁格路径，需与 `--costume-image` 同用 | `抽卡/抽卡-青年男01-cell5.png` |
| **服装参考图** | 可选，`--costume-image`，服装选型/选色图裁格路径 | `costumes/军校常服-选型-cell3.png` |

> **角色自动追加四视图构图指令**：脚本默认生成"四视图设定图（1×4横排：正面全身/侧面全身/背面全身/面部特写）+ 纯白背景"，让视频模型在生成不同角度镜头时保持身份一致。
>
> **脸+服装拼接模式（`--face-image` + `--costume-image`）**：从抽卡格图/服装选型格图中裁出选定格，作为强参考图传入——生成时面部五官、发型严格与图1一致，服装款式、配色、结构严格与图2一致（与 `--ref-image` 的"仅参考风格"语义相反，两者不可同用）。**此模式下不传 `--prompt`，不写任何人物形象词**——脸和衣服已被参考图锁死，写了只会把形象带偏。裁格用技能自带脚本：`python3 <本skill目录>/scripts/crop_cell.py <网格图> <输出.png> --cell <格号>`（默认4×2网格，`--cols/--rows`可改）。

## 执行步骤

### 1. 收集参数

逐个检查参数是否已提供。**任何一个缺失都必须向用户确认**，不要使用默认值。

- 如果用户只说了"生成一个角色"但没给名称和提示词 → 先问名称，再问性别，再问提示词
- 如果用户没指定项目路径 → 询问是哪个项目

### 2. 检查角色是否已存在

检查对应目录下是否已有同名图片文件：

- **角色** → `assets/characters/<角色名>/<角色名>.png`（默认形态）或 `assets/characters/<角色名>/<角色名>-<形态>.png`（多形态）。**一个角色只建一个目录，不同形态追加 `--form <形态名>` 生成同目录下的多个图片**

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
- 如果用户提供了参考图（保持画风一致），追加 `--ref-image <参考图路径>`（多张逗号分隔）
- 脸+服装拼接示例：

```bash
vcshort gen-image <项目路径> \
  --type character \
  --name <角色名> \
  --gender <male|female> \
  --prompt "<体型/气质等补充>" \
  --face-image <抽卡格图路径> \
  --costume-image <服装格图路径> \
  --size 2K
```

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
assets/characters/<角色名>/        # 一个角色一个目录
  <角色名>.png          # 角色图片（默认形态）
  <角色名>-<形态>.png    # 其他形态（同一目录下）
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
