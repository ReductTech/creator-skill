# 模型与较重计算

训练、推理、Embedding 等使用 Shuku 已登记的计算任务；普通数学与可实时完成的可视化留在前端。

```tsx
import { requestCourse } from '@shuku/course-runtime/react/courseRequests';
const submitted = await requestCourse({action:'compute', endpoint, payload, async:true});
// 仅当该任务实际返回 task 标识时查询，具体字段以当前任务契约为准。
const status = await requestCourse({action:'status', task});
```

通过术库父页面转发请求，不直连 GPU、不拼旧训练 URL。端点、输入与响应从当前 Shuku 任务注册和后端实现核对；计算实现位于 `backend/src/shuku_compute/` 等平台目录，Worker 负责任务执行，课程只维护自己的输入和展示逻辑。

- 采用教学所需的小模型、有界数据与参数；等待、失败、重试和重置有明确反馈。
- 明确命名的预计算记录用 `requestCourse({action:'record',name,payload})`；普通静态 JSON 用 `moduleJson('真实路径')`。独立截图只支持平台规定的冻结演示记录，不假装调用真实服务。
- 缺少 GPU 或服务时，说明受影响功能；核心学习流程尽量可用，缓存或模拟结果明确标识。
- 设备策略、凭据、队列与服务启停归 Shuku，课程不实现这些逻辑。旧 `28431`、`/api/lab`、`IDL_DEVICE` 与 `idl_backend` 不是接入契约。
- 仅在任务已授权时运行训练、下载或启动服务，未执行的真实计算标为未验证。
