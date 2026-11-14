# 问卷、投票与科研调研

用于课件中的偏好投票、市场调研、量表、表格填写和实验数据收集。不要求正确答案；有正确答案的教学练习仍用[习题流程](quiz.md)。

## 从现有示范开始

- [可复制的课件示例](../../assets/examples/surveys/SurveyExample.tsx)：问卷定义、标准控件和自定义卡片在同一文件。
- [标准控件预览源码](../../player-preview/preview/survey-template-demo.tsx)：三张演示页，分别展示标准模板、替换单题外观和十种题型。
- [场景预览源码](../../player-preview/preview/survey-demo.tsx)：图片投票、综合调研、表格与管理者结果的界面示意。

先按 [Player Preview](../../player-preview/README.md) 的现有配置启动 `npm run dev`，打开终端实际地址并添加 `?demo=survey-template`。默认端口 5174；被占用时可运行 `npm run dev -- --port 5175`。已有服务可用就复用，不为预览另写网站、播放器或接口服务。启动后实际打开页面，确认三页及相关交互可用，再给用户链接；运行期间保持服务。

标准控件演示使用 Shuku 的真实控件和本地回调，不连接数据库，不模拟真实登录，也不能证明线上保存成功。预览别名 `@preview/*` 只用于工具，不能复制进课程源码。

## 先选接入方式

| 需要 | 使用方式 |
| --- | --- |
| 只看效果，或先做好页面 | `SurveyTemplate` + 本地 `answers/onChange/onSubmit`，参考可复制示例 |
| 直接使用完整在线填写流程 | `SurveyForm surveyKey="已登记的问卷key"`，由控件处理读取、身份提示和提交 |
| 保留标准外观，自己组织在线流程 | `useCourseSurvey(key)` + `SurveyTemplate`，从 `session.survey.definition` 读取定义，将回调接到 `submit(answers, displayName)` |
| 自定义图片、拖拽、实验画布 | 为指定题目提供 `renderQuestion`；需要更自由的流程时直接使用运行时 API |

`SurveyTemplate` 只负责呈现，接收 `definition`、`answers` 和 `onChange`；传入 `onSubmit` 才显示提交按钮。`disabled`、`submitting`、`feedback`、`footer` 用于呈现真实宿主状态。它不自动登记问卷、不发请求。普通控件与自定义控件最终都提交同一份答案。

**当前实现仍需课件管理员在课程详情登记并开放问卷。** “随课件发布自动登记”只是讨论过的方向，尚未实现。仅复制配置、放一个组件或在预览中点击提交，不会在平台生成问卷或保存答卷。

## 检查风格依赖后再复制

课件运行时位于当前 Shuku 的 `packages/course-runtime/`，标准控件位于 `packages/course-styles/default/react/learning/`。Shuku 的位置按预览配置 `SHUKU_ROOT` 或实际已确认路径定位，不写死开发者机器路径。

1. 先检查当前选定风格是否导出 `SurveyTemplate` / `SurveyForm`。有导出时，通过 `@shuku/course-style/react` 引用即可。
2. 当前 Shared 没有这些组件时，不修改或覆盖 Shared。可以由作者按任务范围选择支持它们的风格；也可以把 Shuku 中的 `SurveyTemplate.tsx`、`SurveyTemplate.css`、`SurveyForm.tsx`、`SurveyForm.css` 复制到本课程的 `components/survey/`，保留它们的相对依赖，再将示例的 UI import 改成本课程相对路径。运行时仍使用 `@shuku/course-runtime`。

不要从已编译的 `dist` 或官网包中反向抄组件，不把平台前端、管理页面、后端服务或数据库配置装进课程 ZIP。需要核对更详细的协议时，查看同一 Shuku 版本的 `docs/SURVEYS.md` 和运行时类型。

## 作者通常只改这些

复制示例到本课程，修改问卷标题、问题文案、选项显示名与必要的题型。新建独立调研时分配自己的问卷 key；开始收集后保留问题、选项、行列的 key。改外观或文字不应把旧选项 key 改成另一个含义。

`renderQuestion(question, value, onChange)` 的约定：

- 返回 `undefined`：使用标准控件。
- 返回自己的界面：选择、拖拽等动作后调用 `onChange(value)`。
- 单选题仍返回该题选项 key，例如 `"a"`；换成图片卡片不需要改成 `custom`，也不改变统计规则。
- 真正的 `custom` 题可返回 JSON，例如 `{format: "image-annotation", version: 1, data: {...}}`。这里的格式名称和版本由作者约定，不是新增的平台协议。平台保存明细，不推断其统计含义；希望平台统计的数值、选项应另设标准字段。

自定义输入需尊重传入的禁用状态；标准模板的外层 fieldset 会禁用其中的原生控件，画布等自定义事件还需由作者检查对应状态。媒体继续使用 `moduleAssetUrl('真实素材路径')`，答案保存素材标识、坐标或其他轻量数据，不塞入大图片或文件。

## 真正接入保存

最短的在线入口如下，问卷 key 必须已由本课件管理员登记：

```tsx
import {SurveyForm} from '@shuku/course-style/react';

export function StudySurvey() {
  return <SurveyForm surveyKey="image-preference" />;
}
```

完全自定义时，从 `@shuku/course-runtime/react/surveys` 使用 `readSurvey`、`submitSurvey` 和 `surveyRequestKey`；或使用 `@shuku/course-runtime/react/useCourseSurvey` 的 React 适配。不要自行向课件传递用户 ID、伪造登录或直连数据库。当前课程范围和身份由网站宿主确定。

手写 `submitSurvey` 时，携带读取到的 `definition_version`、本次提交的 `request_key` 与 `answers`；同一次提交的网络重试沿用同一份请求。允许修改答卷时，携带当前答卷的 `expected_response_version`。使用 `useCourseSurvey` 时，这些细节由 hook 处理。

要求登录与记名方式是独立规则。游客记名需要自行填写称呼；登录记名使用账号身份。匿名答卷不向课件管理员返回账号；问卷结果只允许本课件管理员查看，系统管理员身份本身不扩大权限。课程详情的结果页面不应被复制进课件或通过课件接口绕过权限。

自定义在线流程要保留：读取等待、登录要求、未开放或已结束、已提交且不允许修改、提交中和失败后的重试。输入不要因失败丢失。不要在浏览器截图、独立打开或离线包中假装提交成功；课件 iframe 中的点击使用 `type="button"`，沿用[沙箱输入约定](../engineering/implementation.md#播放器沙箱内的输入与提交)。

## 按改动验证

只整理文档时运行 `check.skill` 并检查引用。复制控件或改页面时，按当前工程真实检查入口验证类型、渲染与关键交互：标准选项与自定义外观应产生相同 key/value；条件题与必填规则保持对应；输入和反馈不越出画布。标准题型示范已有单选、多选、填空、数值、评分、排序、矩阵单选、矩阵多选、表格和 Custom，无需重写一套展示。

线上保存要在有权限的术库宿主里验证，结果应出现在课程详情的问卷管理区域。只有本地回调或示例统计时，交付说明为“界面预览”，不能称为已接入数据库或已部署。
