---
name: fix-image
description: 修改已有图片资产，基于原图 + 提示词调用 doubao-seededit API 进行编辑
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

# 修改图片资产

## 前置条件

运行 `install.sh`（macOS/Linux）或 `install.ps1`（Windows）安装后，`vcshort` 已在 PATH 中，直接调用 `vcshort <command> ...`。

## 前置条件

- 项目的 `config.yaml` 中已填写 `api.api_key`
- 待修改的资产图片已存在于 `assets/` 目录中

## 输入参数

| 参数 | 说明 | 示例 |
|------|------|------|
| **项目路径** | 项目根目录的绝对路径 | `/Users/.../末日求生` |
| **资产名称** | assets 目录中的资产名，角色多形态用 `角色名:形态名` | `小帅` 或 `小帅:女装` |
| **修改提示词** | 描述要修改的内容 | `把衣服改成黑色，加一条围巾` |

## 执行步骤

### 1. 收集参数

逐个检查参数是否已提供。缺失的必须向用户确认。

### 2. 查找资产图片

从 `assets/` 目录按约定查找图片：
- 角色多形态：`assets/characters/<角色名>/<角色名>-<形态名>.png`
- 角色默认形态：`assets/characters/<角色名>/<角色名>.png`
- 场景：`assets/scenes/<场景名>/` 下数字最大的图片
- 服装：`assets/costumes/<服装名>.png`
- 道具：`assets/props/<道具名>.png`
- 找到 → 获取原图路径
- 未找到 → 提示用户检查名称，或用 `/vc-short:gen-image` 生成新资产

### 3. 拼接提示词

自动将以下内容拼接为最终提示词：
1. **项目风格**（config.yaml 中的 style，如"动漫3D风格"）
2. **画面比例**（config.yaml 中的 aspect_ratio，如"9:16构图"）
3. **用户修改提示词**

### 4. 调用编辑脚本

```bash
vcshort fix-image <项目路径> \
  --name <资产名> \
  --prompt "<修改提示词>"
```

- 原图转 base64 作为输入
- 原图自动备份为 `.bak` 文件

### 5. 确认结果

- 向用户展示修改后的图片
- 询问是否满意，不满意可从 `.bak` 恢复

## 注意事项

- 原图会自动备份为 `<name>.png.bak`
- 资产信息由 assets 目录结构决定，不再写入 config.yaml
- 编辑模型从 config.yaml 的 `api.image_model` 读取
