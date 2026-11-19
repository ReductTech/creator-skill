import {requestCourse} from './courseRequests';

export interface ShortAnswerAssessment {
 verdict: '正确' | '接近正确' | '错误';
 explanation: string;
}

/** Platform assessment contract; the selected style decides how to display it. */
export async function evaluateShortAnswer(input:{question:string;referenceAnswer:string;answer:string}):Promise<ShortAnswerAssessment>{
 const envelope=await requestCourse<unknown>({action:'compute',endpoint:'/short-answer/evaluate',payload:{question:input.question,reference_answer:input.referenceAnswer,answer:input.answer}});
 if(!envelope||typeof envelope!=='object')throw new Error('简答题评阅服务不可用。');
 const payload=envelope as {structured?:unknown;result?:unknown};
 if(payload.structured!==true||!payload.result||typeof payload.result!=='object')throw new Error('评阅服务没有返回结构化结果。');
 const result=payload.result as {verdict?:unknown;explanation?:unknown};
 if(typeof result.verdict!=='string'||!['正确','接近正确','错误'].includes(result.verdict)||typeof result.explanation!=='string')throw new Error('评阅服务返回了无效结果。');
 return result as ShortAnswerAssessment;
}
