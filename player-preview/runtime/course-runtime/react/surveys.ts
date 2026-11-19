/** Survey storage is course-scoped; authors own their markup and experiment flow. */
import {requestCourse} from './courseRequests.ts';
import {randomUuid} from './uuid.ts';

export type SurveyOption = {key:string;label:string};
export type SurveyColumn = SurveyOption & {kind?:'text'|'number'|'single';options?:SurveyOption[]};
export type SurveyQuestion = {
 key:string;title:string;kind:'single'|'multiple'|'text'|'number'|'rating'|'ranking'|'matrix_single'|'matrix_multiple'|'table'|'custom';
 description?:string;required?:boolean;options?:SurveyOption[];rows?:SurveyOption[];columns?:SurveyColumn[];
 minimum?:number|null;maximum?:number|null;max_length?:number;min_selections?:number;max_selections?:number|null;
 show_if?:{question:string;equals:string|number|boolean}|null;
};
export type SurveyDefinition = {
 title:string;description?:string;login_required?:boolean;identity_mode?:'anonymous'|'named';allow_update?:boolean;questions:SurveyQuestion[];
};
export type SurveyAnswers = Record<string,unknown>;
export type CourseSurvey = {key:string;version:number;definition_version:number;status:'draft'|'open'|'closed';definition:SurveyDefinition};
export type SurveyAnswer = {receipt:string;version:number;answers:SurveyAnswers;display_name?:string|null;user_id?:string|null;submitted_at:string;updated_at:string};
export type SurveySession = {survey:CourseSurvey;my_response:SurveyAnswer|null;is_logged_in:boolean};
export type SurveySubmission = {definition_version:number;answers:SurveyAnswers;request_key:string;display_name?:string;expected_response_version?:number};

export function readSurvey(key:string,signal?:AbortSignal){
 return requestCourse<SurveySession>({action:'survey.read',key},signal);
}
export function submitSurvey(key:string,submission:SurveySubmission,signal?:AbortSignal){
 return requestCourse<SurveyAnswer>({action:'survey.submit',key,submission},signal);
}
export function surveyRequestKey(){return randomUuid();}

export function isSurveyQuestionVisible(question:SurveyQuestion,answers:SurveyAnswers){
 const condition=question.show_if;
 if(!condition)return true;
 const value=answers[condition.question];
 return Array.isArray(value)?value.includes(condition.equals):value===condition.equals;
}

/** Remove hidden answers in order, including cascading conditional questions. */
export function visibleSurveyAnswers(definition:SurveyDefinition,answers:SurveyAnswers):SurveyAnswers{
 const result:SurveyAnswers={};
 for(const question of definition.questions){
  if(!isSurveyQuestionVisible(question,result)||!Object.hasOwn(answers,question.key))continue;
  const raw=answers[question.key],value=question.kind==='text'&&typeof raw==='string'?raw.trim():raw;
  // Server validation omits empty optional answers. Conditions must see the
  // same canonical values as the server, including trimmed free text.
  if(value==null||value===''||Array.isArray(value)&&!value.length||typeof value==='object'&&!Object.keys(value as object).length)continue;
  result[question.key]=value;
 }
 return result;
}
