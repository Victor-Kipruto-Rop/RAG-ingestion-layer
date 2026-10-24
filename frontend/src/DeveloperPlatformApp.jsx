import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity, ArrowDownRight, ArrowRight, ArrowUpRight, BookOpen, Boxes, BellRing, Check, CheckCircle2,
  ChevronDown, CircleHelp, Clipboard, Code2, Copy, ExternalLink, Eye, EyeOff, FileCode2,
  FlaskConical, Globe2, Github, KeyRound, Layers3, LockKeyhole, LogOut, Menu, Plus, Radio,
  RefreshCw, Rocket, Search, ShieldCheck, Terminal, Trash2, UserRound, Webhook, X, Zap
} from 'lucide-react';
import { API_BASE, api, setCsrfToken } from './api.js';
import ToastPopup from './ToastPopup.jsx';

const EVENTS = ['api_key.created','api_key.revoked','api_key.rotated','webhook.test','registry.lookup.completed','data.source.updated','production_access.requested','production_access.reviewed'];
const LANGS = ['cURL','JavaScript','Python','PHP','Go','Java','Ruby','C#'];
const LANG_CODE = {
  cURL: 'curl --request GET \\\n  --url "$PESAGUARD_BASE_URL/api/v1/registry/search?q=example" \\\n  --header "X-API-Key: $PESAGUARD_API_KEY" \\\n  --header "Accept: application/json"',
  JavaScript: 'const response = await fetch(`${process.env.PESAGUARD_BASE_URL}/api/v1/registry/search?q=example`, {\n  headers: { \'X-API-Key\': process.env.PESAGUARD_API_KEY, Accept: \'application/json\' }\n});\nif (!response.ok) throw new Error(`PesaGuard API failed: ${response.status}`);\nconst result = await response.json();',
  Python: 'import os\nimport requests\n\nresponse = requests.get(\n    f"{os.environ[\'PESAGUARD_BASE_URL\']}/api/v1/registry/search",\n    params={"q": "example"},\n    headers={"X-API-Key": os.environ["PESAGUARD_API_KEY"]},\n    timeout=10,\n)\nresponse.raise_for_status()\nprint(response.json())',
  PHP: '$response = Http::timeout(10)->withHeaders([\n  \'X-API-Key\' => config(\'services.pesaguard.key\'),\n])->get(config(\'services.pesaguard.base_url\').\'/api/v1/registry/search\', [\'q\' => \'example\']);\n$response->throw();',
  Go: 'req, _ := http.NewRequest(http.MethodGet, baseURL+"/api/v1/registry/search?q=example", nil)\nreq.Header.Set("X-API-Key", os.Getenv("PESAGUARD_API_KEY"))\nresp, err := http.DefaultClient.Do(req)\nif err != nil { return err }\ndefer resp.Body.Close()',
  Java: 'HttpRequest request = HttpRequest.newBuilder(URI.create(baseUrl + "/api/v1/registry/search?q=example"))\n    .header("X-API-Key", System.getenv("PESAGUARD_API_KEY"))\n    .GET().build();\nHttpResponse<String> response = HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofString());',
  Ruby: 'response = Net::HTTP.start(uri.host, uri.port, use_ssl: true, open_timeout: 5, read_timeout: 10) do |http|\n  request = Net::HTTP::Get.new(uri)\n  request["X-API-Key"] = ENV.fetch("PESAGUARD_API_KEY")\n  http.request(request)\nend',
  'C#': 'using var request = new HttpRequestMessage(HttpMethod.Get, $"{baseUrl}/api/v1/registry/search?q=example");\nrequest.Headers.Add("X-API-Key", Environment.GetEnvironmentVariable("PESAGUARD_API_KEY"));\nusing var response = await httpClient.SendAsync(request);\nresponse.EnsureSuccessStatusCode();'
};
const NAV = [
  {group:'BUILD',items:[['Overview',Rocket],['Projects',Layers3],['API Keys',KeyRound],['Webhooks',Webhook],['API Explorer',FlaskConical],['SDKs & Testing',Code2]]},
  {group:'SHIP',items:[['Production access',ShieldCheck],['Documentation',BookOpen],['Notifications',BellRing],['Account',UserRound],['Sessions',ShieldCheck]]}
];
async function readJson(path, options={}) { const r=await api(path,options); return r.status===204 ? null : r.json(); }
function CodeBlock({children}) { return <pre className="dp-code"><code>{children}</code></pre>; }
function Metric({label,value,detail,icon:Icon}) { return <div className="dp-metric"><span className="dp-metric-icon"><Icon size={17}/></span><div><small>{label}</small><strong>{value}</strong><span>{detail}</span></div></div>; }
function PageHeading({eyebrow,title,description,actions}) { return <div className="dp-page-heading"><div><div className="dp-eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{actions && <div className="dp-heading-actions">{actions}</div>}</div>; }

export default function DeveloperPlatformApp() {
  const [page,setPage] = useState('Overview');
  const [authMode,setAuthMode] = useState('landing');
  const [authConfig,setAuthConfig] = useState({signup_enabled:false,password_reset_enabled:false,password_min_length:12,social_auth_enabled:false});
  const [user,setUser] = useState(null);
  const [workspace,setWorkspace] = useState(null);
  const [csrf,setCsrf] = useState('');
  const [accessToken,setAccessToken] = useState('');
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [notice,setNotice] = useState('');
  const [mobileNav,setMobileNav] = useState(false);
  const [projects,setProjects] = useState([]);
  const [sessions,setSessions] = useState([]);
  const [notifications,setNotifications] = useState([]);
  const [keys,setKeys] = useState([]);
  const [webhooks,setWebhooks] = useState([]);
  const [deliveries,setDeliveries] = useState([]);
  const [selectedHook,setSelectedHook] = useState('');
  const [productionRequests,setProductionRequests] = useState([]);
  const [profile,setProfile] = useState({display_name:'',workspace_name:''});
  const [baseUrls,setBaseUrls] = useState({sandbox:'https://sandbox-api.pesaguard.co.ke',production:'https://api.pesaguard.co.ke'});
  const [keyForm,setKeyForm] = useState({name:'Website integration',environment:'sandbox',expires_in_days:90,scopes:['registry:read']});
  const [newSecret,setNewSecret] = useState('');
  const [showSecret,setShowSecret] = useState(false);
  const [hookForm,setHookForm] = useState({name:'Production events',endpoint_url:'',events:['webhook.test','registry.lookup.completed']});
  const [lang,setLang] = useState('JavaScript');
  const [tester,setTester] = useState({environment:'sandbox',path:'/api/v1/registry/search?q=example',method:'GET',apiKey:'',body:'{}'});
  const [testResult,setTestResult] = useState(null);
  const [search,setSearch] = useState('');
  const [apiDocs,setApiDocs] = useState(null);
  const authed = Boolean(user && accessToken);

  const syncSession = useCallback(async () => {
    try {
      const result = await readJson('/api/v1/developer/auth/session');
      setCsrfToken(result.csrf_token); setCsrf(result.csrf_token || '');
      setUser(result.user); setWorkspace(result.workspace); setAccessToken(result.access_token || '');
      setProfile({display_name:result.user?.display_name || '',workspace_name:result.workspace?.name || ''});
      return true;
    } catch { setUser(null); setWorkspace(null); setAccessToken(''); setCsrf(''); setCsrfToken(''); return false; }
  }, []);
  useEffect(() => {
    let live=true;
    readJson('/api/v1/developer/auth/config').then(v=>{if(live)setAuthConfig(v);}).catch(()=>{});
    readJson('/api/v1/developer/platform/config').then(v=>{if(live){setBaseUrls({sandbox:v.sandbox_base_url,production:v.production_base_url});setApiDocs(v.api_docs || null);}}).catch(()=>{});
    syncSession();
    return ()=>{live=false;};
  },[syncSession]);

  const refreshData = useCallback(async () => {
    if (!authed) return;
    setBusy(true); setError('');
    try {
      // Refresh the short-lived control-plane token from the persisted HttpOnly session.
      const fresh = await readJson('/api/v1/developer/auth/session');
      setCsrfToken(fresh.csrf_token || ''); setCsrf(fresh.csrf_token || '');
      setAccessToken(fresh.access_token || '');
      setUser(fresh.user); setWorkspace(fresh.workspace);
      const [p,k,w,r,s,n] = await Promise.all([
        readJson('/api/v1/developer/projects'), readJson('/api/v1/keys',{headers:{Authorization:`Bearer ${fresh.access_token}`}}),
        readJson('/api/v1/developer/webhooks'), readJson('/api/v1/developer/production-access/requests'), readJson('/api/v1/developer/sessions'), readJson('/api/v1/developer/notifications')
      ]);
      setProjects(p.items || []); setKeys(k.items || []); setWebhooks(w.items || []); setProductionRequests(r.items || []); setSessions((s.items || []).filter(x=>!x.revoked)); setNotifications(n.items || []);
    } catch(e) { setError(e.message || 'Could not load developer workspace data.'); }
    finally { setBusy(false); }
  },[authed]);
  useEffect(()=>{if(authed)refreshData();},[authed,refreshData]);

  const finishAuth = result => {
    setCsrfToken(result.csrf_token || ''); setCsrf(result.csrf_token || '');
    setUser(result.user); setWorkspace(result.workspace); setAccessToken(result.access_token || '');
    setProfile({display_name:result.user?.display_name || '',workspace_name:result.workspace?.name || ''});
    setAuthMode('login'); setError(''); setNotice('You are signed in to your developer workspace.'); setPage('Overview');
  };
  const signOut = async () => {
    try { await readJson('/api/v1/developer/auth/logout',{method:'POST'}); } catch {}
    setUser(null);setWorkspace(null);setAccessToken('');setCsrf('');setCsrfToken('');setPage('Overview');setNotice('You have signed out.');setAuthMode('login');
  };
  const makeKey = async e => {
    e.preventDefault();setBusy(true);setError('');setNotice('');setNewSecret('');
    try {
      const result=await readJson('/api/v1/keys',{method:'POST',headers:{Authorization:`Bearer ${accessToken}`},body:JSON.stringify({...keyForm,expires_in_days:Number(keyForm.expires_in_days) || null})});
      setNewSecret(result.secret);setShowSecret(true);setNotice('API key created. Copy it now; the full secret will not be shown again.');await refreshData();
    } catch(e){setError(e.message || 'API key could not be created.');} finally{setBusy(false);}
  };
  const rotateKey = async item => {
    if(!window.confirm(`Rotate ${item.name}? The current key is revoked when rotation succeeds.`))return;
    setBusy(true);setError('');
    try{const r=await readJson(`/api/v1/keys/${encodeURIComponent(item.id)}/rotate`,{method:'POST',headers:{Authorization:`Bearer ${accessToken}`}});setNewSecret(r.secret);setShowSecret(true);setNotice('Key rotated. Store the new secret securely.');await refreshData();}
    catch(e){setError(e.message || 'Key rotation failed.');}finally{setBusy(false);}
  };
  const revokeKey = async item => {
    if(!window.confirm(`Revoke ${item.name}? Applications using it will stop authenticating.`))return;
    setBusy(true);setError('');
    try{await readJson(`/api/v1/keys/${encodeURIComponent(item.id)}`,{method:'DELETE',headers:{Authorization:`Bearer ${accessToken}`}});setNotice('API key revoked.');await refreshData();}
    catch(e){setError(e.message || 'Could not revoke key.');}finally{setBusy(false);}
  };
  const requestProduction = async e => {
    e.preventDefault();setBusy(true);setError('');setNotice('');
    try{await readJson('/api/v1/developer/production-access/request',{method:'POST',body:JSON.stringify({use_case:e.currentTarget.use_case.value,expected_volume:e.currentTarget.expected_volume.value})});setNotice('Production access request submitted. Production keys remain disabled until approval and organization verification.');await refreshData();}
    catch(e){setError(e.message || 'Could not submit production access request.');}finally{setBusy(false);}
  };
  const createWebhook = async e => {
    e.preventDefault();setBusy(true);setError('');setNotice('');
    try{const r=await readJson('/api/v1/developer/webhooks',{method:'POST',body:JSON.stringify(hookForm)});setNotice('Webhook created. Copy its signing secret now: '+r.signing_secret);setWebhooks(prev=>[r.item,...prev]);setHookForm(v=>({...v,endpoint_url:''}));}
    catch(e){setError(e.message || 'Webhook could not be created.');}finally{setBusy(false);}
  };
  const deleteWebhook = async hook => {
    if(!window.confirm(`Delete webhook ${hook.name}?`))return;
    try{await readJson(`/api/v1/developer/webhooks/${encodeURIComponent(hook.id)}`,{method:'DELETE'});setWebhooks(prev=>prev.filter(x=>x.id!==hook.id));setNotice('Webhook deleted.');}
    catch(e){setError(e.message || 'Could not delete webhook.');}
  };
  const testWebhook = async hook => {
    setBusy(true);setError('');
    try{await readJson(`/api/v1/developer/webhooks/${encodeURIComponent(hook.id)}/test`,{method:'POST'});setSelectedHook(hook.id);const r=await readJson(`/api/v1/developer/webhooks/${encodeURIComponent(hook.id)}/deliveries`);setDeliveries(r.items || []);setNotice('Test delivery queued. Refresh delivery history in a moment to see the result.');}
    catch(e){setError(e.message || 'Webhook test could not be queued.');}finally{setBusy(false);}
  };
  const loadDeliveries = async hook => {
    setSelectedHook(hook.id);
    try{const r=await readJson(`/api/v1/developer/webhooks/${encodeURIComponent(hook.id)}/deliveries`);setDeliveries(r.items || []);}
    catch(e){setError(e.message || 'Delivery history unavailable.');}
  };
  const revokeSession = async item => {
    if(!window.confirm(item.current?'Sign out and revoke this session?':'Revoke this session?'))return;
    setBusy(true);setError('');
    if(item.current){await signOut();return;}
    try{await readJson(`/api/v1/developer/sessions/${encodeURIComponent(item.id)}`,{method:'DELETE'});setSessions(v=>v.filter(x=>x.id!==item.id));setNotice('Session revoked.');}
    catch(e){setError(e.message||'Could not revoke session.');}finally{setBusy(false);}
  };
  const saveProfile = async e => {
    e.preventDefault();setBusy(true);setError('');
    try{const r=await readJson('/api/v1/developer/profile',{method:'PUT',body:JSON.stringify(profile)});setUser(v=>({...v,display_name:r.display_name}));setWorkspace(v=>({...v,name:r.workspace_name}));setProfile(v=>({...v,display_name:r.display_name,workspace_name:r.workspace_name}));setNotice('Profile saved.');}
    catch(e){setError(e.message || 'Profile could not be saved.');}finally{setBusy(false);}
  };
  const runTest = async e => {
    e.preventDefault();setTestResult(null);
    const base=tester.environment==='sandbox'?baseUrls.sandbox:baseUrls.production;
    const url=base.replace(/\/$/,'')+(tester.path.startsWith('/')?tester.path:'/'+tester.path);
    if(tester.environment!=='sandbox'){
      setTestResult({ok:false,status:'BLOCKED',ms:0,body:'Production credentials are not accepted by the browser-based workbench. Run production checks from your trusted backend using the server-side SDK.',url});
      return;
    }
    setBusy(true);
    const started=performance.now();
    try{
      const response=await fetch(url,{method:tester.method,headers:{'X-API-Key':tester.apiKey,'Accept':'application/json',...(tester.method==='POST'?{'Content-Type':'application/json'}:{})},...(tester.method==='POST'?{body:tester.body}:{}),signal:AbortSignal.timeout(10000)});
      const body=await response.text();setTestResult({ok:response.ok,status:response.status,ms:Math.round(performance.now()-started),body:body.slice(0,12000),url});
    }catch(e){setTestResult({ok:false,status:'NETWORK_ERROR',ms:Math.round(performance.now()-started),body:e.message || 'Request failed or CORS blocked this browser request.',url});}
    finally{setBusy(false);}
  };
  const copy = async value => {try{await navigator.clipboard.writeText(value);setNotice('Copied to clipboard.');}catch{setError('Clipboard unavailable; select and copy the text manually.');}};
  const visibleKeys = useMemo(()=>keys.filter(k=>`${k.name} ${k.environment} ${k.key_prefix} ${k.status}`.toLowerCase().includes(search.toLowerCase())),[keys,search]);

  if(!authed) return <>{authMode==='landing' ? <PublicHomePage setMode={setAuthMode} config={authConfig}/> : <AuthScreen mode={authMode} setMode={setAuthMode} config={authConfig} onAuthenticated={finishAuth} busy={busy} error={error} setError={setError}/>}</>;

  const activeTitle=page;
  return <div className="dp-shell">
    <aside className={`dp-sidebar ${mobileNav?'is-open':''}`}>
      <a className="dp-brand" href="#" onClick={e=>{e.preventDefault();setPage('Overview')}}><span className="dp-brand-mark"><img src="/pesaguard-mark.svg" alt=""/></span><span><strong>PesaGuard</strong><small>DEVELOPER PLATFORM</small></span></a>
      <div className="dp-workspace-pill"><span className="dp-live-dot"/> {workspace?.name || 'Developer workspace'} <ChevronDown size={14}/></div>
      <nav className="dp-nav">{NAV.map(group=><div key={group.group}><div className="dp-nav-group">{group.group}</div>{group.items.map(([name,Icon])=><button key={name} className={page===name?'active':''} onClick={()=>{setPage(name);setMobileNav(false);setError('');setNotice('');}}><Icon size={17}/><span>{name}</span>{name==='Webhooks'&&webhooks.length>0&&<small>{webhooks.length}</small>}</button>)}</div>)}</nav>
      <div className="dp-sidebar-bottom"><div className="dp-env-pills"><span>Sandbox</span><span>Live access gated</span></div><button onClick={()=>setPage('Account')}><UserRound size={16}/>{user.display_name}</button><button onClick={signOut}><LogOut size={16}/> Sign out</button><a href="/internal" className="dp-internal-link">Internal operations <ArrowUpRight size={14}/></a></div>
    </aside>
    <main className="dp-main">
      <header className="dp-topbar"><button className="dp-mobile-menu" onClick={()=>setMobileNav(v=>!v)} aria-label="Toggle navigation"><Menu size={20}/></button><div className="dp-breadcrumb"><span>Developer workspace</span><ArrowRight size={14}/><strong>{activeTitle}</strong></div><div className="dp-top-actions"><span className="dp-status-dot"/> API services <button onClick={refreshData} disabled={busy} aria-label="Refresh workspace"><RefreshCw size={16}/></button><button className="dp-avatar" onClick={()=>setPage('Account')} aria-label="Account settings">{(user.display_name||user.email||'D').slice(0,1).toUpperCase()}</button></div></header>
      <div className="dp-content">
        {page==='Overview'&&<OverviewPage workspace={workspace} projects={projects} keys={keys} webhooks={webhooks} baseUrls={baseUrls} setPage={setPage} refreshData={refreshData}/>}
        {page==='Projects'&&<ProjectsPage projects={projects} workspace={workspace}/>}
        {page==='API Keys'&&<ApiKeysPage keys={visibleKeys} allKeys={keys} search={search} setSearch={setSearch} form={keyForm} setForm={setKeyForm} makeKey={makeKey} rotateKey={rotateKey} revokeKey={revokeKey} busy={busy} workspace={workspace} newSecret={newSecret} showSecret={showSecret} setShowSecret={setShowSecret} copy={copy} baseUrls={baseUrls} productionRequests={productionRequests} setPage={setPage}/>}
        {page==='Webhooks'&&<WebhooksPage items={webhooks} form={hookForm} setForm={setHookForm} create={createWebhook} remove={deleteWebhook} test={testWebhook} deliveries={deliveries} selectedHook={selectedHook} loadDeliveries={loadDeliveries} busy={busy}/>}
        {page==='API Explorer'&&<ApiExplorerPage tester={tester} setTester={setTester} runTest={runTest} result={testResult} busy={busy} baseUrls={baseUrls}/>}
        {page==='SDKs & Testing'&&<SdkPage lang={lang} setLang={setLang} copy={copy} baseUrls={baseUrls}/>}
        {page==='Production access'&&<ProductionAccessPage workspace={workspace} requests={productionRequests} submit={requestProduction} busy={busy} baseUrls={baseUrls}/>}
        {page==='Documentation'&&<DeveloperDocsPage baseUrls={baseUrls} apiDocs={apiDocs} setPage={setPage}/>}
        {page==='Account'&&<AccountPage user={user} workspace={workspace} profile={profile} setProfile={setProfile} saveProfile={saveProfile} busy={busy}/>}
        {page==='Sessions'&&<SessionsPage items={sessions} revoke={revokeSession} busy={busy}/>}
        {page==='Notifications'&&<DeveloperNotificationsPage items={notifications} refresh={refreshData} busy={busy}/>} 
      </div>
      <footer className="dp-footer"><span>© {new Date().getFullYear()} PesaGuard Developer Platform</span><span><span className="dp-status-dot"/> Service state is read from the API</span><a href={`${API_BASE}/health`} target="_blank" rel="noreferrer">API health <ExternalLink size={13}/></a></footer>
    </main>
    <ToastPopup kind="error" message={error} onClose={()=>setError('')}/><ToastPopup kind={/warning|blocked|not approved|not configured|cannot|unavailable/i.test(notice) ? 'warning' : 'success'} message={notice} onClose={()=>setNotice('')}/>
  </div>;
}

function AlertCircleIcon(){return <CircleHelp size={17}/>;}
function AuthScreen({mode,setMode,config,onAuthenticated,busy,error,setError}){
  const [stage,setStage]=useState(mode==='reset'?'request':'details');
  const [email,setEmail]=useState('');const [displayName,setDisplayName]=useState('');const [workspaceName,setWorkspaceName]=useState('');
  const [password,setPassword]=useState('');const [confirm,setConfirm]=useState('');const [code,setCode]=useState('');const [localBusy,setLocalBusy]=useState(false);const [localError,setLocalError]=useState('');const [message,setMessage]=useState('');
  const reset=mode==='reset';const loading=busy||localBusy;
  const submit=async e=>{e.preventDefault();setLocalError('');setError('');setMessage('');setLocalBusy(true);
    try{
      if(!reset&&stage==='details'){
        if(password!==confirm)throw new Error('Passwords do not match.');
        const r=await readJson('/api/v1/developer/auth/signup/request-otp',{method:'POST',body:JSON.stringify({email,display_name:displayName,workspace_name:workspaceName,password})});
        setMessage(r.message);setStage('verify');
      }else if(!reset&&stage==='verify'){
        const r=await readJson('/api/v1/developer/auth/signup/verify-otp',{method:'POST',body:JSON.stringify({email,code})});onAuthenticated(r);
      }else if(reset&&stage==='request'){
        const r=await readJson('/api/v1/developer/auth/password-reset/request-otp',{method:'POST',body:JSON.stringify({email})});setMessage(r.message);setStage('confirm');
      }else if(reset&&stage==='confirm'){
        if(password!==confirm)throw new Error('Passwords do not match.');
        const r=await readJson('/api/v1/developer/auth/password-reset/confirm',{method:'POST',body:JSON.stringify({email,code,new_password:password})});setMessage(r.message);setMode('login');setStage('details');
      }else{
        const r=await readJson('/api/v1/developer/auth/login',{method:'POST',body:JSON.stringify({email,password})});onAuthenticated(r);
      }
    }catch(err){setLocalError(err.message||'Authentication failed.');}finally{setLocalBusy(false);}
  };
  const resendCode=async()=>{
    setLocalError('');setError('');setMessage('');setLocalBusy(true);
    try{
      if(reset){
        const r=await readJson('/api/v1/developer/auth/password-reset/request-otp',{method:'POST',body:JSON.stringify({email})});
        setMessage(r.message);
      }else{
        const r=await readJson('/api/v1/developer/auth/signup/request-otp',{method:'POST',body:JSON.stringify({email,display_name:displayName,workspace_name:workspaceName,password})});
        setMessage(r.message);
      }
    }catch(err){setLocalError(err.message||'A new verification code could not be sent.');}
    finally{setLocalBusy(false);}
  };
  const title=reset?(stage==='request'?'Recover your account':'Verify reset code'):mode==='signup'?(stage==='details'?'Build your developer workspace':'Verify your email'):'Welcome back, developer';
  return <><div className="dp-auth-shell">
    <div className="dp-auth-visual"><div className="dp-auth-nav"><a className="dp-brand" href="#"><span className="dp-brand-mark"><img src="/pesaguard-mark.svg" alt=""/></span><span><strong>PesaGuard</strong><small>DEVELOPER PLATFORM</small></span></a><span className="dp-open-badge"><i/> API PLATFORM</span></div><WindHero compact/><div className="dp-auth-pitch"><div className="dp-eyebrow">INTEGRATE WITH CONFIDENCE</div><h1>Build once.<br/><em>Move money data</em><br/>with clarity.</h1><p>Environment-isolated keys, signed webhooks, clear contracts and observable API behavior for real integrations.</p><div className="dp-trust-row"><span><ShieldCheck size={15}/> Least privilege</span><span><Zap size={15}/> Fast feedback</span><span><Radio size={15}/> Event-driven</span></div></div><div className="dp-auth-foot">Built for developers shipping production integrations.</div></div>
    <div className="dp-auth-form-wrap"><div className="dp-auth-form">
      <div className="dp-auth-mobile-brand"><span className="dp-brand-mark"><img src="/pesaguard-mark.svg" alt=""/></span><span><strong>PesaGuard</strong><small>DEVELOPER PLATFORM</small></span></div>
      <div className="dp-auth-step">{reset?'ACCOUNT RECOVERY':mode==='signup'?'CREATE DEVELOPER ACCOUNT':'DEVELOPER SIGN IN'}</div><h2>{title}</h2><p className="dp-auth-subtitle">{reset?'We will send a time-limited code if this account is eligible.':mode==='signup'?'Create a developer account for your website, application or data platform.':'Sign in to manage API keys, webhooks, projects and production access.'}</p>
      <form onSubmit={submit} className="dp-form">
        {!reset&&mode==='signup'&&stage==='details'&&<><label>Full name<input autoComplete="name" value={displayName} onChange={e=>setDisplayName(e.target.value)} minLength={2} maxLength={120} required placeholder="Your name"/></label><label>Workspace name<input value={workspaceName} onChange={e=>setWorkspaceName(e.target.value)} minLength={2} maxLength={160} required placeholder="Company or project"/></label></>}
        <label>Email address<input type="email" autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} required readOnly={stage==='verify'||stage==='confirm'} placeholder="you@company.com"/></label>
        {(stage==='verify'||stage==='confirm')&&<label>6-digit email code<input inputMode="numeric" autoComplete="one-time-code" value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,'').slice(0,6))} pattern="[0-9]{6}" minLength={6} required placeholder="000000"/></label>}
        {(mode==='login'||stage==='details'&&mode==='signup'||reset&&stage==='confirm')&&<><label>{reset?'New password':'Password'}<input type="password" autoComplete={mode==='login'?'current-password':'new-password'} value={password} onChange={e=>setPassword(e.target.value)} minLength={mode==='login'?1:(config.password_min_length||12)} required placeholder={mode==='login'?'Your password':'At least 12 characters'}/></label>{(mode==='signup'||reset)&&<label>Confirm password<input type="password" autoComplete="new-password" value={confirm} onChange={e=>setConfirm(e.target.value)} minLength={config.password_min_length||12} required placeholder="Repeat password"/></label>}</>}
        <button className="dp-button primary wide" disabled={loading||(!reset&&mode==='signup'&&!config.signup_enabled)||(reset&&!config.password_reset_enabled)}>{loading?'Please wait…':reset?'Continue securely':mode==='signup'?(stage==='details'?'Send verification code':'Verify email and create account'):'Sign in'}<ArrowRight size={16}/></button>
      </form>
      {(config.google_enabled||config.github_enabled)&&<div className="dp-social-auth"><div className="dp-social-divider"><span>or continue with</span></div><div className="dp-social-buttons">{config.google_enabled&&<button type="button" onClick={()=>window.location.assign(`${API_BASE}/api/v1/developer/auth/oauth/google/start`)}><Globe2 size={16}/> Google</button>}{config.github_enabled&&<button type="button" onClick={()=>window.location.assign(`${API_BASE}/api/v1/developer/auth/oauth/github/start`)}><Github size={16}/> GitHub</button>}</div></div>}
      <div className="dp-auth-links">{mode==='login'&&!reset&&<><button onClick={()=>{setMode('reset');setStage('request');setLocalError('');}}>Forgot password?</button><span>New here? <button onClick={()=>{setMode('signup');setStage('details');setLocalError('');}}>Create an account</button></span></>}{(mode==='signup'&&stage==='verify'||reset&&stage==='confirm')&&<button disabled={loading||(!reset&&!config.signup_enabled)||(reset&&!config.password_reset_enabled)} onClick={resendCode}>Resend code</button>}{(mode==='signup'||reset)&&<button onClick={()=>{setMode('login');setStage('details');setLocalError('');setMessage('');}}>Back to sign in</button>}</div>
      {mode==='signup'&&!config.signup_enabled&&<div className="dp-config-warning"><LockKeyhole size={16}/><span>Registration is disabled until email delivery, OTP pepper and developer signing/session secrets are configured on the backend.</span></div>}
      <div className="dp-auth-security"><ShieldCheck size={16}/><span>HttpOnly session cookie · CSRF protection · one-time email codes · session revocation</span></div>
    </div></div>
  </div><ToastPopup kind="error" message={localError || error} onClose={()=>{setLocalError('');setError('');}}/><ToastPopup kind={/warning|blocked|not approved|not configured|unavailable/i.test(message) ? 'warning' : 'success'} message={message} onClose={()=>setMessage('')}/></>;
}
function WindHero({compact=false}){return <div className={compact?'dp-wind-scene compact':'dp-wind-scene'} aria-hidden="true"><div className="dp-wind-orb"/><div className="dp-wind-ring ring-one"/><div className="dp-wind-ring ring-two"/><div className="dp-wind-ring ring-three"/><svg viewBox="0 0 760 420" preserveAspectRatio="xMidYMid meet"><defs><linearGradient id="wind-gradient" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#b7ffe0" stopOpacity=".8"/><stop offset=".5" stopColor="#34d399" stopOpacity=".15"/><stop offset="1" stopColor="#5eead4" stopOpacity=".65"/></linearGradient></defs>{Array.from({length:19},(_,i)=><path key={i} d={`M -20 ${34+i*19} C 110 ${-20+i*20}, 205 ${120+i*12}, 360 ${58+i*17} S 590 ${25+i*18}, 790 ${70+i*18}`} fill="none" stroke="url(#wind-gradient)" strokeWidth={i%4===0?2:1} strokeOpacity={.22+(i%5)*.08}/>)}</svg><div className="dp-orbit-chip chip-a"><Code2 size={14}/> SDKs</div><div className="dp-orbit-chip chip-b"><Webhook size={14}/> Webhooks</div><div className="dp-orbit-chip chip-c"><ShieldCheck size={14}/> Scoped access</div></div>}

function OverviewPage({workspace,projects,keys,webhooks,baseUrls,setPage,refreshData}){
 const sandbox=keys.filter(k=>k.environment==='sandbox'&&k.status==='active').length;const live=keys.filter(k=>k.environment==='production'&&k.status==='active').length;
 return <><section className="dp-hero"><div className="dp-hero-copy"><div className="dp-eyebrow"><span className="dp-live-dot"/> DEVELOPER CONTROL PLANE</div><h1>Your integration layer,<br/><em>engineered to ship.</em></h1><p>Provision environment-isolated credentials, test real requests, subscribe to signed events and move from sandbox to production through an explicit review gate.</p><div className="dp-hero-actions"><button className="dp-button primary" onClick={()=>setPage('API Keys')}><KeyRound size={16}/> Create sandbox key <ArrowRight size={15}/></button><button className="dp-button ghost" onClick={()=>setPage('Documentation')}>Read the docs <ArrowUpRight size={15}/></button></div><div className="dp-hero-note"><ShieldCheck size={15}/> Production keys require approval. Sandbox keys never authenticate against the live API.</div></div><WindHero/><div className="dp-hero-gridlines"/></section>
 <div className="dp-section-title"><div><span className="dp-eyebrow">WORKSPACE HEALTH</span><h2>Integration overview</h2></div><button className="dp-button quiet" onClick={refreshData}><RefreshCw size={14}/> Refresh data</button></div>
 <div className="dp-metric-grid"><Metric label="Projects" value={projects.length} detail="Persisted workspace projects" icon={Layers3}/><Metric label="Active sandbox keys" value={sandbox} detail="Restricted to sandbox host" icon={FlaskConical}/><Metric label="Active production keys" value={live} detail="Approved live credentials" icon={KeyRound}/><Metric label="Webhooks" value={webhooks.length} detail="Configured event endpoints" icon={Webhook}/></div>
 <div className="dp-two-col"><section className="dp-panel"><div className="dp-panel-head"><div><h3>Environment endpoints</h3><p>Separate hosts enforce the environment boundary.</p></div><Globe2 size={18}/></div><div className="dp-endpoint-row"><span className="dp-env-tag sandbox">SANDBOX</span><code>{baseUrls.sandbox}</code><button onClick={()=>navigator.clipboard?.writeText(baseUrls.sandbox)} aria-label="Copy sandbox URL"><Copy size={14}/></button></div><div className="dp-endpoint-row"><span className="dp-env-tag production">PRODUCTION</span><code>{baseUrls.production}</code><button onClick={()=>navigator.clipboard?.writeText(baseUrls.production)} aria-label="Copy production URL"><Copy size={14}/></button></div><p className="dp-muted-note">Use the host that matches the key prefix. A mismatch is rejected by the server; do not infer availability until your deployment is configured.</p></section>
 <section className="dp-panel"><div className="dp-panel-head"><div><h3>Next steps</h3><p>Move from first request to production readiness.</p></div><Rocket size={18}/></div><button className="dp-action-row" onClick={()=>setPage('API Explorer')}><span className="dp-action-icon"><FlaskConical size={17}/></span><span><strong>Test an API request</strong><small>Inspect status, response body and latency</small></span><ArrowRight size={16}/></button><button className="dp-action-row" onClick={()=>setPage('Webhooks')}><span className="dp-action-icon"><Webhook size={17}/></span><span><strong>Configure a webhook</strong><small>Receive signed events at your HTTPS endpoint</small></span><ArrowRight size={16}/></button><button className="dp-action-row" onClick={()=>setPage('Production access')}><span className="dp-action-icon"><ShieldCheck size={17}/></span><span><strong>Request live access</strong><small>Submit your use case and expected volume</small></span><ArrowRight size={16}/></button></section></div>
 </>;
}
function ProjectsPage({projects,workspace}){return <><PageHeading eyebrow="WORKSPACE" title="Projects" description="Projects group integrations and provide a boundary for future per-project credentials and event subscriptions."/><div className="dp-panel"><div className="dp-panel-head"><div><h3>{workspace?.name||'Developer workspace'}</h3><p>Workspace-owned project records loaded from the backend.</p></div><Layers3 size={18}/></div>{projects.length?<div className="dp-table-wrap"><table className="dp-table"><thead><tr><th>Project</th><th>Slug</th><th>Created</th><th>Status</th></tr></thead><tbody>{projects.map(p=><tr key={p.id}><td><strong>{p.name}</strong><small>{p.id}</small></td><td><code>{p.slug}</code></td><td>{new Date(p.created_at).toLocaleDateString()}</td><td><span className="dp-state good">ACTIVE</span></td></tr>)}</tbody></table></div>:<Empty title="No projects found" detail="Create an account to provision a default project."/ >}</div></>}
function ApiKeysPage({keys,allKeys,search,setSearch,form,setForm,makeKey,rotateKey,revokeKey,busy,workspace,newSecret,showSecret,setShowSecret,copy,baseUrls,productionRequests,setPage}){
 const productionAllowed=workspace?.verified===true&&workspace?.production_access_approved===true;
 return <><PageHeading eyebrow="CREDENTIALS" title="API key management" description="Create, rotate and revoke integration keys. Secrets are shown once and are never stored in browser persistence." actions={<button className="dp-button ghost" onClick={()=>setPage('Production access')}><ShieldCheck size={15}/> Request production access</button>}/>
 <div className="dp-security-banner"><ShieldCheck size={19}/><div><strong>Environment isolation is enforced by the API gateway</strong><p>Sandbox keys use <code>pg_sandbox_</code> and only authenticate on the sandbox base URL. Production keys use <code>pg_live_</code> and require a verified workspace plus explicit production approval.</p></div></div>
 {newSecret&&<div className="dp-secret-panel"><div><div className="dp-eyebrow">ONE-TIME SECRET</div><h3>Copy your API key now</h3><p>It cannot be retrieved again. Store it in your server-side secret manager, not frontend JavaScript.</p><code>{showSecret?newSecret:'•'.repeat(36)}</code></div><div className="dp-secret-actions"><button className="dp-button ghost" onClick={()=>setShowSecret(v=>!v)}>{showSecret?<EyeOff size={15}/>:<Eye size={15}/>} {showSecret?'Hide':'Reveal'}</button><button className="dp-button primary" onClick={()=>copy(newSecret)}><Copy size={15}/> Copy secret</button><button className="dp-button quiet" onClick={()=>setShowSecret(false)}>Dismiss</button></div></div>}
 <div className="dp-two-col dp-keys-layout"><section className="dp-panel"><div className="dp-panel-head"><div><h3>Create an API key</h3><p>Use least privilege and set an expiry.</p></div><KeyRound size={18}/></div><form className="dp-form" onSubmit={makeKey}><label>Key name<input value={form.name} onChange={e=>setForm(v=>({...v,name:e.target.value}))} required minLength={2} maxLength={100}/></label><label>Environment<select value={form.environment} onChange={e=>setForm(v=>({...v,environment:e.target.value}))}><option value="sandbox">Sandbox — development and tests</option><option value="production">Production — approved live traffic</option></select></label><label>Expiration<select value={form.expires_in_days} onChange={e=>setForm(v=>({...v,expires_in_days:Number(e.target.value)}))}><option value="30">30 days</option><option value="90">90 days</option><option value="180">180 days</option><option value="365">365 days</option></select></label><fieldset className="dp-scope-field"><legend>Permissions</legend><label className="dp-check"><input type="checkbox" checked={form.scopes.includes('registry:read')} onChange={e=>setForm(v=>({...v,scopes:e.target.checked?[...v.scopes,'registry:read'] : v.scopes.filter(s=>s!=='registry:read')}))}/> Registry read</label><label className="dp-check"><input type="checkbox" checked={form.scopes.includes('sources:read')} onChange={e=>setForm(v=>({...v,scopes:e.target.checked?[...v.scopes,'sources:read'] : v.scopes.filter(s=>s!=='sources:read')}))}/> Sources read</label></fieldset>{form.environment==='production'&&!productionAllowed&&<div className="dp-inline-warning"><LockKeyhole size={16}/> Production issuance is blocked until the workspace is verified and access approved. <button type="button" onClick={()=>setPage('Production access')}>Request access</button></div>}<button className="dp-button primary wide" disabled={busy||form.scopes.length===0}>{busy?'Creating…':'Create '+form.environment+' key'}<ArrowRight size={16}/></button></form></section>
 <section className="dp-panel"><div className="dp-panel-head"><div><h3>Existing keys</h3><p>{allKeys.length} persisted credentials · secrets never returned.</p></div><button className="dp-icon-button" onClick={()=>setSearch('')} title="Clear search"><RefreshCw size={15}/></button></div><label className="dp-search"><Search size={15}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Filter keys"/></label>{keys.length?<div className="dp-key-list">{keys.map(k=><article className="dp-key-card" key={k.id}><div className="dp-key-icon"><KeyRound size={16}/></div><div className="dp-key-info"><strong>{k.name}</strong><code>{k.key_prefix}••••••••</code><div><span className={'dp-env-tag '+(k.environment==='sandbox'?'sandbox':'production')}>{k.environment}</span><span className={'dp-state '+(k.status==='active'?'good':'bad')}>{k.status}</span></div><small>Expires {k.expires_at?new Date(k.expires_at).toLocaleDateString():'never'} · Last used {k.last_used_at?new Date(k.last_used_at).toLocaleString():'not used yet'}</small></div><div className="dp-key-actions">{k.status==='active'&&<><button className="dp-icon-button" disabled={busy} onClick={()=>rotateKey(k)} title="Rotate key"><RefreshCw size={15}/></button><button className="dp-icon-button danger" disabled={busy} onClick={()=>revokeKey(k)} title="Revoke key"><Trash2 size={15}/></button></>}</div></article>)}</div>:<Empty title="No matching keys" detail="Create a sandbox key to start integrating."/ >}</section></div></>}
function WebhooksPage({items,form,setForm,create,remove,test,deliveries,selectedHook,loadDeliveries,busy}){
 return <><PageHeading eyebrow="EVENT DELIVERY" title="Webhooks" description="Send asynchronous integration events to your HTTPS endpoints. Deliveries use timestamped HMAC signatures, bounded retries for transient failures, and persisted delivery history."/>
 <div className="dp-two-col"><section className="dp-panel"><div className="dp-panel-head"><div><h3>Register an endpoint</h3><p>Use a public HTTPS endpoint. Localhost/private IP targets are rejected.</p></div><Webhook size={18}/></div><form className="dp-form" onSubmit={create}><label>Endpoint name<input value={form.name} onChange={e=>setForm(v=>({...v,name:e.target.value}))} minLength={2} maxLength={120} required placeholder="Order reconciliation events"/></label><label>HTTPS endpoint URL<input type="url" value={form.endpoint_url} onChange={e=>setForm(v=>({...v,endpoint_url:e.target.value}))} required placeholder="https://yourapp.example.com/webhooks/pesaguard"/></label><fieldset className="dp-scope-field"><legend>Subscribe to events</legend>{EVENTS.map(event=><label className="dp-check" key={event}><input type="checkbox" checked={form.events.includes(event)} onChange={e=>setForm(v=>({...v,events:e.target.checked?[...v.events,event]:v.events.filter(x=>x!==event)}))}/><code>{event}</code></label>)}</fieldset><button className="dp-button primary wide" disabled={busy||!form.events.length}>Create webhook <ArrowRight size={16}/></button></form></section>
 <section className="dp-panel"><div className="dp-panel-head"><div><h3>Configured endpoints</h3><p>{items.length} webhook subscriptions in your workspace.</p></div><RefreshCw size={17}/></div>{items.length?<div className="dp-hook-list">{items.map(h=><article className="dp-hook-card" key={h.id}><div className="dp-hook-head"><span className="dp-hook-icon"><Radio size={16}/></span><div><strong>{h.name}</strong><small>{h.endpoint_url}</small></div><span className={'dp-state '+(h.enabled?'good':'bad')}>{h.enabled?'enabled':'disabled'}</span></div><div className="dp-event-tags">{h.events.map(event=><code key={event}>{event}</code>)}</div><div className="dp-hook-actions"><button className="dp-button quiet" disabled={busy||!h.events.includes('webhook.test')} onClick={()=>test(h)}><Zap size={14}/> Send test</button><button className="dp-button quiet" onClick={()=>loadDeliveries(h)}>Deliveries</button><button className="dp-icon-button danger" onClick={()=>remove(h)} aria-label={'Delete '+h.name}><Trash2 size={15}/></button></div></article>)}</div>:<Empty title="No webhook endpoints yet" detail="Register an HTTPS URL to begin receiving subscribed events."/ >}</section></div>
 <section className="dp-panel dp-delivery-panel"><div className="dp-panel-head"><div><h3>Delivery history {selectedHook?'· selected endpoint':''}</h3><p>Persisted attempt results, response status and elapsed time.</p></div><button className="dp-button quiet" onClick={()=>{const h=items.find(x=>x.id===selectedHook);if(h)loadDeliveries(h)}}><RefreshCw size={14}/> Refresh</button></div>{deliveries.length?<div className="dp-table-wrap"><table className="dp-table"><thead><tr><th>Event</th><th>Status</th><th>HTTP</th><th>Latency</th><th>Created</th><th>Response</th></tr></thead><tbody>{deliveries.map(d=><tr key={d.id}><td><code>{d.event_type}</code></td><td><span className={'dp-state '+(d.status==='delivered'?'good':'bad')}>{d.status}</span></td><td>{d.response_status||'—'}</td><td>{d.duration_ms==null?'—':d.duration_ms+' ms'}</td><td>{new Date(d.created_at).toLocaleString()}</td><td>{d.response_excerpt||'—'}</td></tr>)}</tbody></table></div>:<Empty title="No deliveries loaded" detail="Choose Deliveries on an endpoint, or send a test event to create a delivery record."/ >}</section></>;
}
function ApiExplorerPage({tester,setTester,runTest,result,busy,baseUrls}){
 return <><PageHeading eyebrow="LIVE REQUEST WORKBENCH" title="API Explorer" description="Send a real request to the selected API environment. Results are not mocked; browser CORS and network policies apply."/><div className="dp-two-col"><section className="dp-panel"><div className="dp-panel-head"><div><h3>Request configuration</h3><p>Use a key created for the selected environment.</p></div><FlaskConical size={18}/></div><form className="dp-form" onSubmit={runTest}><label>Environment<select value={tester.environment} onChange={e=>setTester(v=>({...v,environment:e.target.value}))}><option value="sandbox">Sandbox</option><option value="production" disabled>Production (server-side only)</option></select></label><div className="dp-base-preview"><small>Base URL</small><code>{baseUrls[tester.environment]}</code></div><label>HTTP method<select value={tester.method} onChange={e=>setTester(v=>({...v,method:e.target.value}))}><option>GET</option><option>POST</option></select></label><label>Request path<input value={tester.path} onChange={e=>setTester(v=>({...v,path:e.target.value}))} required placeholder="/health"/></label><label>API key<input type="password" autoComplete="off" value={tester.apiKey} onChange={e=>setTester(v=>({...v,apiKey:e.target.value}))} required placeholder={tester.environment==='sandbox'?'pg_sandbox_…':'pg_live_…'}/></label>{tester.method==='POST'&&<label>JSON body<textarea value={tester.body} onChange={e=>setTester(v=>({...v,body:e.target.value}))} rows={5}/></label>}<div className="dp-inline-warning"><LockKeyhole size={15}/> Sandbox-only browser workbench. Production keys must stay on your trusted backend and be tested with the server-side SDK.</div><button className="dp-button primary wide" disabled={busy||!tester.apiKey.trim()}><Terminal size={16}/>{busy?'Sending request…':'Send request'}<ArrowRight size={15}/></button></form></section><section className="dp-panel"><div className="dp-panel-head"><div><h3>Response</h3><p>HTTP status, elapsed time and body preview.</p></div><Activity size={18}/></div>{result?<><div className="dp-response-meta"><span className={'dp-state '+(result.ok?'good':'bad')}>{result.status}</span><span>{result.ms} ms</span><span className="dp-truncate">{result.url}</span></div><CodeBlock>{result.body||'(empty response body)'}</CodeBlock>{!result.ok&&<p className="dp-muted-note">For NETWORK_ERROR, verify the base URL, DNS, TLS and CORS. HTTP 401/403 commonly indicates an invalid key, environment mismatch, missing scope or insufficient authorization.</p>}</>:<Empty title="No request sent" detail="Configure a request and select Send request to see the actual API response."/ >}</section></div></>;
}
function SdkPage({lang,setLang,copy,baseUrls}){
 return <><PageHeading eyebrow="SDKs & DEVELOPER EXPERIENCE" title="Integrate in your language" description="Use language-specific examples and versioned Python/JavaScript SDK packages, then run a real request in API Explorer. Keep secrets on trusted servers."/><div className="dp-sdk-intro"><div><Code2 size={20}/><strong>REST API first</strong><p>Use the HTTP contract directly from any language. The repository includes Python and JavaScript SDK candidates with offline contract tests; other languages have REST starter examples.</p></div><div><ShieldCheck size={20}/><strong>Secure by default</strong><p>Never put a production key in a browser bundle, mobile app binary or public repository.</p></div><div><FlaskConical size={20}/><strong>Sandbox testing</strong><p>Use the sandbox host and <code>pg_sandbox_</code> credentials until your integration passes acceptance checks.</p></div></div><section className="dp-panel dp-sdk-panel"><div className="dp-panel-head"><div><h3>Request starter</h3><p>Registry search request using a protected API key.</p></div><button className="dp-button quiet" onClick={()=>copy(LANG_CODE[lang])}><Copy size={14}/> Copy snippet</button></div><div className="dp-language-tabs">{LANGS.map(l=><button key={l} className={lang===l?'active':''} onClick={()=>setLang(l)}>{l}</button>)}</div><CodeBlock>{LANG_CODE[lang]}</CodeBlock><div className="dp-sdk-footer"><span>Sandbox base URL: <code>{baseUrls.sandbox}</code></span><button className="dp-button primary" onClick={()=>navigator.clipboard?.writeText(baseUrls.sandbox)}><Copy size={14}/> Copy base URL</button></div></section><section className="dp-panel dp-sdk-packages"><div className="dp-panel-head"><div><h3>SDK packages</h3><p>Source packages with environment-isolation and webhook-signature tests.</p></div><Code2 size={18}/></div><div className="dp-sdk-package-links"><a href="https://github.com/Victor-Kipruto-Rop/pesaguard-datasource/tree/feat/datasource-crud-jobs-api-keys/sdks/python" target="_blank" rel="noreferrer"><strong>Python SDK</strong><code>cd sdks/python && pip install -e ".[test]" && pytest</code><span>Search · exact lookup · HMAC webhook verification</span><ExternalLink size={14}/></a><a href="https://github.com/Victor-Kipruto-Rop/pesaguard-datasource/tree/feat/datasource-crud-jobs-api-keys/sdks/javascript" target="_blank" rel="noreferrer"><strong>JavaScript SDK</strong><code>cd sdks/javascript && npm test</code><span>Node 18+ · Fetch API · HMAC webhook verification</span><ExternalLink size={14}/></a></div><p className="dp-muted-note">These packages are source-controlled test candidates; tests still need to pass in a functioning runner and they are not published to PyPI/npm yet.</p></section><section className="dp-panel"><div className="dp-panel-head"><div><h3>Production release checklist</h3><p>Before switching your base URL to production.</p></div><ShieldCheck size={18}/></div><ul className="dp-checklist"><li><CheckCircle2 size={16}/> Sandbox tests pass for valid, invalid, missing and expired keys.</li><li><CheckCircle2 size={16}/> Verify your integration never logs API keys or sensitive payloads.</li><li><CheckCircle2 size={16}/> Set timeouts, bounded retries and idempotency where supported.</li><li><CheckCircle2 size={16}/> Validate webhook signatures and deduplicate delivery IDs.</li><li><CheckCircle2 size={16}/> Request production access and store live secrets in a server-side secret manager.</li></ul></section></>;
}
function ProductionAccessPage({workspace,requests,submit,busy,baseUrls}){
 const approved=workspace?.verified&&workspace?.production_access_approved;
 return <><PageHeading eyebrow="GO-LIVE GOVERNANCE" title="Production access" description="Production credentials are issued only after explicit review and authoritative workspace verification."/><div className="dp-production-status"><span className="dp-production-shield"><ShieldCheck size={23}/></span><div><div className="dp-eyebrow">CURRENT STATUS</div><h2>{approved?'Production access approved':'Production access not approved'}</h2><p>{approved?'Your workspace has the required verification and access approval.':'Sandbox remains available. Request a review with a concrete use case and realistic expected traffic.'}</p></div><span className={'dp-state '+(approved?'good':'warn')}>{approved?'approved':'gated'}</span></div><div className="dp-two-col"><section className="dp-panel"><div className="dp-panel-head"><div><h3>Request live access</h3><p>Include your integration, data handling and operational readiness.</p></div><Rocket size={18}/></div><form className="dp-form" onSubmit={submit}><label>Use case and integration design<textarea name="use_case" minLength={30} maxLength={5000} required rows={6} placeholder="Describe your product, the end-user workflow, authorization, data retention and how you handle errors."/></label><label>Expected request volume<select name="expected_volume" required defaultValue=""><option value="" disabled>Select expected volume</option><option>Under 1,000 requests/day</option><option>1,000–10,000 requests/day</option><option>10,000–100,000 requests/day</option><option>Over 100,000 requests/day</option></select></label><button className="dp-button primary wide" disabled={busy||approved}>Submit production access request</button></form></section><section className="dp-panel"><div className="dp-panel-head"><div><h3>Environment rules</h3><p>These boundaries are server-enforced.</p></div><LockKeyhole size={18}/></div><div className="dp-env-rule"><span className="dp-env-tag sandbox">SANDBOX</span><code>{baseUrls.sandbox}</code><p>Key prefix <code>pg_sandbox_</code> · test data and sandbox policies.</p></div><div className="dp-env-rule"><span className="dp-env-tag production">PRODUCTION</span><code>{baseUrls.production}</code><p>Key prefix <code>pg_live_</code> · verified workspace, approved access and expiring credentials required.</p></div></section></div><section className="dp-panel"><div className="dp-panel-head"><div><h3>Request history</h3><p>Saved requests and review decisions.</p></div></div>{requests.length?<div className="dp-table-wrap"><table className="dp-table"><thead><tr><th>Use case</th><th>Expected volume</th><th>Status</th><th>Requested</th><th>Reviewer note</th></tr></thead><tbody>{requests.map(r=><tr key={r.id}><td>{r.use_case}</td><td>{r.expected_volume}</td><td><span className={'dp-state '+(r.status==='approved'?'good':'warn')}>{r.status}</span></td><td>{new Date(r.created_at).toLocaleString()}</td><td>{r.reviewer_note||'—'}</td></tr>)}</tbody></table></div>:<Empty title="No production access requests" detail="Your request history will appear here after you submit one."/ >}</section></>;
}
function DeveloperDocsPage({baseUrls,apiDocs,setPage}){
 const sections=[['Authentication','Send the API key using the X-API-Key header. Never expose a secret in browser JavaScript or source control.'],['Environment isolation','Use the sandbox base URL with pg_sandbox_ keys, and the production base URL with pg_live_ keys. Never switch hosts based on a client-supplied environment flag.'],['Errors and retries','Treat 401/403 as authentication or authorization failures; retry only bounded transient failures (429/5xx) with exponential backoff and jitter.'],['Webhook verification','Verify the HMAC signature over the exact raw request body, compare signatures in constant time, reject stale timestamps and deduplicate delivery IDs. Delivery retries are bounded and target transient network errors, HTTP 408/425/429, and 5xx responses.'],['Production access','Submit a request, complete organization verification and wait for explicit approval before creating live credentials.'],['Account lifecycle','Sign-up verifies email with a one-time code delivered through Resend. Password recovery uses a separate expiring OTP and revokes all active sessions after a successful reset. Session inventory supports revocation. Configure RESEND_API_KEY, RESEND_FROM_EMAIL and AUTH_OTP_PEPPER on the backend; never put email-provider secrets in frontend builds.']];
 return <><PageHeading eyebrow="DOCUMENTATION" title="Developer documentation" description="Integration guidance, environment rules and live API schema links." actions={<button className="dp-button primary" onClick={()=>setPage('SDKs & Testing')}><Code2 size={15}/> SDK examples</button>}/><div className="dp-doc-links"><a href={`${API_BASE}/openapi.json`} target="_blank" rel="noreferrer"><FileCode2 size={18}/><span><strong>OpenAPI schema</strong><small>Machine-readable API contract</small></span><ExternalLink size={14}/></a><a href={`${API_BASE}/docs`} target="_blank" rel="noreferrer"><BookOpen size={18}/><span><strong>Swagger UI</strong><small>Explore documented FastAPI endpoints</small></span><ExternalLink size={14}/></a><a href={`${API_BASE}/redoc`} target="_blank" rel="noreferrer"><BookOpen size={18}/><span><strong>ReDoc</strong><small>Reference documentation</small></span><ExternalLink size={14}/></a><a href="https://github.com/Victor-Kipruto-Rop/pesaguard-datasource/blob/feat/datasource-crud-jobs-api-keys/docs/developer-platform-deployment-and-integration.md" target="_blank" rel="noreferrer"><BookOpen size={18}/><span><strong>Setup & release guide</strong><small>OAuth, environments, webhooks and SDK testing</small></span><ExternalLink size={14}/></a></div><div className="dp-doc-env"><div><small>Sandbox</small><code>{baseUrls.sandbox}</code></div><div><small>Production</small><code>{baseUrls.production}</code></div></div>{sections.map(([title,body])=><section className="dp-doc-section" key={title}><h3>{title}</h3><p>{body}</p></section>)}</>;
}
function AccountPage({user,workspace,profile,setProfile,saveProfile,busy}){
 return <><PageHeading eyebrow="ACCOUNT & SECURITY" title="Account settings" description="Manage your developer identity and workspace profile. Authentication sessions remain server-controlled."/><div className="dp-two-col"><section className="dp-panel"><div className="dp-panel-head"><div><h3>Profile</h3><p>Changes are saved to your developer account.</p></div><UserRound size={18}/></div><form className="dp-form" onSubmit={saveProfile}><label>Display name<input value={profile.display_name} onChange={e=>setProfile(v=>({...v,display_name:e.target.value}))} minLength={2} maxLength={120} required/></label><label>Workspace name<input value={profile.workspace_name} onChange={e=>setProfile(v=>({...v,workspace_name:e.target.value}))} minLength={2} maxLength={160} required/></label><label>Email address<input value={user.email} disabled readOnly/><small>Email is verified identity metadata and cannot be changed from this profile form.</small></label><button className="dp-button primary" disabled={busy}>Save profile</button></form></section><section className="dp-panel"><div className="dp-panel-head"><div><h3>Security posture</h3><p>Current account facts from the API.</p></div><ShieldCheck size={18}/></div><div className="dp-security-facts"><div><span>Email verified</span><strong>{user.email_verified?'Yes':'No'}</strong></div><div><span>Workspace verified</span><strong>{workspace.verified?'Yes':'No'}</strong></div><div><span>Production access</span><strong>{workspace.production_access_approved?'Approved':'Not approved'}</strong></div><div><span>Session cookie</span><strong>HttpOnly · CSRF protected</strong></div></div><p className="dp-muted-note">Password reset revokes all existing developer sessions. You can sign out here to revoke the current session.</p></section></div></>;
}
function Empty({title,detail}){return <div className="dp-empty"><span><CircleHelp size={21}/></span><strong>{title}</strong><p>{detail}</p></div>;}

function SessionsPage({items,revoke,busy}){
 return <><PageHeading eyebrow="ACCOUNT SECURITY" title="Active sessions" description="Review and revoke authenticated developer sessions. Revocation is persisted and checked by the API on every session-authenticated request."/><section className="dp-panel"><div className="dp-panel-head"><div><h3>Session inventory</h3><p>{items.length} active session(s) returned by the backend.</p></div><ShieldCheck size={18}/></div>{items.length?<div className="dp-table-wrap"><table className="dp-table"><thead><tr><th>Device / browser</th><th>Created</th><th>Last seen</th><th>Expires</th><th>State</th><th>Action</th></tr></thead><tbody>{items.map(s=><tr key={s.id}><td><strong>{s.current?'This session':'Other session'}</strong><small>{s.user_agent||'Browser not identified'}</small></td><td>{new Date(s.created_at).toLocaleString()}</td><td>{new Date(s.last_seen_at).toLocaleString()}</td><td>{new Date(s.expires_at).toLocaleString()}</td><td><span className="dp-state good">{s.current?'current':'active'}</span></td><td><button className="dp-button quiet" disabled={busy} onClick={()=>revoke(s)}><LogOut size={14}/>{s.current?'Sign out':'Revoke'}</button></td></tr>)}</tbody></table></div>:<Empty title="No active sessions found" detail="Your current session should appear after a successful refresh. Sign in again if it has expired."/ >}</section></>;
}

function DeveloperNotificationsPage({items,refresh,busy}){
  return <><PageHeading eyebrow="WORKSPACE ACTIVITY" title="Notifications" description="A live feed assembled from persisted API-key audit events, production-access decisions and webhook delivery outcomes." actions={<button className="dp-button quiet" onClick={refresh} disabled={busy}><RefreshCw size={15}/> Refresh</button>}/>
    <section className="dp-panel"><div className="dp-panel-head"><div><h3>Recent activity</h3><p>{items.length} event(s) returned by the backend. New entries appear after a refresh.</p></div><BellRing size={18}/></div>
    {items.length?<div className="dp-notification-list">{items.map(item=><article className="dp-notification-item" key={item.id}><span className="dp-notification-mark"><BellRing size={16}/></span><div><strong>{item.title}</strong><p>{item.message}</p><small>{item.source} · {new Date(item.created_at).toLocaleString()}</small></div><code>{item.type}</code></article>)}</div>:<Empty title="No workspace notifications yet" detail="API-key changes, production-access decisions and webhook delivery outcomes will appear here."/ >}
    </section></>;
}

function PublicHomePage({setMode,config}){
 return <main className="dp-public-home">
  <header className="dp-public-nav"><a className="dp-brand" href="#"><span className="dp-brand-mark"><img src="/pesaguard-mark.svg" alt=""/></span><span><strong>PesaGuard</strong><small>DEVELOPER PLATFORM</small></span></a><nav><a href="#capabilities">Platform</a><a href="#environments">Environments</a><a href="#integrate">Integration</a><button className="dp-button ghost" onClick={()=>setMode('login')}>Sign in</button><button className="dp-button primary" onClick={()=>setMode('signup')}>Get started <ArrowRight size={15}/></button></nav><button className="dp-mobile-menu" onClick={()=>setMode('login')} aria-label="Sign in"><Menu size={19}/></button></header>
  <section className="dp-public-hero"><div className="dp-public-hero-copy"><div className="dp-eyebrow"><span className="dp-live-dot"/> DEVELOPER-FIRST FINANCIAL DATA INFRASTRUCTURE</div><h1>Connect your product<br/>to <em>trusted data flows.</em></h1><p>Build integrations with environment-isolated API keys, signed webhooks, live request testing and clear production access controls—all in one developer workspace.</p><div className="dp-hero-actions"><button className="dp-button primary" onClick={()=>setMode('signup')}>Start building <ArrowRight size={16}/></button><button className="dp-button ghost" onClick={()=>document.getElementById('integrate')?.scrollIntoView({behavior:'smooth'})}>Explore the API <ArrowDownRight size={15}/></button></div><div className="dp-public-proof"><span><ShieldCheck size={15}/> Scoped API access</span><span><FlaskConical size={15}/> Sandbox first</span><span><Webhook size={15}/> Signed events</span></div></div><div className="dp-public-visual"><WindHero/><div className="dp-floating-card card-key"><span><KeyRound size={15}/></span><div><small>API CREDENTIAL</small><strong>pg_sandbox_••••••</strong><i>Environment locked</i></div></div><div className="dp-floating-card card-event"><span><Webhook size={15}/></span><div><small>EVENT STREAM</small><strong>registry.lookup.completed</strong><i>Signed delivery</i></div></div><div className="dp-floating-card card-status"><span><Activity size={15}/></span><div><small>REQUEST STATUS</small><strong>200 · OK</strong><i>Traceable response</i></div></div></div></section>
  <section className="dp-public-strip" id="environments"><div><span className="dp-eyebrow">SANDBOX</span><strong>Build and test safely</strong><code>https://sandbox-api.pesaguard.co.ke</code><small>Key prefix: pg_sandbox_</small></div><div className="dp-public-strip-divider"/><div><span className="dp-eyebrow">PRODUCTION</span><strong>Go live through review</strong><code>https://api.pesaguard.co.ke</code><small>Key prefix: pg_live_</small></div><div className="dp-public-strip-divider"/><div><span className="dp-eyebrow">BUILT-IN GUARDRAILS</span><strong>Strict environment separation</strong><small>Sandbox keys are rejected by production deployments. Live credentials require approval.</small></div></section>
  <section className="dp-public-features" id="capabilities"><div className="dp-public-section-head"><span className="dp-eyebrow">ONE WORKSPACE · FULL CONTROL</span><h2>From first request to production.</h2><p>Tools to build, validate and operate integrations without exposing internal service credentials.</p></div><div className="dp-public-feature-grid"><article><span><KeyRound size={19}/></span><h3>API key management</h3><p>Create sandbox keys, rotate or revoke credentials, choose read scopes and review expiration metadata. Full secrets are shown only once.</p></article><article><span><Webhook size={19}/></span><h3>Webhooks that explain themselves</h3><p>Register HTTPS endpoints, select event types, send test events and inspect persisted delivery status and response codes.</p></article><article><span><FlaskConical size={19}/></span><h3>API Explorer</h3><p>Send real requests to the selected environment and inspect response bodies, HTTP status and latency without pretending results are mocked.</p></article><article><span><Code2 size={19}/></span><h3>Language starter kits</h3><p>Copy integration examples for cURL, JavaScript, Python, PHP, Go, Java, Ruby and C# using environment variables for secrets.</p></article><article><span><ShieldCheck size={19}/></span><h3>Production access workflow</h3><p>Submit a use case and expected volume. Production keys stay blocked until the workspace is verified and explicitly approved.</p></article><article><span><BookOpen size={19}/></span><h3>Live API documentation</h3><p>Explore OpenAPI, Swagger UI and ReDoc, with a practical handbook for authentication, retries and webhook verification.</p></article></div></section>
  <section className="dp-public-integrate" id="integrate"><div><span className="dp-eyebrow">INTEGRATE YOUR WAY</span><h2>Use your stack.<br/><em>Keep your secrets server-side.</em></h2><p>Connect websites, backend services, business applications and data platforms through the same versioned HTTP API. Start with sandbox credentials and promote only after integration checks.</p><div className="dp-language-pills">{LANGS.map(l=><span key={l}>{l}</span>)}</div><button className="dp-button primary" onClick={()=>setMode('signup')}>Create developer workspace <ArrowRight size={15}/></button></div><div className="dp-public-code"><div className="dp-code-title"><span/><span/><span/> <small>request.example</small></div><CodeBlock>{LANG_CODE.JavaScript}</CodeBlock><div className="dp-code-foot"><ShieldCheck size={14}/> Key loaded from server-side environment variables</div></div></section>
  <footer className="dp-public-footer"><a className="dp-brand" href="#"><span className="dp-brand-mark"><img src="/pesaguard-mark.svg" alt=""/></span><span><strong>PesaGuard</strong><small>DEVELOPER PLATFORM</small></span></a><span>Built for developers integrating financial data into their products.</span><div><button onClick={()=>setMode('login')}>Sign in</button><button onClick={()=>setMode('signup')}>Create account</button></div></footer>
 </main>;
}
