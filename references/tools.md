# 创作工具索引

统一入口为 `<Skill绝对路径>/scripts/tools.py`；工具执行目录来自 `target-root.json`，不根据当前目录猜测。工具发现与帮助无需配置目标。

## 发现与调用

```powershell
python <Skill>/scripts/tools.py list
python <Skill>/scripts/tools.py describe capture.slides
python <Skill>/scripts/tools.py capture.slides --help
```

只需用途、参数或依赖时用 `describe` / `--help`，不读取脚本或整份细节文档。参数以脚本帮助为准，清单由 `scripts/catalog.json` 维护。默认 stdout 为一份 JSON，进度写 stderr；退出码 `0` 为工具覆盖内通过，`1` 为检查不通过，`2` 为参数、依赖或执行错误。读取结果的覆盖范围，不把静态检查通过当作播放或发布成功。

## 按任务选择

| 任务 | 工具与必要资料 |
|---|---|
| 初始化大纲、补齐/检查身份 | `module.init --title "标题"`、`module.identity --check`；[身份](engineering/module-assets.md) |
| 页 UUID、元数据与字面量资源预检 | `check.outlines`、`check.module`；[基础检查](eval/checks.md) |
| 真实截图、缩略图、边界与字数、运行时页序 | 见下方截图流程 |
| 原稿 PPTX 提取 | `extract.pptx --help`；Windows 桌面 PowerPoint；提取产物保存在模块 `_scratchpad/`，不替代原稿视觉核对 |
| 资源分析、压缩、OSS | `assets.inspect`、`assets.compress`、`assets.upload`；[资源规则](engineering/module-assets.md) |
| 本地媒体导入或样式检查 | `check.asset-imports`、`check.styles` |
| 课程源码 ZIP 交付 | `course.pack --help`；[构建与交付](engineering/delivery.md) |
| 可选源码/缩略图统计报告 | `analyze.pages --help`；静态近似统计不能证明实时状态 |
| 环境、工具与 Skill 维护 | `environment.doctor --tool <ID>`、`check.skill`；修改脚本前读[脚本规范](engineering/scripts.md) |

运行具体工具前确认作用范围：素材上传、绿幕转换、训练与专用导出可能写入或覆盖文件，帮助会列出。真实 OSS 上传需要已有任务授权并显式传 `--config <Shuku配置JSON>`；不复制凭据到 Skill。可选 `export.gradcam.*`、`model.emnist.train` 依赖已安装的 Shuku `backend[authoring-compute]`，先用 `--plan`，以 `--asset-root` 指定目标内输出。服务接入见[计算](computing/gpu.md)。

## 截图和缩略图

仅更新缩略图时直接执行 `capture.thumbnails --module <UUID或alias>`，不重走创作设计或评分。已有当前构建可复用，工程外的输出传 `--build-output <目录>`；不启动源码 Vite。

仅在执行截图或一致性检查时读[截图细节](tool-capture.md)，包括单页、操作状态、就绪、返回值与失败处理。常用命令：

```powershell
python <Skill>/scripts/tools.py capture.slides --module <UUID> --slide <页UUID> --page-directory <语义页目录> --build-output <构建输出目录>
python <Skill>/scripts/tools.py capture.thumbnails --module <UUID>
```

## 工具回归

在 Skill 根目录执行 `python -m pytest scripts/tests -q` 与 `node --test scripts/tests/*.test.mjs`。需要平台对照和真实构建的测试以 `CREATOR_SKILL_TEST_SHUKU_ROOT` 显式指定 Shuku。测试不替代课程验收；只改文档时执行 `check.skill` 与引用检查即可。
