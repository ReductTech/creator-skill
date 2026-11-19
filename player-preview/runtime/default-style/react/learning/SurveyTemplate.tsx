import type {ComponentProps, ReactNode} from 'react';
import type {SurveyAnswers, SurveyDefinition} from '@shuku/course-runtime/react/surveys';
import {SurveyFields} from './SurveyForm';
import './SurveyTemplate.css';

export type SurveyQuestionRenderer = NonNullable<ComponentProps<typeof SurveyFields>['renderQuestion']>;

export interface SurveyTemplateProps {
  definition: SurveyDefinition;
  answers: SurveyAnswers;
  onChange: (answers: SurveyAnswers) => void;
  /** Supply the existing survey submit callback, or a local callback for a preview. */
  onSubmit?: (answers: SurveyAnswers) => void;
  renderQuestion?: SurveyQuestionRenderer;
  disabled?: boolean;
  submitting?: boolean;
  submitLabel?: string;
  /** The host can display its actual identity policy, save state or public error here. */
  footer?: ReactNode;
  feedback?: ReactNode;
}

/** Optional, controlled authoring template. It never registers surveys or sends requests. */
export function SurveyTemplate({definition, answers, onChange, onSubmit, renderQuestion,
  disabled = false, submitting = false, submitLabel = '提交问卷', footer, feedback}: SurveyTemplateProps) {
  const blocked = disabled || submitting;
  return <section className="shuku-survey-template" aria-busy={submitting} aria-label={definition.title}>
    <header className="shuku-survey-template-heading">
      <span className="shuku-survey-template-eyebrow">问卷调研</span>
      <h2>{definition.title}</h2>
      {definition.description && <p>{definition.description}</p>}
    </header>
    <SurveyFields definition={definition} answers={answers} onChange={onChange}
      disabled={blocked} renderQuestion={renderQuestion}/>
    {(footer || onSubmit) && <footer className="shuku-survey-template-footer">
      <div className="shuku-survey-template-note">{footer}</div>
      {onSubmit && <button type="button" className="shuku-survey-template-submit" disabled={blocked}
        onClick={() => onSubmit(answers)}>{submitting ? '正在提交…' : submitLabel}</button>}
    </footer>}
    {feedback && <div className="shuku-survey-template-feedback">{feedback}</div>}
  </section>;
}
