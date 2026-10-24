import React, { useState } from 'react';
import { ArrowLeft, ArrowRight, CheckCircle2, KeyRound, LockKeyhole, Mail, ShieldCheck, UserRound } from 'lucide-react';
import { api } from './api.js';

export default function AuthFlowPage({ mode = 'signup', config = {}, onBack, onAuthenticated }) {
  const [stage, setStage] = useState(mode === 'reset' ? 'request' : 'details');
  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const isReset = mode === 'reset';
  const title = isReset ? (stage === 'request' ? 'Reset your password' : 'Verify reset code') : (stage === 'details' ? 'Create operator account' : 'Verify your email');
  const subtitle = isReset
    ? (stage === 'request' ? 'We will send a short-lived code if this email belongs to an eligible operator account.' : 'Enter the six-digit code sent to your email and choose a new password.')
    : (stage === 'details' ? 'Registration is limited to email addresses approved by your workspace administrator.' : 'Enter the six-digit code sent to your approved email address to verify it and activate your account.');

  const submit = async event => {
    event.preventDefault(); setError(''); setNotice('');
    if (!isReset && stage === 'details') {
      if (password !== confirmPassword) { setError('The passwords do not match.'); return; }
      if (password.length < (config.password_min_length || 12)) { setError('Use at least 12 characters for your password.'); return; }
    }
    setBusy(true);
    try {
      if (!isReset && stage === 'details') {
        await api('/api/v1/admin/auth/signup/request-otp', { method: 'POST', body: JSON.stringify({ email, display_name: displayName, password }) });
        setStage('verify');
        setNotice('If the address is approved for registration, a verification code will arrive shortly. Check your inbox and spam folder.');
      } else if (!isReset && stage === 'verify') {
        const response = await api('/api/v1/admin/auth/signup/verify-otp', { method: 'POST', body: JSON.stringify({ email, code }) });
        const result = await response.json();
        onAuthenticated(result);
      } else if (isReset && stage === 'request') {
        await api('/api/v1/admin/auth/password-reset/request-otp', { method: 'POST', body: JSON.stringify({ email }) });
        setStage('confirm');
        setNotice('If an active operator account exists for this address, a password reset code will arrive shortly.');
      } else {
        await api('/api/v1/admin/auth/password-reset/confirm', { method: 'POST', body: JSON.stringify({ email, code, new_password: password }) });
        setStage('done');
        setNotice('Your password was updated. Sign in using the new password.');
      }
    } catch (e) { setError(e.message || 'The request could not be completed. Please try again.'); }
    finally { setBusy(false); }
  };

  return <main className="login-screen auth-flow-screen">
    <section className="login-story"><div className="login-brand"><img className="login-logo" src="/pesaguard-logo.svg" alt="PesaGuard" /></div>
      <div className="login-story-main"><div className="login-eyebrow"><i/> ACCOUNT SECURITY</div><h1>Access built on<br/><em>verified identity.</em></h1><p>Operator access is restricted to approved identities. Email codes expire, passwords are never sent by email, and active sessions can be revoked.</p>
        <div className="login-benefits"><div><span><Mail size={17}/></span><div><strong>Email verification</strong><small>Short-lived, single-use verification codes</small></div></div><div><span><KeyRound size={17}/></span><div><strong>Account recovery</strong><small>Reset access without exposing account existence</small></div></div><div><span><ShieldCheck size={17}/></span><div><strong>Session control</strong><small>Inspect and revoke signed-in sessions</small></div></div></div>
      </div><footer><span>© {new Date().getFullYear()} PesaGuard</span><span><i/> Secure workspace</span></footer>
    </section>
    <section className="login-form-side"><div className="login-form-wrap">
      <button className="auth-back-button" type="button" onClick={onBack}><ArrowLeft size={15}/> Back to sign in</button>
      <div className="login-heading"><span className="login-lock">{isReset ? <KeyRound size={20}/> : stage === 'verify' ? <Mail size={20}/> : <UserRound size={20}/>}</span><div className="login-form-eyebrow">{isReset ? 'ACCOUNT RECOVERY' : 'OPERATOR REGISTRATION'}</div><h2>{stage === 'done' ? 'Password updated' : title}</h2><p>{stage === 'done' ? 'Your account is ready for a new sign-in.' : subtitle}</p></div>
      {error && <div className="login-error" role="alert">{error}</div>}
      {notice && <div className="alert-banner info auth-notice" role="status">{notice}</div>}
      {stage === 'done' ? <div className="auth-complete"><CheckCircle2 size={28}/><p>Your current sessions were revoked as part of the password reset. Sign in again to continue.</p><button className="login-submit" onClick={onBack}>Return to sign in <ArrowRight size={17}/></button></div> :
        <form className="login-form" onSubmit={submit}>
          {!isReset && stage === 'details' && <><label htmlFor="signup-name">Full name</label><div className="auth-input"><UserRound size={16}/><input id="signup-name" autoComplete="name" value={displayName} onChange={e=>setDisplayName(e.target.value)} minLength={2} maxLength={120} required placeholder="Your name"/></div></>}
          {(stage === 'details' || stage === 'request' || stage === 'verify' || stage === 'confirm') && <><label htmlFor="auth-email">Work email</label><div className="auth-input"><Mail size={16}/><input id="auth-email" type="email" autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} required maxLength={320} readOnly={stage === 'verify' || stage === 'confirm'} placeholder="you@company.com"/></div></>}
          {(stage === 'verify' || stage === 'confirm') && <><label htmlFor="auth-code">Email verification code</label><div className="auth-input"><ShieldCheck size={16}/><input id="auth-code" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,'').slice(0,6))} pattern="[0-9]{6}" minLength={6} maxLength={6} required placeholder="6-digit code"/></div><p className="login-hint">Codes expire after {Math.round((config.otp_ttl_seconds || 600)/60)} minutes and are limited to a small number of attempts.</p></>}
          {(!isReset && stage === 'details' || isReset && stage === 'confirm') && <><label htmlFor="auth-password">{isReset ? 'New password' : 'Password'}</label><div className="auth-input"><LockKeyhole size={16}/><input id="auth-password" type="password" autoComplete={isReset ? 'new-password' : 'new-password'} value={password} onChange={e=>setPassword(e.target.value)} minLength={config.password_min_length || 12} maxLength={256} required placeholder="At least 12 characters"/></div><p className="login-hint">Use a unique password with at least {config.password_min_length || 12} characters.</p>{!isReset && <><label htmlFor="auth-confirm-password">Confirm password</label><div className="auth-input"><LockKeyhole size={16}/><input id="auth-confirm-password" type="password" autoComplete="new-password" value={confirmPassword} onChange={e=>setConfirmPassword(e.target.value)} minLength={config.password_min_length || 12} maxLength={256} required placeholder="Enter the password again"/></div></>}</>}
          <button className="login-submit" disabled={busy}>{busy ? 'Please wait…' : stage === 'details' ? 'Send verification code' : stage === 'request' ? 'Send reset code' : isReset ? 'Reset password' : 'Verify email and create account'} <ArrowRight size={17}/></button>
          {stage === 'verify' && <button className="auth-text-button" type="button" disabled={busy} onClick={() => {setStage('details');setCode('');setNotice('Submit the form again to request another code.')}}>Request another code</button>}
          {stage === 'confirm' && <button className="auth-text-button" type="button" disabled={busy} onClick={() => {setStage('request');setCode('');setNotice('Submit again to request a fresh reset code.')}}>Request another code</button>}
        </form>}
      <div className="login-legal">Only approved operator emails can register. If you do not receive a code, contact your workspace administrator.</div>
    </div></section>
  </main>;
}
