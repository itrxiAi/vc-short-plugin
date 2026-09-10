---
name: gen-shots
description: 拆分分镜，将一章小说文本拆分为多个分镜 YAML 文件
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

# 拆分分镜

## 前置条件

运行 `install.sh`（macOS/Linux）或 `install.ps1`（Windows）安装后，`vcshort` 已在 PATH 中，直接调用 `vcshort <command> ...`。

## 前置条件

- 项目已初始化（有 `config.yaml` 和 `chapters/` 目录）
- 该章节已执行过 `/vc-short:extract`，即 `character_map.yaml` 和 `scene_map.yaml` 已存在
- 该章节已执行过 `/vc-short:gen-script`，即 `chapters/<章节号>/script.md` 已存在

## 章节目录结构

```
chapters/ch01/
  novel.md              # 小说原文
  script.md             # 改编剧本（由 /vc-short:gen-script 生成）
  character_map.yaml    # 角色映射（剧本角色名 → assets 目录名）
  scene_map.yaml        # 场景映射（剧本场景描述 → assets 目录名）
  shots/                # 分镜文件（本工作流生成）
    shot_001/
      shot.yaml         # 分镜参数
      shot.mp4          # 生成视频（由 /vc-short:gen-video 生成）
    shot_002/
      shot.yaml
      ...
```

## 输入参数

| 参数 | 说明 | 示例 |
|------|------|------|
| **项目路径** | 项目根目录的绝对路径 | `/Users/.../末日求生` |
| **章节号** | 章节编号 | `ch01` |

## 分镜 YAML 格式

每个分镜一个文件，由 `vcshort gen-shots` 脚本统一生成，保证格式一致。存放在 `chapters/<章节号>/shots/shot_XXX/shot.yaml`：

```yaml
# 分镜 001

shot_id: "001"
chapter: "ch01"

# 剧本片段（原文）
script_segment: |
  对应的小说/剧本原文

# 角色引用（对应 assets 目录名，支持 "角色名:形态名"）
characters:
  - 小帅
  - 小帅:女装

# 场景引用（对应 assets 目录名）
scene: 废弃学校操场

# 镜头参数
camera:
  shot_type: "中景"
  angle: "平视"
  movement: "固定"
  duration: 15

# 生成状态
status: "pending"
keyframe: null
video: null
```

## 执行步骤

### 1. 收集参数

- 确认项目路径
- 确认章节号（如 `ch01`）

### 2. 读取剧本和映射文件

- 读取 `chapters/<章节号>/script.md` 获取剧本内容
- 读取 `chapters/<章节号>/character_map.yaml` 获取角色映射
- 读取 `chapters/<章节号>/scene_map.yaml` 获取场景映射
- 读取 `config.yaml` 获取 style、aspect_ratio
- 如果 `character_map.yaml` 或 `scene_map.yaml` 不存在，提示用户先执行 `/vc-short:extract`

### 3. 分析剧本，拆分分镜

分镜完全按剧本场景走，一个场景对应一个分镜。剧本已在 gen-script 阶段按 15 秒时长拆好，直接将每个场景转为一个分镜。

### 4. 提取角色和场景

从 script_segment 中提取出场角色和场景：
- **characters**：script_segment 中出现的所有角色名
- **scene**：script_segment 所属的场景名

### 5. 检查分镜字数

逐个检查拆分好的分镜，不满足则提示用户重新 gen-script：

- **对白总字数检查**：低字数对白重点检查是否能撑起15s，不能则提示用户合并场景
- **内容足够简洁**：无冗余描述，无重复信息

### 6. 调用脚本写入分镜文件

LLM 将分析结果转为 JSON 数组，写入 `chapters/<章节号>/shots.json`，然后调用：

```bash
vcshort gen-shots <项目路径> \
  --chapter <章节号> [--force]
```

脚本会自动读取 `chapters/<章节号>/shots.json`，生成 YAML 分镜文件后删除该 JSON 文件。

JSON 数组格式（`characters` 使用**剧本角色名**，`scene` 使用**剧本场景描述**，脚本会自动通过 character_map.yaml 和 scene_map.yaml 映射为 assets 目录名）：
```json
[
  {
    "script_segment": "角色名（动作）：台词...",
    "characters": ["角色名A", "角色名B"],
    "scene": "场景名",
    "camera": {"shot_type": "中景", "angle": "平视", "movement": "固定", "duration": 15}
  }
]
```

- 已有分镜文件时，追加 `--force` 覆盖
- 脚本会自动加载 `character_map.yaml` 和 `scene_map.yaml` 进行映射

### 7. 确认结果

- 列出所有生成的分镜（序号、角色、场景、时长）
- 向用户展示分镜列表
- 询问用户是否满意，不满意可调整

## 注意事项

- 分镜拆分要自然，不要把一个完整动作或对白拆到两个分镜
- JSON 中 `characters`、`scene` 使用剧本中的原始名称，脚本自动映射
- 如果映射文件中找不到对应关系，脚本会保留原名称，用户可后续手动修改映射文件后重新生成
- 角色多形态：`character_map.yaml` 的值支持 `角色名:形态名` 格式（如 `小美: 小帅:女装`），映射到 assets 目录 `assets/characters/小帅/小帅-女装.png`
- 所有 YAML 文件由脚本用 ruamel.yaml 生成，格式统一，不要手动编辑 shot YAML
