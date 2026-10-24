import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, CircleHelp, X } from 'lucide-react';

export default function ToastPopup({ kind = 'success', message, onClose, duration = 7000 }) {
  const [createdAt, setCreatedAt] = useState(() => new Date());
  useEffect(() => {
    if (!message) return undefined;
    setCreatedAt(new Date());
    const timer = window.setTimeout(() => onClose?.(), duration);
    return () => window.clearTimeout(timer);
  }, [message, duration, onClose]);
  if (!message) return null;
  const tone = kind === 'success' ? 'success' : kind === 'warning' ? 'warning' : 'error';
  const Icon = tone === 'success' ? CheckCircle2 : tone === 'warning' ? AlertTriangle : CircleHelp;
  const title = tone === 'success' ? 'Success' : tone === 'warning' ? 'Warning' : 'Something needs attention';
  return <div className="dp-toast-viewport" aria-live={tone === 'success' ? 'polite' : 'assertive'}>
    <section className={`dp-toast-popup ${tone}`} role={tone === 'success' ? 'status' : 'alert'}>
      <span className="dp-toast-icon"><Icon size={19}/></span>
      <div className="dp-toast-copy"><strong>{title}</strong><p>{message}</p><time dateTime={createdAt.toISOString()}>{createdAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time></div>
      <button type="button" className="dp-toast-close" onClick={onClose} aria-label="Dismiss message"><X size={17}/></button>
    </section>
  </div>;
}
