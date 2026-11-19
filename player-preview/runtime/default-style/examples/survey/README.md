# 可复制的标准问卷控件

从 `SurveyExample.tsx` 开始：改 `title`、题目的 `title` 和选项的 `label` 即可。`key` 是答案标识，开始收集后应保持稳定。

`SurveyTemplate` 是可选的受控界面，传入 `definition`、`answers`、`onChange`。它不登记问卷、不发请求，也不改变已有的答案协议。需要提交按钮时传入 `onSubmit(answers)`；没有回调时只显示题目。`disabled`、`submitting`、`feedback` 和 `footer` 可用于呈现宿主的真实状态。

线上收集沿用当前流程：先在课程详情登记并开放相同标识与结构的问卷，再使用现有运行时：

```tsx
import {useState} from 'react';
import {SurveyTemplate} from '@shuku/course-style/react';
import {useCourseSurvey} from '@shuku/course-runtime/react/useCourseSurvey';

export function MySurvey() {
  const {session, loading, busy, error, submit} = useCourseSurvey('image-preference');
  const [draft, setDraft] = useState<Record<string, unknown> | null>(null);
  if (!session) return <p>{loading ? '正在读取问卷…' : error}</p>;
  const answers = draft ?? session.my_response?.answers ?? {};
  const definition = session.survey.definition;
  const blocked = loading || session.survey.status !== 'open'
    || (!!definition.login_required && !session.is_logged_in)
    || (!!session.my_response && !definition.allow_update);
  return <SurveyTemplate definition={definition} answers={answers} onChange={setDraft}
    disabled={blocked} submitting={busy}
    onSubmit={values => {void submit(values);}}
    feedback={<span role="status">{error || (session.my_response ? '已提交' : '')}</span>}/>;
}
```

此简例对应匿名问卷；游客记名还需由作者收集称呼，并通过现有 `submit(values, displayName)` 传入。也可以直接继续使用已有的 `SurveyForm` 处理完整的身份与保存流程。

## 只换一道题的界面

```tsx
<SurveyTemplate {...props} renderQuestion={(question, value, onChange) => {
  if (question.key !== 'preference') return undefined;
  return question.options?.map(option => <button
    key={option.key} type="button" aria-pressed={value === option.key}
    onClick={() => onChange(option.key)}
  >
    {/* 这里可以替换成作者自己的图片、卡片或交互内容。 */}
    {option.label}
  </button>);
}}/>
```

回调返回 `undefined` 时使用标准控件；自定义控件通过 `onChange(value)` 返回同一道题原先约定的答案。外观变化不改变选项 key、字段含义或后端统计。`custom` 题也使用这个回调提供输入界面。

标准字段最终仍由已有服务端验证。模板没有新增自动注册、初始化 RPC、协议版本或数据库结构；本地演示的提交回调仅用于查看答案，不会保存到平台。
