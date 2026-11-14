---
name: creator-skill
description: 规划、设计、制作或修改 React 交互演示，包括主线、大纲、口播、从零创作与 PPT/PDF 改编、课件内问卷与投票，以及 Shuku 课件检查和源码 ZIP 交付。适用于教学、科研和商业汇报，不用于普通网站或一般文档。
---

# React 演示创作

## 强制约束：执行前逐项核对

以下规则独立列出，允许与后文重复。新建或更新前先判断任务类型；设计、实现和交付时均须遵守，不因已有示例或其他参考说明而省略。

1. **先分清新建与更新，正确处理 UUID。**
   - **新建课件**：强烈推荐为课件及每一页全部生成新的 UUID；从示例或已有课件复制为独立新课件时，必须更换课件 UUID 和所有页面 UUID，不得沿用示例身份。同步课程目录、`outlines.json.id`、`moduleIdentity.id`，以及 PPT、Guide、讲稿、跳转和资源中的身份引用。
   - **UUID 必须用规范生成器生成**，例如 Python `uuid.uuid4()` 或 JavaScript `crypto.randomUUID()`，使用标准小写、带连字符的 UUID v4。禁止猜测、手写、随意拼接、顺序编号或根据标题、路径推导 UUID；不要直接复用文档中的示例值。
   - **更新已有课件**：课件 UUID 和已有页面 UUID 保持不变；改标题、讲稿、内容、样式或页序均不重新生成身份。仅新增的独立页面使用生成器分配新 UUID，不连带修改其他页面。
2. **细致复刻用户给出的设计示意图，不得偷懒。** 逐项对齐布局、比例、间距、字号、颜色、图形、素材位置与交互意图，不能仅保留大致结构或自行简化。真实渲染后与设计图对照，修正可见差异；不能把整张设计图贴作背景代替正式实现。所有画布仍遵守不添加页码的要求。
3. **预览模块在本 Skill 根目录的 `player-preview/`。** 按其 [README](player-preview/README.md) 安装和启动，确认目标课件实际可打开后，向用户提供真实预览链接，并在预览期间保持服务运行。
4. **模块示例在本 Skill 根目录的 `modules/`。** 可读取和复制示例作为起点；新建时执行上面的 UUID 更换规则，不为制作用户课件而修改原示例。用户课件保存到已配置的目标工程。
5. **不允许修改 Shared。** 本 Skill 根目录的 `shared/` 和目标工程中的 Shared 都只读使用；允许原样复制到缺失的目标位置，禁止改动其源码、样式、资源、`style.json` 或公共行为，也不覆盖已有 Shared。课程专属调整留在课程目录，不能通过改 Shared 让当前页达标。

6. **逐页清理临时目录，交付和提交前再清理。** 每完成一页并完成必要核对，运行 `scratchpad.clean <该页目录> --apply`；整门课收尾、打包交付或 Git 提交前，对本次课件目录再运行一次，确保没有遗留 `_scratchpad`。先将需长期保留的设计图、正式素材和必要记录放到正式位置或用户交付目录；清理后不能仍引用临时路径。支持直接指定绝对路径，递归清理所有嵌套层级的 `_scratchpad`，不按普通目录名称排除；仅不跟随链接/junction，防止越界。此临时目录清理适用于 Shared 下的 `_scratchpad`，不得修改其他 Shared 文件。命令默认只预览，实际删除须带 `--apply`，详见[临时目录清理](references/tools.md#临时目录清理)。

## 开始与续作

先确定目标、已有成果和当前阶段。仅讨论主线、大纲、讲稿或设计时，无需工程配置或创建文件；工程操作按下方配置定位课程。

- 创作、改编与续作：读[流程共用说明](references/workflow/common.md)，再选[从零创作](references/workflow/from-scratch.md)或[参考改编](references/workflow/reference-adaptation.md)。修改已有模块沿用原流程，从当前阶段接续。
- 仅维护缩略图：直接读[截图和缩略图](references/tools.md#截图和缩略图)，不重走创作流程。
- 仅迁移素材引用（包括格式转换后的动态路径）：使用独立工具 `assets.rewrite`，读[路径迁移](references/engineering/asset-paths.md)；与 `assets.compress` 分开执行，先预览再按已授权范围应用。
- 压缩课件图片：默认连续完成[压缩、迁移与查漏](references/engineering/asset-paths.md#压缩后的默认连续流程)。用户要求实际压缩时，相关引用迁移与遗漏检查属于同一任务，主动执行，不再等待用户另行提醒；用户只要求预览或明确限定范围时遵守其限制。
- 按下表读取当前动作所需资料；仍在上下文中的内容不重复读，不预读整个参考目录。已有确认、检查和产物仅在仍对应当前版本与范围时复用。

## 工程定位

工程操作前读本 Skill 的本地 `target-root.json`：`{"targetRoot":"用户指定的课程工程绝对路径"}`。首次按用户提供的有效目录创建，缺少目录时询问；该文件由 Git 忽略。后续沿用，不按 cwd、Skill 位置或旧环境变量猜测或切换工程。

`CREATOR_SKILL_TARGET_CONFIG` 可指定本次调用专用配置，仍只含 `targetRoot`，不改变本地绑定。工具发现、`--help` 与 Skill 自身检查无需目标配置。构建和打包另以 `--shuku-root` 显式指定 Shuku，不能把它当成课程根目录。

## 关键约束

- 每页围绕一个主要信息或问题，视觉和交互承担解释功能。教学方法、习题与 Guide 按任务需要采用。
- 每页按“ImageGen 设计图 → 用户确认 → React 实现与自检 → 用户验收”推进，当前页验收后进入下一页。已有有效确认继续沿用；确认范围、局部修改与用户明确调整流程的规则见[共用说明](references/workflow/common.md#设计实现与确认)。
- 生图前读设计指导并实际查看相关成对正反例，把借鉴与避让决策写入提示词；工具边界见[页面设计指导](references/design/design.md#视觉设计图的工具约束)。
- React 使用 1600×900 固定画布、外层等比例缩放。第一页独立设计封面，其余页默认使用 Shared `ContentBlock` 标准标题区；独立文字用 `Typography`。用户明确指定的版式按指定范围执行。
- 所有课件的设计示意图与正式页面画布均不添加页码、总页数或页序角标；每次生图提示词明确写“不添加页码”，参考原稿和样例中的页码也不保留。
- 课程目录 UUID、`outlines.json.id`、`moduleIdentity.id` 相等；`moduleIdentity` 只含 `version`、`id`。每页登记非空 `id`、`title`、`snippet`，页面 UUID 稳定且与 PPT、Guide、讲稿一致，新增用 UUID v4。大纲不增加其他页面字段，不编造用户尚未提供的内容。
- 页面放 `pages/<语义页目录>/<同名组件及样式>`，按实际制作进度建目录。逐页中间产物放页内 `_scratchpad/`，整体原稿和记录放模块级 `_scratchpad/`；正式素材放课程 `assets/`。
- 视觉组件从 `@shuku/course-style/react` 导入；资源、请求与状态从 `@shuku/course-runtime/react/...` 导入。`moduleAssetUrl('真实相对路径')` 与 `moduleJson('真实相对路径')` 仅接受一个参数；不从 Shared 导入内核接口，不维护历史资源映射。
- 初始化用户工程时，直接将本 Skill 根目录的完整 `shared/` 复制到目标工程的 `modules/shared/`（平铺布局用 `shared/`）；目标已有 Shared 时复用，不覆盖。路径、风格登记与 UUID 规则见[复制内置 Shared](references/engineering/module-assets.md#复制内置-shared)。
- 课程源码与风格在课程工程，正式构建与运行时在 Shuku。制作时可用内置 Player Preview 预览源码；交付展示和截图验收仍使用平台构建产物，本地预览不能代替最终 ZIP 验收。

## 按动作读取

| 当前动作 | 资料 |
|---|---|
| 主线、章节、开场、大纲（含纯聊天） | [大纲](references/design/course-outline.md) |
| 逐页讲稿、口播或 TTS | [口播](references/design/spoken-narration.md) |
| 页面构图与交互设计 | [设计](references/design/design.md) |
| React 实现、入口与布局 | [工程实现](references/engineering/implementation.md) |
| 课程/风格 UUID、素材、OSS | [身份与资源](references/engineering/module-assets.md) |
| 本地开发预览、安装或构建播放器 | [Player Preview](player-preview/README.md) |
| 页面检查与验收 | [基础检查](references/eval/checks.md) |
| 构建、源码 ZIP 与上传交付 | [交付](references/engineering/delivery.md) |
| 执行工具、参数与依赖 | [工具索引](references/tools.md)，优先 `describe <ID>` 与 `<ID> --help` |
| 习题 / 大模型 / GPU | [习题](references/design/quiz.md) / [大模型](references/computing/llm.md) / [计算](references/computing/gpu.md) |
| 问卷、投票、调研、标准控件与 Custom 交互 | [问卷接入与可复制示例](references/design/surveys.md)，先复用标准控件，再按需要替换单题外观 |
| 用户明确要求评分 / 个人偏好 | [Rubric](references/eval/rubric-evaluation.md) / [偏好](references/preferences.md) |

## 完成

按影响范围检查真实渲染、内容与相关交互，修复后复验；随后按上方规则清理本次课件的 `_scratchpad`，再交付或提交。不默认执行评分或全仓测试。交付简述完成内容、实际验证与剩余限制，未执行的检查标为未验证。
