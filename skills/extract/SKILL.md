---
name: extract
description: 从剧本提取角色/场景/道具，与已有 assets 目录匹配，确认后生成 map 文件和 asset yaml
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

# 提取资产

## 前置条件

- `vcshort` CLI 固定安装在 `~/.vc-short/`（Windows 为 `%USERPROFILE%\.vc-short`），自带 Python 运行时，无需系统安装 Python：
  - bash / Git Bash / macOS / Linux：`~/.vc-short/bin/vcshort <command> ...`
  - Windows cmd / PowerShell：`%USERPROFILE%\.vc-short\bin\vcshort.bat <command> ...`
- 下文 `vcshort <command>` 均指上述完整路径
- 若该路径不存在：代用户安装运行时——下载 `https://github.com/itrxiAi/vc-short-plugin/releases/latest/download/vcshort-macos.zip`（Windows 用 `vcshort-windows.zip`），解压并把其中的 `vc-short-plugin` 文件夹移动为 `~/.vc-short`，装好后重试

## 前置条件

- 项目已初始化（有 `config.yaml` 和 `chapters/` 目录）
- `chapters/<章节号>/script.md` 已存在（已执行 gen-script）
- `chapters/<章节号>/novel.md` 已存在（小说原文，用于按需补描述）

## 输入参数

| 参数 | 说明 | 示例 |
|------|------|------|
| **项目路径** | 项目根目录的绝对路径 | `/Users/.../末日求生` |
| **章节号** | 章节编号 | `ch01` |

## 执行步骤

### 1. 收集参数

- 确认项目路径、章节号

### 2. 读取剧本，提取资产清单

读取 `chapters/<章节号>/script.md`，提取三类资产：

- **角色**：所有有名字或有明确出场的角色。多形态（换装、变身）在 `forms` 中列出
- **场景**：所有出现的地点/环境
- **道具**：所有出现的物件——玉镯、信件、令牌、兵器、包袱等。跨镜出现的物件尤其重要

名字用中文，与剧本中的称呼一致——这样 gen-shots 的 map 才能对得上。

### 3. 按需从 novel 补描述

对每个资产，判断是否缺描述（外貌/环境/物件外观）：

- **角色**：script 主要是对白和动作，外貌描写通常不足。缺 description 或 instruction 时，grep `novel.md` 搜角色名，取命中行前后各 5 行，从这些段落提取外貌、年龄、性格、语气。**personality 独立提取**：从角色的言行、决策、他人评价中提炼性格特征（如"洒脱从容、重情义"、"阴险狡诈、唯利是图"），不要混进 description（description 只写外貌、年龄等可见特征）
- **场景**：缺 description 时，grep `novel.md` 搜场景名或场景关键词，从命中段落提取环境描写
- **道具**：缺 description 时，grep `novel.md` 搜道具名，从命中段落提取外观描写；同时推断 owner（持有者角色名，可为空）

grep 命令示例：
```bash
# 搜角色"陈青源"在 novel.md 中的段落，命中行前后各 5 行
grep -n -C 5 "陈青源" chapters/<章节号>/novel.md
```

script 里已经有足够信息的（如对白能推断语气），不查 novel。查不到的明确标记"未在 novel 中找到"，留给用户补，不瞎编。

### 4. 生成 extract.tmp.json

把提取结果写入 `chapters/<章节号>/extract.tmp.json`：

```json
{
  "characters": [
    {
      "name": "角色名",
      "gender": "male",
      "description": "外貌、年龄等描述（script 不足时从 novel 补）",
      "personality": "性格描述（如：洒脱从容、重情义；或从言行推断的脾气特征）",
      "instruction": "用XX的语气说",
      "forms": [
        {"name": "默认", "description": "主要形态描述"},
        {"name": "女装", "description": "女装形态描述"}
      ]
    }
  ],
  "scenes": [
    {"name": "场景名", "description": "场景描述"}
  ],
  "props": [
    {"name": "道具名", "description": "道具外观描述", "owner": "持有者角色名"}
  ]
}
```

**提取原则：**
- **角色 gender**：根据小说原文描写和称呼推断（如"女孩"→female、"壮汉"→male）。无法确定时留空 `""`
- **角色 instruction**：角色的语音情感指令，根据言行描写推断。参考：
  - 凶狠霸道型：`用凶狠霸道、盛气凌人的语气说`
  - 冷静沉稳型：`用冷静沉稳、低沉平淡的语气说`
  - 倔强隐忍型：`用倔强带泪光、隐忍但坚韧的语气说`
  - 活泼开朗型：`用活泼轻快、充满活力的语气说`
  - 虚弱疲惫型：`用虚弱疲惫、有气无力的语气说`
  - 阴险狡诈型：`用阴险狡诈、阴阳怪气的语气说`
  - 温柔体贴型：`用温柔体贴、轻声细语的语气说`
  - 惊恐害怕型：`用惊恐颤抖、害怕的语气说`
- **道具 owner**：持有者角色名，可为空（公共道具如大殿里的香炉）。跨镜转移的道具（如玉镯从红裙姑娘到陈青源）填当前持有者

### 5. 调用脚本匹配

```bash
vcshort extract <项目路径> --chapter <章节号>
```

脚本会：
1. 读取 `extract.tmp.json`
2. 扫描 `assets/characters/`、`assets/scenes/`、`assets/props/` 目录，与已有资产匹配（精确 + 模糊匹配）
3. **写回 `extract.tmp.json`，每条记录加上 `matched` 字段**（不生成 map 文件）
4. 打印匹配摘要

### 6. 用户确认

LLM 读取 `extract.tmp.json`，在对话中展示匹配结果：

```
角色:
  小帅（形态: 默认） → 小帅 ✅
  林霸 → 林霸 ✅
  新角色A ❌ 未匹配

场景:
  废弃学校操场 → 废弃学校操场 ✅
  新场景B ❌ 未匹配

道具:
  玉镯 → 玉镯 ✅
  饼干袋 ❌ 未匹配
```

对于未匹配的资产，让用户逐个选择：
1. **手动指定** — 填入已有的 assets 目录名（如发现是同一角色的不同称呼）
2. **注册为新资产** — 保持 `matched: ""`，--confirm 时映射到自身名称，后续用 `/vc-short:gen-character`（角色）或 `/vc-short:gen-image`（场景/道具）生成图片
3. **跳过** — 从 extract.tmp.json 中删除该条目

用户确认后，LLM 更新 `extract.tmp.json` 中的 `matched` 字段。

### 7. 确认生成

```bash
vcshort extract <项目路径> --chapter <章节号> --confirm
```

脚本读取确认后的 `extract.tmp.json`，一次性完成：
1. **生成 `character_map.yaml`** — 剧本角色名 → assets 目录名
2. **生成 `scene_map.yaml`** — 剧本场景名 → assets 目录名
3. **生成 `prop_map.yaml`** — 剧本道具名 → assets 目录名
4. **生成 asset yaml**（不覆盖已有）：
   - `assets/characters/<名称>/character.yaml` — 角色档案（name/gender/appearance/voice）
   - `assets/scenes/<名称>/scene.yaml` — 场景档案（name/description）
   - `assets/props/<名称>/prop.yaml` — 道具档案（name/description/owner）
5. **删除 `extract.tmp.json`** — 临时文件清理

注意：脚本不再往 config.yaml 注册资产。新资产的"注册"就是用 `/vc-short:gen-character`（角色）或 `/vc-short:gen-image`（场景/道具）生成图片到对应目录。

### 8. 后续生成

未匹配的新资产需要生成图片：
- 角色：`/vc-short:gen-character`（自动生成图片+音色）
- 场景：`/vc-short:gen-image --type scene --name <场景名> --prompt "<描述>"`
- 道具：`/vc-short:gen-image --type prop --name <道具名> --prompt "<描述>"`

## extract.tmp.json 格式

匹配前（LLM 生成）：
```json
{
  "characters": [{"name": "角色名", "gender": "male", "description": "...", "personality": "...", "instruction": "用XX的语气说", "forms": [...]}],
  "scenes": [{"name": "场景名", "description": "..."}],
  "props": [{"name": "道具名", "description": "...", "owner": "持有者"}]
}
```

匹配后（脚本写回 matched）：
```json
{
  "characters": [{"name": "角色名", "gender": "male", "description": "...", "personality": "...", "instruction": "...", "forms": [...], "matched": "角色名"}],
  "scenes": [{"name": "场景名", "description": "...", "matched": "场景名"}],
  "props": [{"name": "道具名", "description": "...", "owner": "...", "matched": "道具名"}]
}
```

用户确认后（LLM 更新 matched）：
```json
{
  "characters": [
    {"name": "角色名", "gender": "male", "instruction": "...", "matched": "角色名"},
    {"name": "新角色A", "gender": "", "instruction": "", "matched": ""}
  ],
  "scenes": [
    {"name": "场景名", "matched": "场景名"},
    {"name": "新场景B", "matched": ""}
  ],
  "props": [
    {"name": "道具名", "matched": "道具名"},
    {"name": "新道具C", "matched": ""}
  ]
}
```

--confirm 后该文件自动删除。

## 与 gen-shots 的关系

--confirm 生成的 `character_map.yaml`、`scene_map.yaml`、`prop_map.yaml` 直接被 `vcshort gen-shots` 使用。
gen-shots 读取 map 文件，将剧本角色名/场景名/道具名映射为 assets 目录名写入 shot YAML。

## 注意事项

- extract.tmp.json 是临时文件：LLM 生成 → 脚本写回 matched → LLM 更新 matched → 脚本消费后删除
- map 文件只在 --confirm 时生成一次，生成即最终版
- 资产信息由 assets 目录结构决定，不再写入 config.yaml
- 新资产只需用 `/vc-short:gen-character`（角色）或 `/vc-short:gen-image`（场景/道具）生成到 `assets/characters/<名称>/`、`assets/scenes/<名称>/`、`assets/props/<名称>/` 即可
- asset yaml（character.yaml/scene.yaml/prop.yaml）已存在则不覆盖，保护手动修改
