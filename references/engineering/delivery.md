# Shuku 构建与源码 ZIP 交付

仅在构建、打包或发布时读取。课程工程保存源码和风格；Shuku 提供统一依赖、校验、构建与运行时。不要在 IDL 根目录新增 npm/Vite 工程或用历史 node_modules/dist 作为新流程输入。

## 构建与检查

在用户指定的 Shuku 根目录按该工程 README 配置 `course_build.source_root` 和独立的 `output_root`，执行：

```powershell
python run.py courses-check
python run.py courses-build --module <UUID或alias>
```

源码不包含平台 runtime；`@shuku/course-runtime`、`@shuku/course-style` 由构建器解析。Guide TSX 导出与文件名相同的命名组件；PPT 入口导出 `deck`，页面 UUID 与大纲一致。源码类型检查按宿主实际提供的入口执行；Vite 构建不等于完整 TypeScript 类型检查，不能用网站 frontend 的 typecheck 冒充课程检查。

Skill `check.module` 是独立的静态预检；官网验收以当前 Shuku 的 `shuku-course` 校验器与真实构建为准。平台不再从外部 Skill 加载检查器，两者变更需做行为对照。

## 交付和提交前清理

保留正式设计与必要检查结论后，执行 `python <Skill绝对路径>/scripts/tools.py scratchpad.clean modules/<课程UUID> --apply` 清理本次课件中的所有 `_scratchpad`。检查或构建若新生成临时目录，完成核对后再次清理，再交付或 Git 提交；不能仅依赖 ZIP 排除或 `.gitignore`。范围与保护规则见[临时目录清理](../tools.md#临时目录清理)。

## 导出上传包

官网 ZIP 导入接收带 `outlines.json` 的课程源码，不接收只有 dist 的包或普通 npm 项目。推荐调用：

```powershell
python <Skill绝对路径>/scripts/tools.py course.pack --module <UUID或alias> --shuku-root <Shuku绝对路径> --output <新ZIP绝对路径>
```

工具仅本地打包，不上传、不发布：选择课程及其依赖，包含公共代码与完整风格；排除无关草稿、嵌套 ZIP、Skill、缓存和 `_scratchpad`，平台业务源码由导入校验拒绝。动态 import 按平台规则保守保留更多课程；若因此带入纯大纲或仍缺依赖，停止并说明，不能静默漏包。

临时 ZIP 重新解包后运行该 Shuku 的真实导入校验与每门课程构建；全部成功才原子交付，已有输出不覆盖。结果列出课程、依赖、检查覆盖与构建目录。ZIP 最多 1 GiB、展开最多 1 GiB、单文件最多 128 MiB、最多 10000 个文件；上传器限制以当前平台为准。

仅使用平台 alias 的默认风格课程可由官网补齐默认包；直接相对引用 `shared` 或自定义风格必须携带对应完整依赖。工具保留实际依赖，不用默认包掩盖缺失的自定义组件。

## 播放与官网验收

打包构建不能证明页面正常。若没有对应当前源码和所选风格的真实检查证据，使用输出的构建目录执行 `capture.slides --build-output <目录>`，检查本次影响的页面与关键状态；页序、入口和依赖变化扩大范围。请求模型/GPU 的互动在术库宿主中验证，独立静态页面不能验证 RPC。

上传新课程后网站自动逐门导入、构建和保存，完成后在“我的课程”打开，默认仅自己可见。纯大纲不能播放；公开上架、受审核或他人所有的课程更新仍遵循平台权限。没有实际上传生产官网时，只说明本地验证通过，不能声称官网部署已验收。
