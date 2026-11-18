# 本地环境、一次性安装意愿与多窗口目录

## 每窗口独立绑定

旧的 Skill根目录 `target-root.json` 只含 `targetRoot`，仍支持已有单窗口任务。它不是多窗口共享的“当前工程”；不要由不同窗口轮流覆盖它。新窗口按用户明确指定的绝对路径创建上下文：

```powershell
python <Skill>/scripts/tools.py context.create --target-root <工程绝对路径> --context-directory <当前窗口工作目录> [--module <课程UUID或alias>] [--shuku-root <本地Shuku目录>]
python <Skill>/scripts/tools.py --context <返回的target-root.json绝对路径> check.outlines
python <Skill>/scripts/tools.py --context <同一路径> course.pack <课程目录>
```

context.create在指定工作目录下新建带随机UUID的独立目录，保存兼容的target-root.json和context.json（窗口身份、工程、可选课程及Shuku位置）。不会覆盖全局配置。续作沿用当前窗口的绝对配置路径；用户明确换工程时新建上下文，不改旧上下文。原始targetRoot只作为目录边界，不随每次课件切换改写。

工具只对本次子进程传递 `CREATOR_SKILL_TARGET_CONFIG`，不修改系统环境变量。显式绑定课程后，支持module参数的工具默认选中该课程；冲突参数、越界路径和越界打包拒绝执行。相对工程路径在该窗口targetRoot下解析。仅传绝对路径的直接course工具仍可独立使用。

打包使用独立临时副本、输出占位锁和独立 `.checks/`，预览服务使用系统分配端口，避免覆盖其他窗口的ZIP、报告、构建和截图。上下文解决目录串用，不自动合并两窗口对同一文件的直接编辑；同一课程并行改动应使用不同Git worktree，或明确分配不同页面文件。

## 一次性安装意愿

创作偏好 `references/preferences.md` 不保存安装授权；target-root.json也不增加授权字段。本机当前账号跨窗口、跨Skill检出共用独立JSON：Windows为 `%LOCALAPPDATA%/creator-skill/dependency-preferences.json`；其他系统使用XDG配置目录或`~/.config/creator-skill/`。`CREATOR_SKILL_LOCAL_STATE` 可显式指定隔离状态目录（例如测试）。凭据不写入这些文件。

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

`.report.json`记录每项passed/failed/unverified/not-applicable、实际工具结果和日志；`.checks/`保留本次构建及截图供智能体查看。服务器仍独立检查实际上传内容、权限、安全、正式编译、发布和正式缩略图，不把本地报告当作放行凭证。
