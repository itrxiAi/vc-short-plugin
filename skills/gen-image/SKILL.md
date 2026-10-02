---
name: gen-image
description: 生成图片资产（服装/道具/场景/面部抽卡），调用 doubao-seedream API 生成并保存到 assets 目录
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

> **角色生成请用 `/vc-short:gen-character`**，本工作流仅用于服装/道具/场景/面部抽卡。

## 前置条件

- `vcshort` CLI 固定安装在 `~/.vc-short/`（Windows 为 `%USERPROFILE%\.vc-short`），自带 Python 运行时，无需系统安装 Python：
  - bash / Git Bash / macOS / Linux：`~/.vc-short/bin/vcshort <command> ...`
  - Windows cmd / PowerShell：`%USERPROFILE%\.vc-short\bin\vcshort.bat <command> ...`
- 下文 `vcshort <command>` 均指上述完整路径
- 若该路径不存在：代用户安装运行时——下载 `https://github.com/itrxiAi/vc-short-plugin/releases/latest/download/vcshort-macos.zip`（Windows 用 `vcshort-windows.zip`），解压并把其中的 `vc-short-plugin` 文件夹移动为 `~/.vc-short`（Windows 为 `%USERPROFILE%\.vc-short`），装好后重试

- 项目的 `config.yaml` 中已填写 `api.api_key`（火山引擎方舟 API Key）
- 用户已在某个视频项目目录中（含 `config.yaml` 和 `assets/` 结构）

## 输入参数

需要从用户获取以下信息，缺失的必须逐个确认：

| 参数 | 说明 | 示例 |
|------|------|------|
| **项目路径** | 项目根目录的绝对路径 | `/Users/.../末日求生` |
| **资产类型** | `costume` / `prop` / `scene` / `face` | `scene` |
| **资产名称** | 资产名称（中文，对应 assets 目录名） | `废弃学校操场` |
| **提示词** | 图片生成的描述文本 | `废弃学校操场，末日废墟氛围，搭满帐篷` |

> **服装生成的是8格展示图**：服装类型自动生成"4列2行网格、不出现人物"的8格服装展示图，整张保存为一个资产文件。两种模式：
> - **选色图**（默认）：同一款式8种配色；要指定配色就在提示词里写颜色列表
> - **选型图**（加 `--designs`）：同一风格主题下8款不同设计，用于筛选款式；可用 `--ref-image` 指定参考风格，也可纯文字描述
> - **命名规则**：`<服装用途>-选型.png` / `<服装用途>-选色.png`，如 `军校常服-选型.png`、`休闲服-选色.png`——服装用途是剧本里的着装身份（如 军校常服/教官作训服/联盟礼服），不是角色名
>
> **场景生成的是4景别设定图**：场景类型自动生成"2列×2行网格"的同一环境4个景别梯度画面（远景俯瞰/全景/中景/近景特写，构图、一致性约束由脚本追加），并自动追加"不要出现人物"，避免干扰后续图生视频。
>
> **面部抽卡（`--type face`）**：一张图生成"4列2行网格"的8张不同面部肖像，保存到 `assets/characters/抽卡/<名称>.png`，用于给角色抽脸。
> - **命名规则**：`抽卡-<年龄段><性别><批次>`，如 `抽卡-青年男01.png`、`抽卡-老年男08.png`——批次号按年龄段+性别独立递增，和群演格图命名同构但带 `抽卡-` 前缀避免混淆
> - **年龄段词表**（face/extra 共用，命名和 `--age` 只用这五档）：`儿童`（~6-12 岁）、`少年`（~13-17 岁）、`青年`（~18-30 岁）、`中年`（~30-45 岁）、`老年`（60+ 岁）
> - `--age` 指定年龄段（用上表词），`--gender` 指定性别，`--hair` 指定发型整体偏向（八格发型仍各异），`--prompt` 补充其他特征（脸型/风格等），可只用部分参数
> - 同样自动追加防写实约束；可用 `--ref-image` 参考已有角色图保持画风
> - 用户挑中某格后，裁出该格作为 `gen-character` 的面部参考图
>
> **群演格图（`--type extra`）**：一张图生成 4 格不同人物的全身立像（4列×1行横排，`--cells 8` 可改回 4列×2行8格），保存到 `assets/characters/群演/<名称>.png`。参数同 face（`--age`/`--gender`/`--prompt`），可配 `--ref-image` 锁定服装款式。
> - **命名规则**：`<年龄段><性别><批次>`，如 `青年男1.png`、`青年男2.png`、`青年女1.png`——同一批次是一张格图，批次号区分多张；年龄段用上表五档词（儿童/少年/青年/中年/老年）
> - **引用规则**：分镜/character_map 里写 `群演-<格图名>#<格号>`，如 `群演-青年男1#3` 表示 `青年男1.png` 第3格；运行时会自动裁格缓存为 `群演/青年男1-3.png` 平铺文件，不需要为群演建单独子目录
> - 兼容旧写法：`群演1` → `群演/群演1.png` 平铺文件
> **角色自动追加"防写实约束"**：gen-character/gen-image 生成角色图时，脚本自动追加"最终幻想式3D CG风格，影视级角色建模，非真人照片、非写实摄影"——角色脸部过度写实会被视频 API 审核判定为真人（`InputImageSensitiveContentDetected.PrivacyInformation`）导致 gen-video 提交失败。角色图被审核拦截时，用 `/vc-short:fix-image` 把面部往风格化方向调整后重试。

## 执行步骤

### 1. 收集参数

逐个检查参数是否已提供。**任何一个缺失都必须向用户确认**，不要使用默认值。

- 如果用户没指定项目路径 → 询问是哪个项目

### 2. 检查图片是否已存在

检查对应目录下是否已有同名图片文件（场景支持多张，不检查）：

- **服装** → `assets/costumes/<服装名>.png`
- **道具** → `assets/props/<道具名>/<道具名>.png`（与 prop.yaml 同目录）
- **面部抽卡** → `assets/characters/抽卡/<名称>.png`
- **群演格图** → `assets/characters/群演/<名称>.png`

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
- 面部抽卡示例：

```bash
vcshort gen-image <项目路径> \
  --type face \
  --name 抽卡-青年男01 \
  --age 青年 --gender male --hair 短寸 \
  --prompt "气质冷峻" \
  --size 2K
```

### 4. 确认结果

脚本执行完成后：
- 向用户展示生成结果（图片路径）
- 询问用户是否满意，不满意可重新生成

## 类型与目录映射

| 类型参数 | 目录 | 文件命名 |
|---------|------|---------|
| `costume` | `assets/costumes/` | `<服装用途>-选型.png` / `<服装用途>-选色.png` |
| `prop` | `assets/props/<道具名>/` | `<道具名>.png`（与 prop.yaml 同目录） |
| `scene` | `assets/scenes/<场景名>/` | `<N>.png`（数字递增，支持多张） |
| `face` | `assets/characters/抽卡/` | `抽卡-<年龄段><性别><批次>.png`（8格肖像抽卡图，如 `抽卡-老年男08.png`） |
| `extra` | `assets/characters/群演/` | `<年龄段><性别><批次>.png`（4格全身立像，如 `青年男1.png`） |

## 错误处理

- **API Key 未配置** → 提示用户在 `config.yaml` 的 `api.api_key` 中填入火山引擎 API Key
- **网络错误** → 提示重试
- **图片已存在** → 让用户改名或覆盖
- **项目路径不存在** → 提示用户检查路径
