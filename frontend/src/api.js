const BASE=import.meta.env.VITE_API_BASE_URL||'http://localhost:8000';

export async function api(path,options={}){
  const headers=new Headers(options.headers||{});
  if(!(options.body instanceof FormData)&&options.body)headers.set('Content-Type','application/json');
  const response=await fetch(`${BASE}${path}`,{...options,headers});
  if(!response.ok){
    const body=await response.json().catch(()=>({detail:response.statusText}));
    const detail=body?.detail;
    const message=typeof detail==='string'
      ? detail
      : (detail?.message||detail?.detail||detail?.code||`Request failed (${response.status})`);
    const error=new Error(message);
    error.status=response.status;
    error.code=typeof detail==='object'&&detail!==null?detail.code:undefined;
    error.details=detail;
    throw error;
  }
  return response;
}