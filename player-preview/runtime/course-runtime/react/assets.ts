type AssetContext = typeof globalThis & {
  __SHUKU_COURSE_ID__?: string;
  __SHUKU_ASSET_BASE__?: string;
  __SHUKU_COURSE_ASSET_DIRECTORY__?: string;
  __SHUKU_ASSET_URLS__?: Record<string, string>;
  __SHUKU_OFFLINE_ASSET__?: (key: string) => string;
};

const missingImages = new Set<string>();

/** Fail at the image consumer so a missing file cannot abort React rendering. */
function missingImageUrl(key:string):string {
  if(!missingImages.has(key)){
    missingImages.add(key);
    console.warn('Image absent from this published version: '+key);
  }
  // Deliberately undecodable: img.onerror / Image.decode() retain their normal
  // failure behavior. Never guess an OSS URL or fall back to a different version.
  return 'data:application/x-shuku-missing-image,'+encodeURIComponent(key);
}

/** Directory URLs serve legacy HTML/game trees through the current artifact manifest. */
export function courseAssetDirectory(relativePath:string):string {
  return assetDirectory((globalThis as AssetContext).__SHUKU_COURSE_ID__,relativePath);
}

function assetDirectory(id:string|undefined,relativePath:string):string {
  const context=globalThis as AssetContext;
  if(!id||!relativePath||/[\\:?#]/.test(relativePath)||relativePath.split('/').some(part=>!part||part==='.'||part==='..'))throw new Error('Missing or invalid course asset directory');
  const base=(id===context.__SHUKU_COURSE_ID__?context.__SHUKU_COURSE_ASSET_DIRECTORY__:null)||(context.__SHUKU_ASSET_BASE__?context.__SHUKU_ASSET_BASE__.replace(/\/+$/,'')+'/'+encodeURIComponent(id):null);
  if(!base)throw new Error('Missing course asset directory context');
  return base.replace(/\/+$/,'')+'/'+relativePath.split('/').map(encodeURIComponent).join('/')+'/';
}

/** Paths are relative to the course assets directory. Published URLs are platform-owned. */
export function moduleAssetUrl(relativePath: string): string {
  if(arguments.length!==1)throw new Error('moduleAssetUrl requires one course-local path');
  return assetUrl((globalThis as AssetContext).__SHUKU_COURSE_ID__,relativePath);
}

function assetUrl(moduleId:string|undefined,relative:string):string {
  const context=globalThis as AssetContext;
  if(!moduleId || !/^[a-zA-Z0-9_-]+$/.test(moduleId))throw new Error('Missing course asset context');
  if(!relative || relative.includes('\\') || /[:?#]/.test(relative) || relative.startsWith('/') || relative.split('/').some(part=>!part||part==='.'||part==='..')){
    throw new Error('Use a relative path inside the course assets directory: '+relative);
  }
  const key='assets/'+moduleId+'/'+relative;
  if(context.__SHUKU_OFFLINE_ASSET__)return context.__SHUKU_OFFLINE_ASSET__(key);
  if(context.__SHUKU_ASSET_URLS__){
    const url=context.__SHUKU_ASSET_URLS__[key];
    if(!url){
      if(/\.(?:png|jpe?g|webp|avif|gif|bmp|tiff?|svg|ico)$/i.test(relative))return missingImageUrl(key);
      throw new Error('Asset absent from this published version: '+relative);
    }
    return url;
  }
  if(!context.__SHUKU_ASSET_BASE__)throw new Error('Missing course asset base');
  const base=context.__SHUKU_ASSET_BASE__.replace(/\/+$/,'');
  return base+'/'+encodeURIComponent(moduleId)+'/'+relative.split('/').map(encodeURIComponent).join('/');
}

/** Compiler binding: retain the referenced course's canonical asset identity. */
export function courseAssetReferences(courseId:string) {
  return {
    moduleAssetUrl(relativePath:string):string {
      if(arguments.length!==1)throw new Error('moduleAssetUrl requires one course-local path');
      return assetUrl(courseId,relativePath);
    },
    courseAssetDirectory(relativePath:string):string {return assetDirectory(courseId,relativePath);},
  };
}
