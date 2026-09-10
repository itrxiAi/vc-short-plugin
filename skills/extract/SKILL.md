---
name: extract
description: 从章节小说原文提取角色/场景，与已有 assets 目录匹配，确认后生成 map 文件
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

运行 `install.sh`（macOS/Linux）或 `install.ps1`（Windows）安装后，`vcshort` 已在 PATH 中，直接调用 `vcshort <command> ...`。

## 前置条件

- 项目已初始化（有 `config.yaml` 和 `chapters/` 目录）
- `chapters/<章节号>/novel.md` 已存在（有小说原文）

## 输入参数

| 参数 | 说明 | 示例 |
|------|------|------|
| **项目路径** | 项目根目录的绝对路径 | `/Users/.../末日求生` |
| **章节号** | 章节编号 | `ch01` |

## 执行步骤

### 1. 收集参数

- 确认项目路径、章节号

### 2. 读取小说原文

读取 `chapters/<章节号>/novel.md`，理解内容。

### 3. LLM 分析提取

阅读小说原文，提取角色和场景，输出为 JSON 写入 `chapters/<章节号>/extract.tmp.json`：

```json
{
  "characters": [
    {
      "name": "角色名（小说中的称呼）",
      "gender": "male",
      "description": "外貌、年龄、性格等描述",
      "instruction": "用XX的语气说",
      "forms": [
        {"name": "默认", "description": "主要形态描述"},
        {"name": "女装", "description": "女装形态描述"}
      ]
    }
  ],
  "scenes": [
    {"name": "场景名", "description": "场景描述"}
  ]
}
```

**提取原则：**
- **角色**：所有有名字或有明确外貌描写的出场人物。多形态（换装、变身）在 `forms` 中列出
- **gender**：角色性别，`male` 或 `female`。根据小说原文描写和称呼推断（如"女孩"→female、"壮汉"→male、名字含"帅/霸/哥"多为 male、"美/姐/妹"多为 female）。无法确定时留空 `""`，脚本会写入 character.yaml 让用户后续补
- **instruction**：角色的语音情感指令，根据小说中的言行描写推断。写自然语言描述语气的句子，写入 character.yaml 的 voice.instruction，后续 gen-voice 读取。参考：
  - 凶狠霸道型：`用凶狠霸道、盛气凌人的语气说`
  - 冷静沉稳型：`用冷静沉稳、低沉平淡的语气说`
  - 倔强隐忍型：`用倔强带泪光、隐忍但坚韧的语气说`
  - 活泼开朗型：`用活泼轻快、充满活力的语气说`
  - 虚弱疲惫型：`用虚弱疲惫、有气无力的语气说`
  - 阴险狡诈型：`用阴险狡诈、阴阳怪气的语气说`
  - 温柔体贴型：`用温柔体贴、轻声细语的语气说`
  - 惊恐害怕型：`用惊恐颤抖、害怕的语气说`
- **场景**：所有出现的地点/环境
- **名称用中文**，与小说中的称呼一致

### 4. 调用脚本匹配

```bash
vcshort extract <项目路径> --chapter <章节号>
```

脚本会：
1. 读取 `extract.tmp.json`
2. 扫描 `assets/characters/` 和 `assets/scenes/` 目录，与已有资产匹配（精确 + 模糊匹配）
3. **写回 `extract.tmp.json`，每条记录加上 `matched` 字段**（不生成 map 文件）
4. 打印匹配摘要

### 5. 用户确认

LLM 读取 `extract.tmp.json`，在对话中展示匹配结果：

```
角色:
  小帅（形态: 默认） → 小帅 ✅
  林霸 → 林霸 ✅
  新角色A ❌ 未匹配

场景:
  废弃学校操场 → 废弃学校操场 ✅
  新场景B ❌ 未匹配
```

对于未匹配的资产，让用户逐个选择：
1. **手动指定** — 填入已有的 assets 目录名（如发现是同一角色的不同称呼）
2. **注册为新资产** — 保持 `matched: ""`，--confirm 时映射到自身名称，后续用 `/vc-short:gen-character`（角色）或 `/vc-short:gen-image`（场景）生成图片
3. **跳过** — 从 extract.tmp.json 中删除该条目

用户确认后，LLM 更新 `extract.tmp.json` 中的 `matched` 字段。

### 6. 确认生成

```bash
vcshort extract <项目路径> --chapter <章节号> --confirm
```

脚本读取确认后的 `extract.tmp.json`，一次性完成：
1. **生成 `character_map.yaml`** — 小说角色名 → assets 目录名（最终版，无需再改）
2. **生成 `scene_map.yaml`** — 小说场景名 → assets 目录名
3. **删除 `extract.tmp.json`** — 临时文件清理

注意：脚本不再往 config.yaml 注册资产。新资产的"注册"就是用 `/vc-short:gen-character`（角色）或 `/vc-short:gen-image`（场景）生成图片到对应目录。

### 7. 后续生成

未匹配的新资产需要生成图片：
- 角色：`/vc-short:gen-character`（自动生成图片+音色）
- 场景：`/vc-short:gen-image --type scene --name <场景名> --prompt "<描述>"`

## extract.tmp.json 格式

匹配前（LLM 生成）：
```json
{
  "characters": [{"name": "角色名", "gender": "male", "description": "...", "instruction": "用XX的语气说", "forms": [...]}],
  "scenes": [{"name": "场景名", "description": "..."}]
}
```

匹配后（脚本写回 matched）：
```json
{
  "characters": [{"name": "角色名", "gender": "male", "description": "...", "instruction": "用XX的语气说", "forms": [...], "matched": "角色名"}],
  "scenes": [{"name": "场景名", "description": "...", "matched": "场景名"}]
}
```

用户确认后（LLM 更新 matched）：
```json
{
  "characters": [
    {"name": "角色名", "gender": "male", "instruction": "用XX的语气说", "matched": "角色名"},
    {"name": "新角色A", "gender": "", "instruction": "", "matched": ""}
  ],
  "scenes": [
    {"name": "场景名", "matched": "场景名"},
    {"name": "新场景B", "matched": ""}
  ]
}
```

--confirm 后该文件自动删除。

## 与 gen-shots 的关系

--confirm 生成的 `character_map.yaml` 和 `scene_map.yaml` 直接被 `vcshort gen-shots` 使用。
gen-shots 读取 map 文件，将剧本角色名/场景名映射为 assets 目录名写入 shot YAML。

## 注意事项

- extract.tmp.json 是临时文件：LLM 生成 → 脚本写回 matched → LLM 更新 matched → 脚本消费后删除
- map 文件只在 --confirm 时生成一次，生成即最终版
- 资产信息由 assets 目录结构决定，不再写入 config.yaml
- 新资产只需用 `/vc-short:gen-character`（角色）或 `/vc-short:gen-image`（场景）生成到 `assets/characters/<名称>/` 或 `assets/scenes/<名称>/` 即可
