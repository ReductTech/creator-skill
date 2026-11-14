# 构建产物截图、缩略图与一致性

仅执行这些任务时读取；工具发现与返回值规则见[工具索引](tools.md)。

### 截图和缩略图

以下命令的模块参数应替换为目标 UUID、目录名或已登记 alias；`--slide` 使用实际场景 ID，可通过 `capture.inspect` 查询。省略 `--slide` 会捕获整套课件。截图读取已完成的构建产物，不启动源码 Vite、不注入源码页面。默认从 `targetRoot/dist` 启动临时的清单校验服务；Shuku 构建目录在工程外时传 `--build-output <构建输出目录>`，已有构建预览服务可传 `--base-url <服务地址>`。只有清单内且校验通过的构建文件会被交付。

**仅更新缩略图，直接执行一条命令：**

```powershell
python creator-skill/scripts/tools.py capture.thumbnails --module AI-Practice-Education
```

工具只使用已构建的课件，任务结束后自动关闭自己启动的临时服务；显式传入的预览服务保持运行。页 ID 已知时用 `--slide <ID>` 只更新受影响页，不必先扫描全部场景。缺少构建、素材或浏览器依赖时按具体错误处理。

默认复用一次加载的课件，每次切页重新挂载页面以重置状态；等待字体、图片、可见的 `aria-busy` 和 `data-capture-ready` 就绪，不为每页固定停留数秒。**常规生成不要传 `--settle-ms 6500`**；只有明确需要某个等待时刻的截图才指定 `--settle-ms`。异步生成内容或自动播放页面应在实际内容容器暴露 `data-capture-ready={是否完成}`，不要让通用截图脚本识别课程专属选择器。默认加载/就绪超时 15 秒，可用 `--timeout-ms` 调整；渲染异常直接报告原因。

截图只加载固定构建，不做源码依赖优化。原有服务和用户浏览器不被关闭；工具自己的浏览器与临时服务在任务结束时退出。

正式图片写入模块自己的 `assets/scenedeck-thumbnails/`。同时自动保存模块 `_scratchpad/thumbnails/report.json` 和 `contact-sheet.jpg`；单页任务保存 `<页ID>.json`，不重建整套总览。JSON 返回 `generatedCount`、`requestedCount`、`generationStatus`、`checksStatus`、`timing.totalSeconds`、各页 `elapsedMs` 及报告路径，无需另写汇总脚本。

检查 `generationStatus` 和生成数量后打开总览核对。`generationStatus: ok` 表示图片已写入；`checksStatus: failed` / 退出码 `1` 表示另有布局检查发现，不等于没有生成图片，**不要因此反复重跑整套**。保留并按范围核对这些发现；只有执行错误、缺页或图像错误才补采相关页。缩略图维护不默认制作 ZIP、额外逐页截图或执行全仓库测试；修改了工具本身才运行工具回归测试。

```powershell
python creator-skill/scripts/tools.py capture.slides --module <UUID> --slide <页面UUID> --page-directory OpeningPage --build-output D:/Builds/Shuku
python creator-skill/scripts/tools.py capture.thumbnails --module Policy-Gradient --slide play-maze
python creator-skill/scripts/tools.py capture.inspect --module Policy-Gradient
```

逐页使用 `capture.slides --slide <场景ID> --page-directory <语义页目录>`，保存到 `modules/<模块目录名>/pages/<语义页目录>/_scratchpad/screenshots/<场景ID>.png`；操作状态用 `--state` 命名为 `<场景ID>/<状态>.png`。批量捕获旧模块而未指定页目录时仍兼容模块级输出，制作新页时使用逐页目录。`--output` 可指定对应页 `_scratchpad/` 内的图片目录。

`capture.thumbnails` 生成正式播放器缩略图，默认保存到 `modules/<模块目录名>/assets/scenedeck-thumbnails/<页ID>.webp`（1600×900 WebP，q=20），只接受默认状态；其 `--output` 仅可选择正式缩略图目录内的位置。`capture.slides --format both` 从一次采集中同时写入评估目录和正式缩略图目录。评估截图仍为 1600×900 PNG。采集到当前运行时第一页时，自动另外生成 `assets/course-covers/<第一页ID>.webp`（1600×900 WebP，q=20），供首页使用；封面和缩略图都直接使用完整页面截图编码。智能体只需指定模块，可选指定页 ID，无需填写尺寸和质量；已有图片对应当前实现和状态时直接复用。

浏览器使用隔离的无头上下文，不读取用户浏览器配置。显式提供的服务不由工具关闭；仅临时启动的产物服务会在任务结束后停止。

截图入口在隔离浏览器内读取课件构建产物，使用真实运行时暴露的场景元数据，不挂载源码或创建页面副本。工具及浏览器启动辅助文件均位于 `creator-skill/scripts/`，不依赖旧后端兼容命令。整批采集结束、关闭浏览器后才写入图片，避免更新资源打断后续页面。

`--actions` 接收按 slide ID 分组的 JSON 文件路径，支持 `click`、`fill`、`press` 和有上限的 `wait`。例如文件内容为 `{"play-maze":[{"action":"click","selector":"button[data-example]"}]}`。选择器必须来自实际页面；只执行任务已授权的操作，不能随便点击训练或发布按钮。传入 `--actions` 时同时传入非 `default` 的 `--state`，如 `--state answered`，避免覆盖默认状态。复查截图覆盖对应状态文件，检查时必须重新读取。

### 页面基础检查与字数

`capture.slides` 复用同一次加载、动作和截图，在 JSON 的 `checks` 中返回各页当前状态的几何检查和字数：验证页面就绪、实际页 ID、逻辑画布、画布外越界、容器内部溢出。`--surface` 默认 `.ppt-slide-surface`。可追踪的内部视口例外及人工核对范围见[基础检查](eval/checks.md)。

字数口径为 `rendered-dom-codepoints-v1`：中文、英文字母、数字、标点各计一个非空白 Unicode 码点，可见文本节点不重复累加，隐藏文本和画布外播放器、讲稿不计。可见文本输入值和选中项单列并计入；密码及非文本控件不计。图片、Canvas、视频及 CSS 生成文字未覆盖，输入值可能包含裁切字符；不是 OCR 或完整页面精确计数。默认与交互状态分别返回，不相加。

仅有明确上限时传 `--max-chars <上限>`；未传时照常统计，`maximum` 和 `exceeded` 为 `null`。`text.characters: null` 表示未验证，不能记为零。JSON 的错误、警告、例外和覆盖限制分列；退出码 `1` 为发现违规，`2` 为执行错误或未验证，截图仍可用于定位问题。基础检查不生成 Rubric 分数或 HTML 报告。

`check.bounds --url <页面地址> --slides <页ID>` 复用同一浏览器检查表达式，通过已有 Chromium 调试端口（默认 9223，`--port` 可改）新开检查标签页，结束后关闭；不启动浏览器或服务。按就绪条件轮询，`--timeout` 默认 15000 毫秒。术库 URL 自动使用无播放器侧栏的捕获入口；其他页面须暴露真实 `data-scene-id`。支持同样的 `--surface` 和 `--max-chars`。此命令检查新开页面的默认状态；关键操作状态用 `capture.slides --actions ... --state ...`，不另建动作格式。


### 课程一致性

```powershell
python creator-skill/scripts/tools.py check.course --module Policy-Gradient --base-url http://127.0.0.1:5173
```

通过已构建运行时的捕获元数据读取 PPT 场景与讲稿，并在隔离上下文临时展开 Guide，比较页 ID 和顺序。标题、讲稿差异单列为警告，不擅自改写；Guide 未暴露可读页序时返回未完成检查，不假称一致。

`--save-snapshot modules/<模块目录名>/_scratchpad/snapshots/course.json` 可保存本次真实快照，返回实际保存路径；后续用 `--snapshot` 离线比较。离线比较不能证明当前页面未变化。运行检查可能加载页面本身的默认行为，需在适用的本地环境执行。

