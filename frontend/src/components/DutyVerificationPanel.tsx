import React from 'react';
import { DutyVerification } from '../api/client';

export const DutyVerificationPanel: React.FC<{ duty?: DutyVerification | null }> = ({ duty }) => {
  if (!duty) return null;
  return <details className="rounded-lg border border-slate-700 p-3 text-xs space-y-2">
    <summary className="cursor-pointer font-semibold">Duty verification: {duty.status}{duty.review_required ? ' · review needed' : ''}</summary>
    <p className="text-slate-400">Source: {duty.source || 'Not linked'} · Revision: {duty.source_revision ?? 'Unknown'}</p>
    {duty.assignment && <p>Assignment: {String(duty.assignment.external_id)} · Officer: {String(duty.assignment.officer_name)}</p>}
    {duty.duty_slip && <div className="space-y-1"><p>Duty slip: {String(duty.duty_slip.external_id)}</p>
      <p>Destination: {String(duty.duty_slip.destination)}</p><p>Purpose: {String(duty.duty_slip.purpose)}</p>
      <p>Period: {new Date(String(duty.duty_slip.valid_from)).toLocaleString()} – {new Date(String(duty.duty_slip.valid_until)).toLocaleString()}</p></div>}
    {duty.rules.map(r => <p key={r.rule_id} className={r.outcome === 'FAIL' ? 'text-red-300' : r.outcome === 'REVIEW' ? 'text-amber-300' : 'text-emerald-300'}>{r.outcome}: {r.message}</p>)}
    {duty.review && <p className="text-slate-400">Reviewed by {duty.review.actor} · {new Date(duty.review.at).toLocaleString()} · {duty.review.notes}</p>}
  </details>;
};
