# 大模型与简答题

确定性计算留在页面；开放回答评价与语义生成使用 Shuku 的课程 RPC。页面不保存密钥、上游地址或模型认证，不直连旧 localhost 服务。

## 简答题

```tsx
import { Question } from '@shuku/course-style/react';
<Question type="short" title="为什么数像素也可以叫特征？"
  referenceAnswer="像素数量是按固定规则测得、可在样本间比较的数值。" />
```

PPT 使用揭示模式；Guide 由 Shared 提交题目、参考答案与学生回答。提供 `title` 和字符串 `referenceAnswer` 即可，不传题库 `taskId`。页面不通过 URL 或 DOM 判断模式。

内核 `@shuku/course-runtime/react/assessment` 的 `evaluateShortAnswer` 调用 `/short-answer/evaluate`，payload 为 `{question, reference_answer, answer}`。当前结构化响应包络为 `{structured:true,result:{verdict,explanation}}`，`verdict` 为“正确”“接近正确”“错误”；普通页面优先使用组件，避免重复解析。

## 自定义语义任务

```tsx
import { requestCourse } from '@shuku/course-runtime/react/courseRequests';
// endpoint 与 payload 必须来自当前 Shuku 已登记的任务契约。
const response = await requestCourse({action:'compute', endpoint, payload});
```

请求由术库父页面转发，课程单独打开时不能调用宿主 RPC。参考当前 Shuku 的 `packages/course-runtime/react/courseRequests.ts`、`assessment.ts` 与对应后端任务实现核对输入和响应，不假设所有任务共享同一包络。缺少任务时，明确需要平台扩展；不在课程 ZIP 中复制平台后端。

旧 `task_id` 题库模式、`VITE_LLM_SERVICE_URL`、`/api/ai`、`idl_backend` 与旧全局对象不受支持。等待、失败、重试与结果呈现必须真实；不把预计算记录冒充实时模型调用。
