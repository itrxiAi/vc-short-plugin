# vc-short 插件规则

本插件提供 AI 短视频制作全流程工具。

## 核心约定

- 所有 Python 脚本已合并为单一 CLI 可执行文件 `bin/vcshort`，用 PyInstaller 编译
- SKILL.md 里用 `vcshort <command>` 调用，不要直接 `python xxx.py`
- 首次调用前用 `devin skills show vc-short:<skill>` 定位插件路径
- 资产信息由 `assets/` 目录结构决定，不写入 `config.yaml`
- `config.yaml` 只保留 `style`、`aspect_ratio`、`api` 全局配置

## 工作流程

1. `/vc-short:init` 初始化项目
2. `/vc-short:extract` 提取角色/场景
3. `/vc-short:gen-character` 生成角色资产（图片+音色）
4. `/vc-short:gen-image` 生成场景/服装/道具图片
5. `/vc-short:gen-voice` 重新生成角色音色（不满意时用）
6. `/vc-short:gen-script` 改编剧本
7. `/vc-short:gen-shots` 拆分分镜
8. `/vc-short:gen-video` 生成分镜视频
9. `/vc-short:compose-chapter` 合成章节视频

每一步完成后都要让用户确认，不要跳步。
