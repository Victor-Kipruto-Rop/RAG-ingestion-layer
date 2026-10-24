import React, { useEffect, useState } from 'react';
import { CheckCircle2, LoaderCircle, Save, ShieldCheck, UserRound } from 'lucide-react';
import { api } from './api.js';

export default function ProfilePage() {
  const [profile, setProfile] = useState({ display_name: '', contact_email: '', role: 'operator', auth_method: 'password', identity_email: null, updated_at: null });
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  useEffect(() => {
    let active = true;
    api('/api/v1/admin/profile').then(r => r.json()).then(value => { if (active) setProfile({ ...value, contact_email: value.contact_email || '' }); })
      .catch(e => { if (active) setError(e.message || 'Could not load operator profile. Apply the database migration and retry.'); })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, []);
  const save = async event => {
    event.preventDefault(); setSaving(true); setError(''); setMessage('');
    try {
      const response = await api('/api/v1/admin/profile', { method: 'PUT', body: JSON.stringify({ display_name: profile.display_name, contact_email: profile.contact_email || null }) });
      const updated = await response.json();
      setProfile(current => ({ ...current, ...updated, contact_email: updated.contact_email || '' }));
      setMessage('Profile changes saved to the datasource database.');
    } catch (e) { setError(e.message || 'Could not save profile.'); }
    finally { setSaving(false); }
  };
  return <div className="profile-page">
    <div className="page-heading"><div><div className="eyebrow-label">ACCOUNT</div><h1>Operator profile</h1><p>Manage the display name and contact email for this internal datasource workspace.</p></div><span className="profile-role"><ShieldCheck size={15}/> Operator access</span></div>
    {error && <div className="alert-banner error" role="alert">{error}</div>}
    {message && <div className="alert-banner success" role="status"><CheckCircle2 size={16}/>{message}</div>}
    <div className="profile-grid">
      <section className="panel profile-card"><div className="profile-avatar"><UserRound size={27}/></div><div><h2>{profile.display_name || 'Operator profile'}</h2><p>{profile.contact_email || profile.identity_email || 'No contact email configured'}</p></div><span className="profile-role">{profile.role || 'operator'}</span><div className="profile-divider"/><div className="profile-detail"><span>Sign-in method</span><strong>{profile.auth_method || 'password'}</strong></div><div className="profile-detail"><span>Verified identity</span><strong>{profile.identity_email || 'Password-based operator'}</strong></div><div className="profile-detail"><span>Profile last updated</span><strong>{profile.updated_at ? new Date(profile.updated_at).toLocaleString() : 'Not saved yet'}</strong></div></section>
      <section className="panel profile-form-card"><div className="panel-heading"><div><h2>Profile details</h2><p>Changes are persisted by the authenticated backend.</p></div></div>
        {busy ? <div className="module-empty"><LoaderCircle size={22} className="spin"/><strong>Loading profile</strong></div> : <form className="profile-form" onSubmit={save}><label htmlFor="profile-display-name">Display name</label><input id="profile-display-name" required minLength={2} maxLength={120} value={profile.display_name} onChange={e => setProfile(p => ({ ...p, display_name: e.target.value }))}/><label htmlFor="profile-contact-email">Contact email</label><input id="profile-contact-email" type="email" maxLength={320} placeholder="name@company.com" value={profile.contact_email} onChange={e => setProfile(p => ({ ...p, contact_email: e.target.value }))}/><p className="profile-note">The contact email is profile metadata only. It does not change the identity provider email, allowlist membership, or password-reset destination.</p><button className="button-primary" type="submit" disabled={saving || !profile.display_name.trim()}><Save size={16}/>{saving ? 'Saving…' : 'Save profile'}</button></form>}
      </section>
    </div>
  </div>;
}
