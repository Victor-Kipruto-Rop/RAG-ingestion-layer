import React, { useEffect, useState } from 'react';
import { ArrowLeft, ArrowRight, CheckCircle2, KeyRound, LockKeyhole, Mail, ShieldCheck, UserRound, Building2 } from 'lucide-react';
import { api, setCsrfToken } from './api.js';

export default function DeveloperAuthPage({ initialMode = 'login', onAuthenticated }) {
  const [mode, setMode] = useState(initialMode);
  const [stage, setStage] = useState(initialMode === 'reset' ? 'request' : initialMode === 'signup' ? 'details' : 'login');
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [workspace, setWorkspace] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [config, setConfig] = useState({ signup_enabled: false, password_reset_enabled: false, password_min_length: 12, otp_ttl_seconds: 600 });
  const reset = mode === 'reset';
  const signup = mode === 'signup';
  useEffect(() => { api('/api/v1/developer/auth/config').then(r => r.json()).then(setConfig).catch(() => {}); }, []);

  const submit = async event => {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      let result;
      if (stage === 'login') {
        const r = await api('/api/v1/developer/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
        result = await r.json(); setCsrfToken(result.csrf_token); onAuthenticated(result); return;
      }
      if (signup && stage === 'details') {
        await api('/api/v1/developer/auth/signup/request-otp', { method: 'POST', body: JSON.stringify({ email, display_name: name, workspace_name: workspace, password }) });
        setStage('verify'); setNotice('If the request can be completed, a verification code has been sent. Check your inbox and spam folder.');
      } else if (signup && stage === 'verify') {
        const r = await api('/api/v1/developer/auth/signup/verify-otp', { method: 'POST', body: JSON.stringify({ email, code }) });
        result = await r.json(); setCsrfToken(result.csrf_token); onAuthenticated(result); return;
      } else if (reset && stage === 'request') {
        await api('/api/v1/developer/auth/password-reset/request-otp', { method: 'POST', body: JSON.stringify({ email }) });
        setStage('confirm'); setNotice('If an active account exists for this address, a reset code has been sent.');
      } else if (reset && stage === 'confirm') {
        await api('/api/v1/developer/auth/password-reset/confirm', { method: 'POST', body: JSON.stringify({ email, code, new_password: password }) });
        setStage('done'); setNotice('Password updated. All active sessions have been revoked. Sign in with your new password.');
      }
    } catch (e) { setError(e.message || 'Authentication could not be completed.'); }
    finally { setBusy(false); }
  };

  const changeMode = next => { setMode(next); setStage(next === 'reset' ? 'request' : next === 'signup' ? 'details' : 'login'); setError(''); setNotice(''); setCode(''); setPassword(''); setConfirm(''); };
  const title = stage === 'login' ? 'Welcome back' : stage === 'details' ? 'Create your developer account' : stage === 'verify' ? 'Verify your email' : stage === 'request' ? 'Recover your account' : stage === 'confirm' ? 'Set a new password' : 'Password updated';
  const subtitle = stage === 'login' ? 'Sign in to build and manage your integrations.' : stage === 'details' ? 'Create a workspace, start in sandbox, and move to production after review.' : stage === 'verify' ? 'Enter the six-digit code sent to your email address.' : stage === 'request' ? 'We will send a short-lived code if an account exists for this email.' : stage === 'confirm' ? 'Enter the code and choose a new password.' : 'Your account recovery is complete.';
  const passwordStage = (signup && stage === 'details') || (reset && stage === 'confirm');
  return <main className="dev-auth">
    <section className="dev-auth-story">
      <a href="/" className="dev-brand"><span className="dev-brand-mark">P</span><span>PesaGuard <b>Developers</b></span></a>
      <div className="dev-auth-orbit" aria-hidden="true"><i/><i/><i/><span>API</span></div>
      <div className="dev-auth-copy"><span className="dev-eyebrow">DEVELOPER INFRASTRUCTURE</span><h1>Build once.<br/><em>Integrate with confidence.</em></h1><p>Environment-isolated API keys, signed webhooks, clear API contracts, and developer-first tooling.</p><ul><li><ShieldCheck size={17}/> Sandbox-first access</li><li><KeyRound size={17}/> Short-lived access tokens</li><li><Building2 size={17}/> Separate workspace and operator identities</li></ul></div>
      <span className="dev-auth-foot">Secure by design · Production access is reviewed</span>
    </section>
    <section className="dev-auth-panel">
      <div className="dev-auth-card">
        <a href="/" className="dev-back"><ArrowLeft size={15}/> Back to home</a>
        <span className="dev-auth-icon">{reset ? <KeyRound size={20}/> : stage === 'verify' ? <Mail size={20}/> : stage === 'details' ? <UserRound size={20}/> : <LockKeyhole size={20}/>}</span>
        <div className="dev-eyebrow">{signup ? 'CREATE ACCOUNT' : reset ? 'ACCOUNT RECOVERY' : 'DEVELOPER CONSOLE'}</div>
        <h2>{title}</h2><p className="dev-auth-subtitle">{subtitle}</p>
        {error && <div className="dev-alert error" role="alert">{error}</div>}
        {notice && <div className="dev-alert info" role="status">{notice}</div>}
        {stage === 'done' ? <button className="dev-primary-button" onClick={() => changeMode('login')}>Return to sign in <ArrowRight size={16}/></button> :
          <form onSubmit={submit} className="dev-form">
            {signup && stage === 'details' && <><label htmlFor="dev-name">Your name</label><input id="dev-name" value={name} onChange={e=>setName(e.target.value)} autoComplete="name" required minLength={2} maxLength={120} placeholder="Jane Developer"/><label htmlFor="dev-workspace">Workspace or company</label><input id="dev-workspace" value={workspace} onChange={e=>setWorkspace(e.target.value)} required minLength={2} maxLength={160} placeholder="Acme Engineering"/></>}
            {(stage === 'login' || stage === 'details' || stage === 'request' || stage === 'verify' || stage === 'confirm') && <><label htmlFor="dev-email">Email address</label><input id="dev-email" type="email" value={email} onChange={e=>setEmail(e.target.value)} autoComplete="email" required maxLength={320} readOnly={stage === 'verify' || stage === 'confirm'} placeholder="you@company.com"/></>}
            {(stage === 'verify' || stage === 'confirm') && <><label htmlFor="dev-otp">Six-digit verification code</label><input id="dev-otp" value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,'').slice(0,6))} inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" required placeholder="000000"/></>}
            {stage === 'login' && <><label htmlFor="dev-password">Password</label><input id="dev-password" type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete="current-password" required maxLength={256} placeholder="Your password"/></>}
            {passwordStage && <><label htmlFor="dev-new-password">{reset ? 'New password' : 'Password'}</label><input id="dev-new-password" type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete="new-password" minLength={12} maxLength={256} required placeholder="At least 12 characters"/>{signup && <><label htmlFor="dev-confirm-password">Confirm password</label><input id="dev-confirm-password" type="password" value={confirm} onChange={e=>setConfirm(e.target.value)} autoComplete="new-password" minLength={12} maxLength={256} required placeholder="Repeat password"/></>}</>}
            <button className="dev-primary-button" disabled={busy || (signup && stage === 'details' && password !== confirm)}>{busy ? 'Please wait…' : stage === 'login' ? 'Sign in' : stage === 'details' ? 'Send verification code' : stage === 'verify' ? 'Verify email and create workspace' : stage === 'request' ? 'Send reset code' : 'Reset password'} <ArrowRight size={16}/></button>
          </form>}
        {stage === 'login' && <div className="dev-auth-links"><button onClick={() => changeMode('reset')}>Forgot password?</button><button onClick={() => changeMode('signup')}>Create account</button></div>}
        {stage !== 'login' && stage !== 'done' && <button className="dev-text-button" onClick={() => changeMode('login')}>Back to sign in</button>}
        <p className="dev-auth-legal">By continuing, you agree to use only authorized data and keep your credentials private. Production keys require approval and organization verification.</p>
      </div>
    </section>
  </main>;
}
