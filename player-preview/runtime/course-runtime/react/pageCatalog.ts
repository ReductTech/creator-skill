/** Frozen build metadata exported from the course/page relations. */
type Page = {id:string;title?:string;snippet?:string};
type Catalog = {id?:string;pages:Page[];pageSources?:Record<string,string[]>};
export function frozenPageCatalog():Catalog|undefined {
 const value=Reflect.get(globalThis,'__SHUKU_PAGE_CATALOG__') as Catalog|undefined;
 return value&&Array.isArray(value.pages)?value:undefined;
}
export function arrangeCoursePages<T extends {id:string}>(source:T[],strict=false,courseId?:string,onMissing?:(page:Page)=>T):T[]{
 const catalog=frozenPageCatalog();if(!catalog)return source;
 if(courseId&&catalog.id&&courseId!==catalog.id)return source;
 const registered=new Map(source.map(page=>[page.id,page]));
 for(const [id,sources] of Object.entries(catalog.pageSources||{})){
  const implementation=sources.map(source=>registered.get(source)).find(Boolean);
  if(implementation&&!registered.has(id))registered.set(id,implementation);
 }
 if(!catalog.pages.some(page=>registered.has(page.id))){
  if(strict&&courseId&&catalog.pages.length){if(!onMissing)throw new Error('Course pages have no registered renderers');}
  else return source; // An embedded, independent lesson.
 }
 return catalog.pages.flatMap(page=>{
  const implementation=registered.get(page.id);
  if(!implementation){if(onMissing)return [onMissing(page)];if(strict)throw new Error('Course page has no registered renderer: '+page.id);return [];}
  return [{...implementation,id:page.id,...(typeof page.title==='string'?{title:page.title}:{})}];
 });
}
