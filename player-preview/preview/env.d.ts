/// <reference types="vite/client" />

declare module 'virtual:preview-catalog' {
  interface Course {
    id: string; alias?: string; assetId: string; title: string;
    description?: string; badge?: string; entry?: string;
    ppt?: {entry?: string};
    pages: {id: string; title?: string; snippet?: unknown}[];
  }
  const courses: Course[];
  export default courses;
}
declare module '@preview/runtime' {
  import type {ComponentType} from 'react';
  export const SceneDeck: ComponentType<{
    catalog: {id: string; [key: string]: unknown}[];
    moduleId: string; assetId: string; progressKey: string;
    getNotes: (id: string) => {text: string; selectors: string[]}[];
  }>;
}
declare module '@preview/runtime-styles';

declare module '@preview/survey-template' {
  import type {ComponentType, ReactNode} from 'react';
  export interface PreviewQuestion {key: string; title: string; kind: string; options?: {key: string; label: string}[]; [key: string]: unknown}
  export interface PreviewDefinition {title: string; description?: string; questions: PreviewQuestion[]; [key: string]: unknown}
  export const SurveyTemplate: ComponentType<{
    definition: PreviewDefinition; answers: Record<string, unknown>;
    onChange: (answers: Record<string, unknown>) => void;
    onSubmit?: (answers: Record<string, unknown>) => void;
    renderQuestion?: (question: PreviewQuestion, value: unknown, onChange: (value: unknown) => void) => ReactNode;
    disabled?: boolean; submitting?: boolean; submitLabel?: string; footer?: ReactNode; feedback?: ReactNode;
  }>;
}
declare module '@preview/survey-example' {
  import type {ComponentType} from 'react';
  import type {PreviewDefinition} from '@preview/survey-template';
  export const surveyExampleDefinition: PreviewDefinition;
  export const SurveyExample: ComponentType<{onSubmit?: (answers: Record<string, unknown>) => void}>;
}
