---
name: gen-voice
description: 为角色生成音色参考音频，调用火山引擎豆包 TTS API
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

# 生成角色音色

## 前置条件

运行 `install.sh`（macOS/Linux）或 `install.ps1`（Windows）安装后，`vcshort` 已在 PATH 中，直接调用 `vcshort <command> ...`。

- 项目已初始化（有 `config.yaml` 和 `assets/` 结构）
- `config.yaml` 中已配置 `tts.api_key`（火山引擎语音合成 API Key）
- 角色图片已生成（`assets/characters/<角色名>/` 目录存在）

## 输入参数

| 参数 | 说明 | 示例 |
|------|------|------|
| **项目路径** | 项目根目录的绝对路径 | `/Users/.../末日求生` |
| **角色名** | 角色名（对应 assets/characters/<角色名>/） | `小帅` |
| **性别** | `male` 或 `female` | `male` |

## 执行步骤

### 1. 收集参数

- 确认项目路径、角色名、性别
- 性别决定从哪个音色池随机选择

### 2. 调用脚本

```bash
vcshort gen-voice <项目路径> \
  --name <角色名> \
  --gender <male|female>
```

脚本会自动完成以下操作：
1. 根据性别从豆包 2.0 音色池随机选一个未用过的音色
2. 生成一句包含角色名的台词
3. 调用火山引擎豆包语音合成 API 生成音频
4. 保存到 `assets/characters/<角色名>/<角色名>.mp3`
5. 记录使用的音色到 `assets/characters/<角色名>/voice.json`

### 3. 确认结果

- 向用户展示音频路径和使用的音色名
- 询问用户是否满意
- 不满意 → 加 `--force` 重新生成（会换一个新音色）

```bash
vcshort gen-voice <项目路径> \
  --name <角色名> \
  --gender <male|female> \
  --force
```

## 与 gen-image 的关系

`gen-image --type character` 时可传 `--gender` 参数，生成图片后自动调用 `gen-voice`：

```bash
vcshort gen-image <项目路径> \
  --type character \
  --name <角色名> \
  --gender male \
  --prompt "<描述>"
```

如果不需要自动生成音色，加 `--no-voice`：
```bash
vcshort gen-image <项目路径> \
  --type character \
  --name <角色名> \
  --prompt "<描述>" \
  --no-voice
```

## 文件结构

```
assets/characters/<角色名>/
  <角色名>.png          # 角色图片
  <角色名>.mp3          # 音色参考音频
  voice.json            # 音色元数据（记录使用的音色和已用列表）
```

## 音色池

### 男声（11 个）
云舟、小天、儒雅逸辰、大壹、解说小明、译制片男、邻家男孩、四郎、儒雅青年、擎苍、少年自信

### 女声（11 个）
小何、Vivi、清新女声、知性灿灿、撒娇学妹、甜美小源、甜美桃子、爽快思思、邻家女孩、魅力女友、流畅女声

## 错误处理

- **TTS API Key 未配置** → 提示在 `config.yaml` 的 `tts.api_key` 中填入火山引擎语音合成 API Key
- **角色目录不存在** → 提示先用 gen-image 生成角色图片
- **音色已存在** → 提示加 `--force` 重新生成
- **TTS API 错误** → 展示错误信息
