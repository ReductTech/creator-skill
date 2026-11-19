/** Browser state is already isolated by account/course/release by the host. */
export function currentCourseId():string{
 const course=Reflect.get(globalThis,'__SHUKU_COURSE_ID__');
 return typeof course==='string'?course:'';
}
function storageKey(key:string){
 const course=currentCourseId();
 return course&&key?'shuku-runtime-state:'+JSON.stringify([course,key]):null;
}
export function readCourseState<T>(key:string):T|null{
 const scoped=storageKey(key);if(!scoped)return null;
 try{const record=JSON.parse(localStorage.getItem(scoped)||'null');return record?.version===1?record.value as T:null;}catch{return null;}
}
export function writeCourseState<T>(key:string,value:T){
 const scoped=storageKey(key);if(!scoped)return;
 try{localStorage.setItem(scoped,JSON.stringify({version:1,value}));}catch{/* Storage can be disabled by the browser. */}
}
