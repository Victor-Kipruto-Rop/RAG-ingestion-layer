import React, { useState } from 'react';
import { ArrowRight, Eye, EyeOff, ShieldCheck, Database, LockKeyhole, Activity } from 'lucide-react';

export default function LoginPage({ password, setPassword, onSubmit, error, checking }) {
  const [visible, setVisible] = useState(false);
  return <main className="auth-shell">
    <section className="auth-story">
      <div className="auth-brand"><span className="auth-brand-mark"><Database size={22}/></span><span><strong>PesaGuard</strong><small>DATASOURCE PLATFORM</small></span></div>
      <div className="auth-story-content">
        <span className="auth-kicker"><i/> FINANCIAL DATA INFRASTRUCTURE</span>
        <h1>Reliable data.<br/><em>Clear decisions.</em></h1>
        <p>Securely ingest, validate and inspect registry data from one operational workspace.</p>
        <div className="auth-feature-list">
          <div><span><ShieldCheck size={17}/></span><div><strong>Controlled access</strong><small>Server-managed session and CSRF protection</small></div></div>
          <div><span><Database size={17}/></span><div><strong>Traceable data operations</strong><small>Follow imports, registry records and processing status</small></div></div>
          <div><span><Activity size={17}/></span><div><strong>Operational visibility</strong><small>Inspect persisted outcomes without fabricated metrics</small></div></div>
        </div>
      </div>
      <div className="auth-story-footer"><span>© {new Date().getFullYear()} PesaGuard</span><span><i/> Secure workspace</span></div>
    </section>
    <section className="auth-form-side">
      <div className="auth-form-wrap">
        <div className="auth-mobile-brand"><span className="auth-brand-mark"><Database size={20}/></span><strong>PesaGuard <small>DATASOURCE</small></strong></div>
        <div className="auth-form-heading"><span className="auth-form-icon"><LockKeyhole size={20}/></span><div className="auth-kicker">WORKSPACE ACCESS</div><h2>Welcome back</h2><p>Sign in to continue to your datasource workspace.</p></div>
        {error && <div className="auth-error" role="alert"><ShieldCheck size={16}/><span>{error}</span></div>}
        <form className="auth-form" onSubmit={onSubmit}>
          <label htmlFor="admin-password">Admin password</label>
          <div className="auth-password-wrap"><LockKeyhole size={17}/><input id="admin-password" type={visible ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)} placeholder="Enter your admin password" autoComplete="current-password" required autoFocus/><button type="button" aria-label={visible ? 'Hide password' : 'Show password'} onClick={() => setVisible(v => !v)}>{visible ? <EyeOff size={17}/> : <Eye size={17}/>}</button></div>
          <div className="auth-security-hint"><ShieldCheck size={14}/><span>Your password is sent to the server over HTTPS. The browser never stores the service API key.</span></div>
          <button className="auth-submit" type="submit" disabled={checking || !password}>{checking ? 'Checking session…' : <>Sign in to workspace <ArrowRight size={17}/></>}</button>
        </form>
        <div className="auth-help"><span>Need access?</span><p>Contact your PesaGuard workspace administrator to obtain the authorized admin credential.</p></div>
        <div className="auth-legal">Access is monitored. Only sign in if you are authorized to use this workspace.</div>
      </div>
    </section>
  </main>;
}
