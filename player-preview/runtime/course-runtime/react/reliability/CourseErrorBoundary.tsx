import {Component,type ErrorInfo,type ReactNode} from 'react';

export class CourseErrorBoundary extends Component<{children:ReactNode;page?:string},{failed:boolean}>{
 state={failed:false};
 static getDerivedStateFromError(){return {failed:true};}
 componentDidCatch(error:unknown,_info:ErrorInfo){
  try{
  const value=error instanceof Error?error:{name:'Error',message:String(error??'未知渲染错误'),stack:''};
  const params=new URLSearchParams(location.search);
  if(params.has('scenedeckCapture')&&params.get('shukuViewer')!=='1')Reflect.set(window,'__SHUKU_CAPTURE_ERROR__',String(value.message).slice(0,500));
  if(parent!==window)parent.postMessage({channel:'shuku-runtime-diagnostic-v1',kind:'render-error',fatal:true,
   page:this.props.page,name:String(value.name).slice(0,80),message:String(value.message).slice(0,500),stack:String(value.stack||'').slice(0,2200)},'*');
  }catch{/* The recovery UI must survive even a malformed thrown value. */}
 }
 render(){
  if(!this.state.failed)return this.props.children;
  return <section role="alert" data-course-error data-capture-ready="false" style={{padding:32,margin:20,fontFamily:'system-ui',background:'#fff',color:'#263a53',border:'1px solid #dce5ee',borderRadius:10}}>
   <h2>本页暂时无法显示</h2><p>可以重试本页，或通过课件导航切换到其他页面继续。</p><small>SHK-03-08-001</small>
   <button onClick={()=>this.setState({failed:false})}>重试本页</button>
  </section>;
 }
}
