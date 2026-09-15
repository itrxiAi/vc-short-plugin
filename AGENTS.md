# vc-short 插件规则

本插件提供 AI 短视频制作全流程工具。

## 核心约定

- `vcshort` CLI 固定安装在 `~/.vc-short/`（Windows 为 `%USERPROFILE%\.vc-short`），随插件自带便携 Python 运行时（`python/` 目录），无需系统安装 Python
- SKILL.md 里用固定路径调用：bash/Git Bash 下 `~/.vc-short/bin/vcshort <command>`；Windows cmd/PowerShell 用 `%USERPROFILE%\.vc-short\bin\vcshort.bat <command>`，不要直接 `python xxx.py`
- 技能可安装到任意 agent 的技能目录（如 WorkBuddy 的 `~/.workbuddy/skills/`），SKILL.md 一律用上面的固定路径引用 CLI，不依赖技能与 CLI 的相对位置
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
8. `/vc-short:gen-keyframe` 生成分镜首帧图（确认满意后再生成视频，避免一次确认同时产生图片+视频两笔费用）
9. `/vc-short:gen-video` 生成分镜视频（自动使用已确认的首帧图）
10. `/vc-short:compose-chapter` 合成章节视频

每一步完成后都要让用户确认，不要跳步。
