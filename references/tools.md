# 创作工具索引

先用 `python <Skill>/scripts/tools.py list`、`describe <ID>` 或 `<ID> --help` 查用途和参数，不预读所有源码。原有工具全部保留；默认由course.pack按环境调度，详见[本地环境与窗口](engineering/local-environment.md)。

## 工程、依赖与调用

- 新窗口用 `context.create --target-root <工程绝对路径> --context-directory <当前窗口工作目录> [--module <课程>]` 创建独立绑定，之后每次调用 `tools.py --context <返回的绝对配置路径> <工具>`。
- 原 `target-root.json`兼容单窗口默认，不由多窗口轮流覆盖；无上下文的显式路径course工具仍独立可用。
- `dependencies.policy`读取/保存本机安装意愿；unknown只问一次，pending不重复问，allowed补依赖，declined继续已有能力。安装器 `dependencies.install`默认列计划，`--apply`只有保存同意后才能执行。

## 按任务选择

| 任务 | 工具与条件 |
|---|---|
| 创建大纲、身份 | `module.init`、`module.identity --check`，Python；[身份与资源](engineering/module-assets.md) |
| 元数据、页UUID与文件 | `check.outlines`、`check.module`、`course.inspect`，Python |
| 检查并交付 | `course.pack <目录>`，自动调度媒体、引用、可用本地检查与归档；[交付](engineering/delivery.md) |
| 完整引用迁移 | `assets.rewrite`，Node+TypeScript；自动打包优先复用其规划器，直接调用默认预览、--apply改原源码 |
| 编辑ID | `module.edit-ids`，Node+Babel；打包时在副本补齐并检查，保留已有ID，原Shared只读 |
| 资源导入、样式 | `check.asset-imports`、`check.styles`，Node |
| 页面统计 | `analyze.pages`，Node+numpy+Pillow；源码近似统计，不证明当前渲染 |
| 图片、资源清单 | `assets.compress`、`assets.inspect`；图片用Pillow；原地压缩按[迁移说明](engineering/asset-paths.md)收尾 |
| 音视频 | `course.videos`、`course.audio`，Python+FFmpeg/ffprobe；独立工具保留，打包时有媒体就处理、没有就跳过 |
| 真实截图、边界、字数 | `capture.slides`、`capture.inspect`，Python Playwright+浏览器；自动流程检查本次构建 |
| 正式缩略图维护 | `capture.thumbnails`保留；最终正式缩略图由服务器发布版本生成 |
| 浏览器调试与页序 | `check.bounds`（Node，已有调试浏览器）、`check.course`（Python浏览器）；capture.slides已覆盖相同边界逻辑，不重复开启调试会话 |
| 原稿提取 | `extract.pptx`，Windows桌面PowerPoint；[参考改编](workflow/reference-adaptation.md) |
| 清理与环境 | `scratchpad.clean`、`environment.doctor`、`check.skill`；检查不替代实际清理 |

GPU导出、训练、绿幕和素材上传保留独立入口，按任务授权执行，不因打包而自动训练、上传或启动远端服务。真实OSS上传需明确配置，不把凭据写入Skill。

## 检查结果

stdout为JSON、进度写stderr；course.pack输出精简报告与完整报告路径。结果区分passed、failed、unverified、not-applicable。普通工具退出0为覆盖范围内成功、1为检查失败、2为执行错误；course.pack另用3表示等待首次回答或补齐已授权依赖。严重错误阻止出包；已保存的安装意愿不因失败、重试、新窗口或新增依赖再次询问。

截图细节见[截图工具](tool-capture.md)。指定--actions只执行已授权操作；无操作清单不把默认截图标作交互已验证。检查截图放所属页/模块_scratchpad；自动打包将证据保存在同级.checks/。正式缩略图位于课程自己的assets/shuku-thumbnails/<页面UUID>.webp，1600×900、q20。

## 工具回归

维护者按改动运行Python与Node行为测试；课程真实构建测试需明确本地Shuku运行时。测试环境使用独立CREATOR_SKILL_LOCAL_STATE，不修改用户的安装意愿或全局目标。

## 临时目录清理

仅打包任务自动排除 `_scratchpad`，不执行清理，不修改原工程。以下清理命令用于创作收尾或用户另行要求的清理。

每完成一页并完成必要核对，清理该页；课件接近完成时，以及 Git 提交前，清理整门课。已有 `.gitignore` 或打包排除规则不能替代实际清理。需长期保留的已确认设计图、正式资源和记录先保存到工程约定的正式位置或用户交付目录；不要把整个 `_scratchpad` 换名当作清理，也不要让正式代码引用临时目录。

支持直接指定任意绝对路径（无需配置 `targetRoot`）；相对路径仍以配置的 `targetRoot` 为基准，与当前终端目录无关。指定路径下无嵌套深度限制，也不排除 Shared、`.git`、`node_modules` 等普通目录；只删除其中的 `_scratchpad`，不改动其他内容：

```powershell
# 任意指定路径，递归清理所有层级
python <Skill绝对路径>/scripts/tools.py scratchpad.clean "F:\course" --apply
# 默认仅预览；--dry-run 可显式指定
python <Skill绝对路径>/scripts/tools.py scratchpad.clean modules/<课程UUID>/pages/<语义页目录>
# 每页完成后，实际清理该页
python <Skill绝对路径>/scripts/tools.py scratchpad.clean modules/<课程UUID>/pages/<语义页目录> --apply
# 创作收尾或提交前，清理该课件所有层级的临时目录
python <Skill绝对路径>/scripts/tools.py scratchpad.clean modules/<课程UUID> --apply
# 明确需要清理整个已配置工程时
python <Skill绝对路径>/scripts/tools.py scratchpad.clean . --apply
```

仅删除目录名为 `_scratchpad` 的目录及其全部内容，不自动备份；正式文件和 `_scratchpad-backup` 等不同名称不会匹配。必须显式指定扫描路径，路径本身就是 `_scratchpad` 时也支持删除。所有层级的普通目录都扫描，删除外层 `_scratchpad` 时其内部嵌套的同名目录一并删除。递归删除前校验绝对路径，符号链接和 Windows junction/reparse point 不跟随，避免跨出指定范围，结果 `skipped` 中报告被跳过的链接。Shared 只读约束对本清理工具的例外仅限用户要求的 `_scratchpad` 临时目录清理，不得借此修改 Shared 正式文件。
