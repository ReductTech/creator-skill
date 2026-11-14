import {useState, type ReactNode} from 'react';
import {SurveyTemplate} from '@shuku/course-style/react';
import type {SurveyAnswers, SurveyDefinition, SurveyOption} from '@shuku/course-runtime/react/surveys';

// See references/design/surveys.md before copying: the selected style must export
// SurveyTemplate, or the UI import must point to course-local copied components.
// This is a local controlled example. Its callback does not register a survey.
export const surveyDefinition: SurveyDefinition = {
  title: '图片偏好调研',
  description: '请选择更喜欢的方案，也可以留下你的理由。',
  login_required: false,
  identity_mode: 'anonymous',
  questions: [
    {key:'preference',title:'你更喜欢哪一个方案？',kind:'single',required:true,
      options:[{key:'a',label:'方案 A'},{key:'b',label:'方案 B'}]},
    {key:'reason',title:'为什么这样选择？',kind:'text',max_length:1000},
  ],
};

export interface SurveyExampleProps {
  onSubmit: (answers: SurveyAnswers) => void;
  customCards?: boolean;
  /** Supply an image or your own content; no media path is hardcoded here. */
  renderOption?: (option: SurveyOption) => ReactNode;
  disabled?: boolean;
}

export function SurveyExample({onSubmit, customCards=false, renderOption, disabled=false}: SurveyExampleProps) {
  const [answers,setAnswers]=useState<SurveyAnswers>({});
  return <SurveyTemplate definition={surveyDefinition} answers={answers} onChange={setAnswers}
    disabled={disabled} onSubmit={onSubmit} footer="请选择一个方案；文字说明为选填。"
    renderQuestion={(question,value,onChange)=>{
      if(!customCards||question.key!=='preference')return undefined;
      return <div style={{display:'grid',gridTemplateColumns:'repeat(2,minmax(0,1fr))',gap:16}}>
        {question.options?.map(option=><button key={option.key} type="button" disabled={disabled}
          aria-label={option.label} aria-pressed={value===option.key} onClick={()=>onChange(option.key)}
          style={{padding:18,borderRadius:10,textAlign:'left',maxWidth:'100%',
            background:value===option.key?'var(--shuku-surface-soft,#edf2f8)':'var(--shuku-surface,#fff)',
            border:'1px solid '+(value===option.key?'var(--shuku-accent,#4d6f9f)':'var(--shuku-line,#dfe6ef)')}}>
          {renderOption?.(option)??option.label}
        </button>)}
      </div>;
    }}/>;
}
