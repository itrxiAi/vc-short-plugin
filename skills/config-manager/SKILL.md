---
name: config-manager
description: 扫描 assets 目录列出已有角色/场景/服装/道具
allowed-tools:
  - read
  - exec
triggers:
  - user
  - model
---

# 查看项目资产

## 定位 vcshort 可执行文件

本插件自带 CLI 工具 `vcshort`，位于插件根目录的 `bin/vcshort`。首次调用先定位：
```bash
devin skills show vc-short:config-manager
```
`Base directory` 向上两级即为插件根目录，可执行文件在 `<插件根>/bin/vcshort`。

## 用途

扫描 `assets/` 目录，列出已有的角色、场景、服装、道具。资产信息由目录结构决定，不再维护 config.yaml。

## 前置条件

- 项目已初始化（有 `assets/` 目录）

## 命令

### 列出所有资产

```bash
<插件根>/bin/vcshort config-list <项目路径> list
```

输出示例：
```
角色:
  小帅（形态: 默认）
  林霸（形态: 默认）

场景:
  废弃学校操场（1 张图片）

服装:
  (无)

道具:
  (无)
```

## 目录约定

| 类型 | 目录 | 文件命名 |
|------|------|---------|
| 角色 | `assets/characters/<角色名>/` | 默认形态 `<角色名>.png`，其他形态 `<角色名>-<形态>.png` |
| 场景 | `assets/scenes/<场景名>/` | `1.png`, `2.png`, ...（数字递增） |
| 服装 | `assets/costumes/` | `<服装名>.png` |
| 道具 | `assets/props/` | `<道具名>.png` |

## 注意事项

- 资产信息由 assets 目录结构决定，不再写入 config.yaml
- 新增资产只需用 `/vc-short:gen-image` 生成图片到对应目录
- `config.yaml` 只保留 `style`、`aspect_ratio`、`api` 等全局配置
