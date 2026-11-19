---
name: creator-skill
description: 规划、设计、制作和修改 React 交互课件，用内置术库（Shuku）播放器预览和验收。支持 PPT/PDF 改编、大纲、讲稿、问卷及 Shuku 源码 ZIP 交付。
---

# React 演示创作

先判断当前任务与已有进度。纯讨论不创建工程；局部修改只处理受影响页面及必要依赖，沿用有效确认，不从头重做。

## npm 安装入口

npm 包提供 `creator demo`、`creator init <新目录>` 和 `creator preview <工程目录>`。示例和预览默认打开浏览器，可用 `--no-open` 关闭自动打开。安装包内已有播放器和预览依赖，新建工程后直接用 `creator preview`。Python、浏览器截图和媒体工具按后续操作所需检查。

## 首次上手

用户从官网复制提示词、要求准备 Creator Skill 或表示稍后才提供创作需求时，先完成上手流程：

1. 复用用户已下载的完整 Creator Skill 仓库。没有本地副本时，从 [Creator Skill 的 GitHub 仓库](https://github.com/ReductTech/creator-skill)获取完整目录，放在当前工作区，保留脚本、参考资料、Shared 和播放器。
2. 在 Skill 根目录运行 `python scripts/tools.py environment.doctor --group preview`，检查 Python、Node.js 24+、npm 和播放器依赖。当前版本不支持该检查分组或没有 Python 时，先用 `node --version` 和 `npm --version` 验证能否预览，再报告 Python 检查不可用的原因。优先使用已有依赖，仅补齐本次操作所需的依赖。用户的请求已明确授权安装预览依赖时，直接安装；其他依赖按下文的安装意愿处理。
3. 启动示例预览。仓库根目录提供 `setup` 和 `start` 脚本时，缺预览依赖才运行 `npm run setup`，然后运行 `npm start -- --demo`。保持预览服务运行，打开终端实际显示的地址并播放内置课件。入口与深链接见[术库本地预览](player-preview/README.md)。有浏览器工具时实际打开并确认渲染；否则提供预览地址并说明已验证到哪一步。
4. 简要告诉用户准备结果和预览地址。用户尚未提供主题或材料时，等待下一条需求。收到主题、PPT 或 PDF 后，按对应工作流开始；新建课件时在用户指定的目录或当前工作区的新目录创建可编辑工程，有现成工程时就接续该工程。

## 创作、确认与预览

以下流程适用于新建课件及需要重新设计的页面。局部修改沿用仍然有效的确认，按[共用流程](references/workflow/common.md)接续。只交付大纲、讲稿或源码打包的任务按相应流程处理。

**设计与制作的必经步骤。** 每次课件设计或制作任务开始时，先完成[资料通读](references/design/design.md#2-先通读-creator-guide-并看完全部视觉案例)两项要求。用图像工具逐张打开 [visual_samples](assets/visual_samples/) 中的全部原图并对照每组正反例，并逐页通读 [modules 下的 Creator Guide](modules/444f8951-dd2e-42dc-94e5-c5a878618631/CreatorGuide.tsx) 正文。两项均完成后才能构思页面、编写生图提示词、生成或重做设计示意图，以及开始页面实现。接续制作、批量制作或跳过确认时也须完成。

1. **先确认大纲。** 展示大纲并等用户明确确认，再进入页面设计。用户明确授权跳过某个确认时，只跳过对应环节和页面。「帮我制作」「直接做一个课件」及给出主题、页数或交付目录，只授权开展任务。沉默也不视为确认。
2. **先构思主图，再用讲稿核对。** 根据当页标题 `title` 先确定观众要看懂的核心关系、主图如何表达，以及有交互时操作后会看到什么。形成初案后，浏览当页讲稿，检查讲者能否指着画面自然展开。讲稿只用于核对画面是否切题、哪里需要更清楚，不作为生图输入，也不按讲稿逐点配图。从已完整查看的案例中提炼与当前页面相关的设计判断，把正例可借鉴的表达方法、反例的问题及本页的具体取舍写进新提示词。详见[设计](references/design/design.md#视觉设计图的工具约束)。
3. **设计示意图必须从零生成，再展示。** 用户要求给出、制作或重做设计示意图时，每页都必须在本次请求中重新构思、编写全新文字提示词，并实际调用生图工具从零生成。视觉案例只用于设计分析，生图调用只传本次新写的文字提示词。严禁使用旧设计稿、旧提示词、截图、模板或现成素材重新制作或替代当次新图，包括 `_scratchpad/` 中的旧稿。每次生图调用的实际提示词开头必须写入[设计指南规定的 Pinterest 美观度要求](references/design/design.md#生图提示词)，重试也必须保留。在这条美观底线上，按当页主题写入用户要求、工程标准和案例中提炼的表达方法。出图后核对美观度、核心关系、正反例的取舍和组件要求。任一项未达标时，重写提示词并从零生成。展示通过自检的新图，并说明主图和关键交互。默认等用户确认设计后，才编写页面实现。授权跳过设计确认时，仍先展示示意图。无法生图时按[设计指南的替代流程](references/design/design.md#视觉设计图的工具约束)处理，经用户明确同意省略示意图后才可直接实现。设计稿与正式画布均不添加页码。
4. **必须精准复刻设计示意图，逐页验收。** 以用户确认的本次生成示意图为实现规格。用户授权跳过设计确认时，仍以已展示的示意图为规格。必须按同一画布复刻可见布局、尺寸、位置、间距、文字、配色、图形、素材与控件状态。严禁自由改版。仅将用户明确要求的变更落实到对应元素。交付前必须实际渲染并逐项对照，修正所有可见偏差后复验。对照失败或缺少证据，当前页不得标记完成。详见[工程实现](references/engineering/implementation.md#按设计示意图实现)和[基础检查](references/eval/checks.md#页面渲染与边界)。默认展示实际效果并等待该页验收，再进入下一页。用户明确授权批量验收或跳过逐页验收时，仍逐页自检。
5. **交付时用术库播放器给用户预览。** 从仓库根目录运行 `npm start` 并指定本次工程，在内置的 Shuku 播放器里打开目标课件并核对渲染。有浏览器工具时实际打开课件。保持预览服务运行，把可访问的目标课件链接作为验收入口交给用户。截图、离线 HTML 和源码包可作补充。资源或环境受限时说明具体原因，以及用户当前可访问的预览和已验证范围。

## 核心约束

- **直接在用户指定的目录内作业。** 直接修改指定目标中的文件。临时脚本、预览配置、截图和检查记录放在目标目录内对应模块或页面的 `_scratchpad/`，有现成目录就复用。仅当用户未指定目录时才使用智能体默认工作目录。
- **设计示意图与正式页面都必须达到可在 Pinterest 公开分享的美观水准。** 这是构思页面和验收成稿的最低视觉要求。根据内容选择视觉风格，让主视觉有足够的画面面积，建立清楚的图文层级，保持版式、图文细节与交互状态一致；在实际渲染中核对整体完成度。
- 新建课程与新增页面使用生成器分配 UUID v4；复制为独立课件时更换课程及全部页面身份。更新保留已有 UUID。课程目录、`outlines.json.id`、`moduleIdentity.id` 一致；页面 UUID 贯通大纲、PPT、Guide 和讲稿。详见[身份与资源](references/engineering/module-assets.md)。
- 画布为 1600×900，外层等比例缩放。封面独立设计，其余页默认用 Shared `ContentBlock` 标准标题区，独立文字用 `Typography`；用户指定版式按其范围执行。
- Shared 与内置示例只读。缺失时可原样复制完整 `shared/`，已有时不覆盖；课程专属内容留在课程目录。`modules/` 是示例，用户成果保存到目标工程。
- 视觉组件从 `@shuku/course-style/react` 导入，资源、请求与状态从 `@shuku/course-runtime/react/...` 导入。资源 helper 只接收一个完整真实相对路径；动态选择使用完整路径列表，不拼接路径。
- 标题缺失或空白时使用“未命名标题”；讲稿 `snippet` 缺失补空字符串，允许为空，不编造讲稿。身份与入口不可用展示默认值替代。
- 页面放 `pages/<语义页目录>/`，正式资源放课程 `assets/`。中间文件放所属页或模块 `_scratchpad/`；逐页收尾与提交前调用 `scratchpad.clean <范围> --apply`，先转存需保留的设计、素材和记录。清理参数见[工具索引](references/tools.md)。

## 工程与依赖

用户要创建独立工程且仓库提供 `new` 脚本时，从 Skill 根目录运行 `npm run new -- "<新工程目录>"`，创建可编辑示例和工程配置，再按当前任务制作。旧版仓库使用 [module.init 和 Shared 初始化流程](references/engineering/module-assets.md)。将用户的课件创作放在目标工程，内置示例用于演示和复制。

每个窗口先用 `context.create` 绑定用户指定的工程绝对路径，可进一步限定课程；将 `--context-directory` 指向目标课程内适用的 `_scratchpad/`。之后调用 `tools.py --context <返回的绝对配置路径> <工具>`。每个窗口有独立配置，命令只向子进程传递目标，不改共享的“当前工程”。旧 `target-root.json` 仍兼容，只作为单窗口默认值；新任务不靠改它切换工程。具体命令与边界见[本地环境与窗口](references/engineering/local-environment.md)。

从 Skill 根目录用 `npm start -- --context "<context.create 返回的绝对配置路径>"` 启动预览，打开终端输出地址并选择目标课件。本地预览默认使用仓库中随附的 Shuku 播放器、播放入口、课程运行时和默认风格，可独立验证真实渲染、课件素材及本地交互。AI 评阅、平台提交、GPU 等术库服务按任务单独接入。作者可在预览中用「发布到术库」准备当前课件 ZIP，并进入术库预审和确认上传。正式构建和发布依照[交付说明](references/engineering/delivery.md)。

按实际任务探测 Python、Node、解析依赖、课程运行时、构建依赖、浏览器与 FFmpeg。已有依赖默认启用原有检查；齐全时默认类型检查、本地构建、真实浏览器检查。有音视频就处理，没有就跳过。Node解析器可用时优先复用原有完整引用迁移，Python解析作为受限补充，不替代或删除原有能力。

缺依赖先读持久化安装意愿，只问一次，并用 `dependencies.policy` 保存回答。多窗口共用同一份偏好；`pending` 不重复提问，`allowed` 直接补依赖重试，`declined` 继续可执行检查并标明未验证范围。安装失败不能再次询问意愿。配置缺失与安装意愿分开处理。详见[依赖流程](references/engineering/local-environment.md)。

本地尽量发现并修复错误；服务器仍独立入库、安全检查和正式构建，生成正式缩略图并发布。本地截图与交互证据须对应本次交付副本，不以设计图冒充实现。保留本地预览入口和原有 Node 检测工具。

## 按当前动作读取

| 动作 | 资料 |
|---|---|
| 创作、改编与续作 | [共用流程](references/workflow/common.md)，再选[从零创作](references/workflow/from-scratch.md)或[参考改编](references/workflow/reference-adaptation.md) |
| 主线、章节与逐页大纲 | [大纲](references/design/course-outline.md) |
| 讲稿与 TTS | [口播](references/design/spoken-narration.md) |
| 页面构图与交互 | [设计](references/design/design.md) |
| React、入口与沙箱输入 | [实现](references/engineering/implementation.md) |
| 身份、Shared 与素材 | [身份与资源](references/engineering/module-assets.md) |
| 检查与验收 | [基础检查](references/eval/checks.md)；用户要求评分时再读 [Rubric](references/eval/rubric-evaluation.md) |
| 习题、问卷、模型与计算 | [习题](references/design/quiz.md) / [问卷](references/design/surveys.md) / [大模型](references/computing/llm.md) / [GPU](references/computing/gpu.md) |
| 工具、参数及可选本地预览 | [工具索引](references/tools.md) / [术库本地预览](player-preview/README.md) |

设计与制作先完成必读资料通读，再按当前动作读取上表中的相关资料。

## 源码交付

运行 `python <Skill>/scripts/module/package_course.py <课程或工程目录>`，或 `tools.py course.pack <目录>`。一次完成环境调度、源码检查、媒体准备、引用迁移、可用的本地深入检查、归档与完整性核验。转换与改引用仅发生在临时副本，原工程不修改。默认 Shared、缓存与临时文件不入包，明确依赖的自定义风格保留。

stdout 是精简 JSON，完整转换映射、问题与行号保存在同级 `.report.json`，简明说明在 `.report.md`。智能体先修复授权范围内可确定的问题再重跑；不可靠的转换路径、碰撞或转换失败阻止出包，不猜测修复。详见[交付与依赖](references/engineering/delivery.md)。

交付普通 ZIP，不要求用户选择版本标签。工具不上传；Shuku 独立进行入库、安全、编译和运行检查，正式缩略图与内容审核单独执行。未执行的服务器检查不能标为本地通过。
