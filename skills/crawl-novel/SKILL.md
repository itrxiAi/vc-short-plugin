---
name: crawl-novel
description: 爬取小说阅读页正文，写入 chapters/<章节号>/novel.md 并生成该章简述 brief.md
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

# 爬取小说章节

把小说阅读页的正文采集下来，转写进 `chapters/<章节号>/novel.md`，同时产出该章简述 `chapters/<章节号>/brief.md`。

采集分两步：**脚本负责滚动截图**，**Agent 负责逐张读图转写**。

- 阅读页正文用自定义字体做了混淆，DOM 文本是乱码，**必须读截图**，不要读 DOM，也不要调用 OCR
- 不绕过登录、验证码、付费墙或其他访问控制

## 前置条件

- 项目已初始化（有 `chapters/` 目录）
- **系统 `python3` 已装 playwright 与 chromium**。插件的便携 Python 不含 playwright，所以本技能用系统 `python3`：

```bash
python3 -c "import playwright" 2>/dev/null || echo "缺少 playwright"
```

缺则先提示用户安装，不要自行安装：

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
```

## 输入参数

| 参数 | 说明 | 示例 |
|------|------|------|
| **项目路径** | 项目根目录的绝对路径 | `/Users/.../我在精神病院学斩神` |
| **起始章节 URL** | 阅读页地址 | `https://fanqienovel.com/reader/6982758195982926373?enter_from=reader` |
| **起始章节号** | 上面 URL 对应的章号 | `ch11` |
| **采集章数** | 连续采几章 | `5` |
| **跳过章数** | 起始 URL 不是要采的第一章时，先点几次「下一章」 | `1` |

起始 URL 是已采过的上一章时，用「跳过章数」从下一章开始，不要重复采。

## 执行步骤

### 1. 收集参数

确认项目路径、起始章节 URL、起始章节号、采集章数、跳过章数。缺 URL 时向用户索取，不要猜测章号。

### 2. 检查依赖

按前置条件检测 playwright；缺失就提示用户安装并停止。

### 3. 滚动截图

用系统 `python3` 运行本 skill 目录下的脚本（`<本 skill 目录>/scripts/capture_novel.py`，如 `~/.vc-short/skills/crawl-novel/scripts/capture_novel.py`）：

```bash
python3 "<本 skill 目录>/scripts/capture_novel.py" \
  --url "<起始章节 URL>" \
  --project "<项目路径>" \
  --start-chapter 11 \
  --chapters 5 \
  --skip 1
```

产物在 `<项目路径>/.crawl/ch<NN>/`：`chunks/chunk_*.png`、`preview.png`、`crawl.json`。

- **退出码 0**：全部采完
- **退出码 2**：遇到付费墙，该章及之后未采集——**报告用户并停止，不要尝试绕过**
- **退出码 1**：其他错误（滚动异常、找不到「下一章」等），把报错原文告诉用户

### 4. 逐章读图转写

对每一章，按顺序读取 `.crawl/ch<NN>/chunks/chunk_0001.png`、`chunk_0002.png`…，先写正文，再写简述。

#### 4.1 写 `chapters/ch<NN>/novel.md`

**文件格式：**

```md
# 书名

## 第N章 章节名

正文第一段。

正文第二段。
```

**转写规则：**

- 截图之间有 20% 重叠，**用重叠区去重**，相邻两张重复的内容只写一次
- 逐张读取、逐段续写，**不要攒到最后一次性写入**——单次输出过长会中途截断，攒着写中断即全部丢失；中断后先读已有 `novel.md`，从最后一段接着写
- 只转写正文。忽略页面 UI（加书架 / 目录 / 夜间 / 字号 / 下载 / 领红包 / 上一章 / 下一章）、「作者有话说」栏目
- 保留原文的段落划分与对话引号，不要改写、不要润色、不要补写
- 章节标题取页面上的章节名（如 `## 第11章 开门`）

#### 4.2 写 `chapters/ch<NN>/brief.md`

正文写完后，用一段话概括这一章。**格式：**

```md
# 第11章 开门 — 简述

（150–300 字：这一章谁在哪做了什么，局面怎么变，结尾停在什么地方）
```

**规则：**

- 150–300 字，连贯叙述，不复述细节，也不写对后续剧情的猜测
- 每章写完 `novel.md` 就紧接着写它的 `brief.md`，不要全部转写完再回头补

### 5. 清理中间产物

全部转写完成后，删除工作目录。`chapters/<章节号>/` 下保留 `novel.md` 和 `brief.md` 两个文件：

```bash
rm -rf "<项目路径>/.crawl"
```

### 6. 确认结果

- 向用户报告每章的段数、大致字数，以及 `brief.md` 的简述
- 提示可以执行 `/vc-short:extract` 提取角色场景，或继续爬下一批章节

## 注意事项

- 每章两个产物：`novel.md`（原文）和 `brief.md`（简述），清理时只删 `.crawl`，两个都保留
- 付费墙、登录墙、验证码一律不绕过；检测到就停下报告，由用户决定怎么办
- 采集的是**用户有权访问的页面**；不要用于绕过任何访问控制
- 章节号统一用 `ch01`、`ch11` 这种两位格式，与 `chapters/` 下的目录名一致
- 同一批多章采集时，脚本会按顺序点「下一章」，中途某章找不到「下一章」会报错停止，已采的章节仍然可用
