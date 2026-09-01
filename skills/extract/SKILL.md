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

## 定位 vcshort 可执行文件

本插件自带 CLI 工具 `vcshort`，位于插件根目录的 `bin/vcshort`。首次调用先定位：
```bash
devin skills show vc-short:extract
```
`Base directory` 向上两级即为插件根目录，可执行文件在 `<插件根>/bin/vcshort`。

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
      "description": "外貌、年龄、性格等描述",
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
- **场景**：所有出现的地点/环境
- **名称用中文**，与小说中的称呼一致

### 4. 调用脚本匹配

```bash
<插件根>/bin/vcshort extract <项目路径> --chapter <章节号>
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
2. **注册为新资产** — 保持 `matched: ""`，--confirm 时映射到自身名称，后续用 `/vc-short:gen-image` 生成图片
3. **跳过** — 从 extract.tmp.json 中删除该条目

用户确认后，LLM 更新 `extract.tmp.json` 中的 `matched` 字段。

### 6. 确认生成

```bash
<插件根>/bin/vcshort extract <项目路径> --chapter <章节号> --confirm
```

脚本读取确认后的 `extract.tmp.json`，一次性完成：
1. **生成 `character_map.yaml`** — 小说角色名 → assets 目录名（最终版，无需再改）
2. **生成 `scene_map.yaml`** — 小说场景名 → assets 目录名
3. **删除 `extract.tmp.json`** — 临时文件清理

注意：脚本不再往 config.yaml 注册资产。新资产的"注册"就是用 `/vc-short:gen-image` 生成图片到对应目录。

### 7. 后续生成

未匹配的新资产需要用 `/vc-short:gen-image` 生成图片：
- 角色：`/vc-short:gen-image --type character --name <角色名> --form <形态名> --prompt "<描述>"`
- 场景：`/vc-short:gen-image --type scene --name <场景名> --prompt "<描述>"`

## extract.tmp.json 格式

匹配前（LLM 生成）：
```json
{
  "characters": [{"name": "小帅", "description": "...", "forms": [...]}],
  "scenes": [{"name": "废弃学校操场", "description": "..."}]
}
```

匹配后（脚本写回 matched）：
```json
{
  "characters": [{"name": "小帅", "description": "...", "forms": [...], "matched": "小帅"}],
  "scenes": [{"name": "废弃学校操场", "description": "...", "matched": "废弃学校操场"}]
}
```

用户确认后（LLM 更新 matched）：
```json
{
  "characters": [
    {"name": "小帅", "matched": "小帅"},
    {"name": "新角色A", "matched": ""}
  ],
  "scenes": [
    {"name": "废弃学校操场", "matched": "废弃学校操场"},
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
- 新资产只需用 `/vc-short:gen-image` 生成图片到 `assets/characters/<名称>/` 或 `assets/scenes/<名称>/` 即可
