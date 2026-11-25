# 本地环境、一次性安装意愿与多窗口目录

## 每次调用指定工程

```powershell
python <Skill>/scripts/tools.py --project "<工程目录>" check.outlines
python <Skill>/scripts/tools.py --project "<工程目录>" --module <课程UUID或alias> course.pack <课程目录>
```

工程路径按当前终端目录解析，随后以绝对路径传给本次子进程（`CREATOR_SKILL_PROJECT_ROOT`）。工具中的相对工程路径以该工程为基准。要限定课程，在工具名前传 `--module`；支持课程筛选的工具自动选中它，路径清理与打包也会核对范围。直接打包仍可只传课程目录。联调外部 Shuku 时使用 `SHUKU_ROOT`。

打包使用隔离的临时快照和输出占位锁，检查证据保存在目标 `_scratchpad/package-checks/` 下，预览服务使用系统分配端口。同一课程续作复用原目录，并行编辑时分配不同页面文件。

## 一次性安装意愿

创作偏好 `references/preferences.md` 不保存安装授权。本机当前账号跨窗口、跨Skill检出共用独立JSON：Windows为 `%LOCALAPPDATA%/creator-skill/dependency-preferences.json`；其他系统使用XDG配置目录或`~/.config/creator-skill/`。`CREATOR_SKILL_LOCAL_STATE` 可显式指定隔离状态目录（例如测试）。凭据不写入这些文件。

安装状态只有 unknown、pending、allowed、declined：

1. 自动流程发现本任务缺依赖，原子把unknown登记为pending并返回requestId，只有抢到登记的窗口发起一次询问：是否允许为本Skill按任务需要安装本地Node、Python包、浏览器及FFmpeg。
2. 其他窗口看到pending就等待同一份回答，不另问；不因超时、重试、新依赖或窗口切换自动清空记录。
3. 获得回答后执行 `dependencies.policy --decision allowed|declined --request-id <ID>`。尚未回答不能当作同意。后续一直沿用，用户主动改变偏好时才更新；`unknown`重置仅在用户明确要求重新询问时使用。
4. allowed时调用 `dependencies.install --apply`，然后重新探测并重跑；安装失败查看日志、修复条件，不再询问愿不愿安装。declined时不安装，照常使用已经可用的依赖，剩余检查标为未验证。

```powershell
python <Skill>/scripts/tools.py dependencies.policy
python <Skill>/scripts/tools.py dependencies.policy --decision allowed --request-id <本次ID>
python <Skill>/scripts/tools.py dependencies.install [--shuku-root <目录>] [--media]
# 默认只列计划；已有保存的同意后才允许实际安装
python <Skill>/scripts/tools.py dependencies.install --apply [--shuku-root <目录>] [--media]
```

安装器有本机互斥锁，不会让两个窗口同时运行安装。它仅使用已知本机包管理器；缺少包管理器、运行时源码、权限或安装后PATH未更新时给出具体处理方法，不另问安装意愿。Shuku位置属于配置，不会因用户允许安装而自动猜测或下载私有工程。

## 检查调度

course.pack默认 `--checks auto`：Python结构/文件检查始终执行；有媒体才处理；Node及解析依赖可用时运行原有引用迁移、资源导入、样式、编辑ID与适用统计；运行时和构建依赖齐全时做类型检查、本地构建；浏览器就绪后检查本次构建的渲染、边界、字数和页序。Guide首屏有独立浏览器检查，PPT用现有capture.slides；不要求另开调试浏览器来重复相同的边界检查。check.bounds仍可独立调用。

有Node不代表全部依赖齐全，按能力分别判断。只有大纲的模块不构建；缺Shuku路径要求配置，不把它当成pip依赖。浏览器默认检查实际页面状态；课程专属操作通过 `--actions <已授权操作JSON>` 提供，不随意点击、不把默认截图说成交互已验证。

本地无法运行 Shuku 正式构建，且独立播放器和浏览器可用时，自动预览本次打包副本，保存 PPT 各页和 Guide 首屏截图。报告用 `standaloneRendering` 记录这次预览，平台构建、构建产物渲染和课程专属交互按原检查报告。依赖平台服务的课件可能无法在独立预览中渲染，这类独立检查结果作为交付报告中的警告。

用户明确只要基础源码检查时可用 `--checks basic`；不能为了省事自行关闭已可执行的检测。退出码0表示生成包，1表示检查不通过，2表示执行错误，3表示需要保存首次回答或补齐已授权依赖。缺依赖而被用户拒绝时可继续基础交付，但明确未验证；实际发现的严重错误阻止出包。

`.report.json`记录每项passed/failed/unverified/not-applicable、实际工具结果和日志；`_scratchpad/package-checks/` 保留构建及截图供查看。服务器仍独立检查实际上传内容、权限、安全、正式编译、发布和正式缩略图，不把本地报告当作放行凭证。
