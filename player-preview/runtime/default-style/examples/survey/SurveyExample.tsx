import {useState} from 'react';
import type {SurveyAnswers, SurveyDefinition} from '@shuku/course-runtime/react/surveys';
import {SurveyTemplate} from '../../react/learning/SurveyTemplate';

// Copy this definition and change the title, question wording and option labels.
// Keep keys stable once answers have been collected.
export const surveyExampleDefinition: SurveyDefinition = {
  title: '图片偏好调研',
  description: '请选择更喜欢的方案，也可以留下你的理由。',
  login_required: false,
  identity_mode: 'anonymous',
  questions: [
    {key: 'preference', title: '你更喜欢哪一个方案？', kind: 'single', required: true,
      options: [{key: 'a', label: '方案 A'}, {key: 'b', label: '方案 B'}]},
    {key: 'reason', title: '为什么这样选择？', kind: 'text', max_length: 1000},
  ],
};

/** Local example. Supply a callback to connect the existing collection API. */
export function SurveyExample({onSubmit}: {onSubmit?: (answers: SurveyAnswers) => void}) {
  const [answers, setAnswers] = useState<SurveyAnswers>({});
  return <SurveyTemplate definition={surveyExampleDefinition} answers={answers} onChange={setAnswers}
    onSubmit={onSubmit} footer="请选择一个方案；文字说明为选填。"/>;
}
