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

- `vcshort` 已安装（运行 `install.sh`/`install.ps1`），直接调用 `vcshort <command>`
- 项目已初始化，且该章节已执行过 `/vc-short:extract` 和 `/vc-short:gen-script`（即 `character_map.yaml`、`scene_map.yaml`、`script.md` 已存在）

## 输入参数

| 参数 | 说明 | 示例 |
|------|------|------|
| **项目路径** | 项目根目录的绝对路径 | `/Users/.../末日求生` |
| **章节号** | 章节编号 | `ch01` |

## 分镜编号规则

存放在 `chapters/<章节号>/shots/shot_XXX_YY/shot.yaml`：
- `shot_001_01`、`shot_001_02` — 同一地点的连续分镜（主号 001 相同，子号递增）
- `shot_002_01` — 下一个地点的第一个分镜
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

**默认一个场景对应一个分镜**。剧本已在 gen-script 阶段按 15 秒时长拆好，一般不需要再拆。

**连续分镜识别**：看 script.md 中 `【场景X：描述】` 的地点是否相同。地点相同 = 同主号子号递增；地点不同 = 新主号。

**角色一致性**：同主号分镜的核心角色应保持一致，角色增减（离开/加入）必须在 script_segment 中明确交代，不能凭空出现。

### 3. 循环迭代检查（写 YAML 前必须完成）

发现问题则回到第 2 步调整拆分，直至全部通过：

**检查 1 — 时长匹配**：15 秒约需 40-60 字对白（只计台词，动作描写不计字数）。
- < 40 字 → 合并到相邻同主号分镜；无法合并则提示重新 gen-script
- 40-60 字 → 合适
- \> 60 字 → 拆分为同主号子号递增，每个子分镜仍须 ≥ 40 字；无法拆分则提示重新 gen-script

**检查 2 — 动作对白合理性**：动作和对白是否符合逻辑、有无矛盾（如角色已离开却突然说话）。发现矛盾对照 `novel.md` 原文核实，以原文为准。

**检查 3 — 角色对应合理性**：characters 列表与实际出场角色一致，同主号连续分镜角色增减合理，position 与动作描写一致。

**检查 4 — 分镜衔接检查**：代入观众视角，检查分镜衔接是否有难以理解的地方。发现问题从专业编导角度给出解决方案，让用户确认。

**迭代终止**：4 项检查全部通过才进入第 4 步。

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
