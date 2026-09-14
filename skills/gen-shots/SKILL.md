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

- 本插件自带 Python 运行时，无需系统安装 Python
- `vcshort` CLI 位于插件根目录 `bin/` 下（插件根目录 = 本 SKILL.md 上两级目录）：
  - WorkBuddy / CodeBuddy：`${CODEBUDDY_SKILL_DIR}/../../bin/vcshort`
  - Claude Code：`${CLAUDE_PLUGIN_ROOT}/bin/vcshort`
  - Devin / Cursor：从技能源路径取上两级目录，拼接 `bin/vcshort`
- 下文 `vcshort <command>` 均指展开后的完整路径；Windows 也可用 `bincshort.bat`
- 项目已初始化，且该章节已执行过 `/vc-short:extract` 和 `/vc-short:gen-script`（即 `character_map.yaml`、`scene_map.yaml`、`script.md` 已存在）

## 输入参数

| 参数 | 说明 | 示例 |
|------|------|------|
| **项目路径** | 项目根目录的绝对路径 | `/Users/.../末日求生` |
| **章节号** | 章节编号 | `ch01` |

## 分镜编号规则

存放在 `chapters/<章节号>/shots/shot_XXX_YY/shot.yaml`：
- `shot_001_01`、`shot_001_02` — **同一地点且角色，角色位置一致**的连续分镜（主号 001 相同，子号递增）
- `shot_002_01` — 地点或角色组发生变化后的第一个分镜
- **同主号必须顺序生成**（后一镜需要前一镜的 last_frame 保持连贯），**不同主号可并行**

## 分镜 YAML 格式

```yaml
shot_id: "001_01"
chapter: "ch01"
script_segment: |
  对应的剧本原文
characters:
  - name: 小帅
    position: 站在教室中央
  - name: 小美
    position: 坐在窗边
scene: 废弃学校操场
camera:
  shot_type: "中景"
  angle: "平视"
  movement: "固定"
  duration: 15
status: "pending"
keyframe: null
video: null
```

- `characters`：有动作或台词的角色都必须列入（含 `name` 和 `position`），不能省略
- `position`：从剧本动作描写和场景描述推断，同主号连续分镜的 position 应连贯

## 执行步骤

### 1. 读取文件

读取 `script.md`、`character_map.yaml`、`scene_map.yaml`、`config.yaml`。映射文件不存在则提示用户先执行 `/vc-short:extract`。

### 2. 分析剧本，拆分分镜

先读取本 skill 目录下的 `constraints.md`，**严格遵守其中的约束规则**生成分镜。

**默认一个场景对应一个分镜**。剧本已在 gen-script 阶段按 15 秒时长拆好，一般不需要再拆。

**连续分镜识别**：同时看 script.md 中 `【场景X：描述】` 的地点，以及该分镜的角色组。
- 地点相同 **且** 角色组一致 = 同主号子号递增
- 地点不同 **或** 角色组有增减（有人离开/加入）= 新主号

**角色一致性**：同主号的连续分镜必须保持同一批角色，角色增减（离开/加入）必须在 script_segment 中明确交代，不能凭空出现。若角色组发生变化，应开新主号，而不是沿用子号。

### 3. 启动 shot-reviewer subagent 全面审查

主 agent 不自行检查，将分镜方案交给 `shot-reviewer` subagent 独立审查。subagent 有独立 context，不知道拆分过程，从纯第三方视角逐项检查。

调用方式：

```
run_subagent(
  profile="shot-reviewer",
  task="审查以下分镜拆分方案。\n\n约束规则：\n<粘贴 constraints.md 全文>\n\n分镜方案（JSON）：\n<粘贴分镜 JSON 数组>\n\n剧本原文：<项目路径>/chapters/<章节号>/script.md\n小说原文：<项目路径>/chapters/<章节号>/novel.md"
)
```

将 `constraints.md` 全文、分镜方案（JSON 数组）、文件路径传给 subagent。subagent 会逐项检查时长、动作对白、角色对应、衔接流畅性，输出结构化审查结果。

**处理审查结果**：
- subagent 返回"全部通过" → 进入第 4 步
- subagent 返回问题清单 → 根据建议修改拆分方案，重新启动 subagent 审查，直至通过
- 修改涉及剧本本身的问题（如缺过渡台词）→ 提示用户重新 gen-script

### 4. 调用脚本写入分镜文件

将分析结果转为 JSON 数组，写入 `chapters/<章节号>/shots.json`，然后调用：

```bash
vcshort gen-shots <项目路径> --chapter <章节号> [--force]
```

脚本读取 JSON 生成 YAML 后删除该 JSON。`characters` 用剧本角色名，`scene` 用剧本场景描述，脚本自动通过映射文件转为 assets 目录名。

```json
[
  {
    "shot_id": "001_01",
    "script_segment": "角色名（动作）：台词...",
    "characters": [
      {"name": "角色名A", "position": "站在大殿中央"},
      {"name": "角色名B", "position": "坐在左侧首位"}
    ],
    "scene": "场景名",
    "camera": {"shot_type": "中景", "angle": "平视", "movement": "固定", "duration": 15}
  }
]
```

已有分镜文件时追加 `--force` 覆盖。映射不到时脚本保留原名称，可后续修改映射文件重新生成。

### 5. 确认结果

列出所有分镜（序号、角色、场景、时长），询问用户是否满意。

## 注意事项

- 分镜拆分要自然，不要把一个完整动作或对白拆到两个分镜
- 角色多形态：`character_map.yaml` 值支持 `角色名:形态名`（如 `小美: 小帅:女装`），映射到 `assets/characters/小帅/小帅-女装.png`
- 所有 YAML 由脚本用 ruamel.yaml 生成，不要手动编辑 shot YAML
