# Shuku 播放内核

本包只维护页面身份与编排、播放通信、资源访问、平台请求、学习状态和异常恢复，不包含字体、配色、控件、教学布局或第三方可视化库。

- `react/presentation/useCoursePlayback.ts`：播放状态与宿主通信，不渲染界面。
- `react/presentation/types.ts`：风格适配器可复用的类型。
- `react/assets.ts`、`moduleJson.ts`：当前课件资源访问。
- `react/courseRequests.ts`、`courseState.ts`：平台服务与隔离的学习状态。
- `react/surveys.ts`、`useCourseSurvey.ts`：问卷读取、提交及可选 React 状态适配；基础表单位于默认风格包，详见 [问卷与调研](../../../references/design/surveys.md)。
- `react/assessment.ts`：简答评阅的请求与返回契约，反馈外观由风格决定。
- `react/reliability/CourseErrorBoundary.tsx`：运行异常和截图失败边界。

发布资源清单缺少图片时，`moduleAssetUrl` 返回不可解码的图片地址，并按课程和路径只警告一次；图片组件可通过 `onError` 显示局部提示，Canvas 消费者可处理 `decode()` 拒绝，不因资源查询直接抛错中断页面渲染。不猜测 OSS 地址或其他版本的素材。缺失 JSON 等非图片资源、非法路径和缺少课程上下文仍会报错。

课程视觉组件通过 `@shuku/course-style` 引用。平台默认风格随镜像从 `packages/course-styles/default` 提供；上传者也可以携带 IDL `modules/shared` 或自己的风格包，并非本内核的固定 UI。风格可以自行实现字体、布局、控件与内部交互，只需遵守当前播放协议。

参见 [风格包与编辑选择](../../../references/engineering/module-assets.md)。

风格包不再转发内核接口。课程直接从内核导入 `moduleAssetUrl`、`moduleJson`、`requestCourse`、`readCourseState`、`writeCourseState`；`currentCourseId` 返回当前课程身份。旧桌面 Telemetry 与技能记忆传输已删除，需要保留的练习状态通过内核状态接口读写，不采集全局 DOM 操作。

计算请求通过 `requestCourse` → 宿主 `courseBridge` → `/modules/{课程内部ID}/computations` → Worker 流转；网址中的课程 UUID 先解析为内部 ID，页面 UUID 只定位教学页面，不是模型或提示词配置 ID。请求身份使用安全随机 UUID，兼容 HTTP 及隔离 iframe。运行时代码随课件构建写入产物，修改后已有课件需重新构建。

决策分析依次请求 `/decision/intake` 与 `/decision/extra-factors`，后者返回恰好两个补充因素。因素结果同时包含 `direction` 和派生的 `value_transform`，CPU 在接收 Worker 结果时核对两者一致。计算缓存使用课程、接口、输入和执行版本；模型配置、课程版本或评阅契约变化时不复用旧结果。评阅契约版本不会影响视觉计算缓存。

自学导览可使用 `react/guide/useGuidePlayback.ts`：在课程自身的连续文档布局中，根据 `data-step-id` 观察当前章节，响应宿主的目录定位并报告讲稿。交互完成时通过 `reportGuideProgress` 上报真实完成状态；单纯滚动或定位不会标记完成。默认风格的 `LessonFlow` 已接入，其他风格可自行适配同一 `shuku-player-v1` 协议。内核不提供聊天控件或文档样式。

课程只按已有的自学入口与 PPT 入口分别加载。选择自学时导入自学入口，选择 PPT 时导入 PPT 入口及对应风格；入口内部的静态依赖由 Vite/Rollup 正常打包和初始化。平台不扫描页面源码推断加载边界，不自动把静态导入改写成动态导入，也不维护逐页预取队列。课程作者无需为平台拆页改写源码。若课程本身显式使用动态导入，其行为仍由课程自身决定。
