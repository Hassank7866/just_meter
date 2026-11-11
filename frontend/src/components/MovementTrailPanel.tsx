import React, { useEffect, useState } from 'react';
import { fetchMovementTrail, MovementTrail, reviewMovementAlert } from '../api/client';
import { useAuth } from '../context/AuthContext';

const box = 'rounded-xl border border-slate-800 bg-slate-900/70 p-4 space-y-2';
const button = 'rounded-lg border border-slate-700 px-3 py-2 text-sm hover:bg-slate-800 disabled:opacity-40';
const date = (value: string) => new Date(value).toLocaleString();

export const MovementTrailPanel: React.FC<{ vehicleId: number; filters: string; refresh: number }> = ({ vehicleId, filters, refresh }) => {
  const { user } = useAuth();
  const [offset, setOffset] = useState(0);
  const [trail, setTrail] = useState<MovementTrail | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [reviewKey, setReviewKey] = useState('');
  const [reviewNotes, setReviewNotes] = useState('');
  const [reload, setReload] = useState(0);

  useEffect(() => { setOffset(0); }, [vehicleId, filters]);
  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams(filters);
    params.delete('as_of'); params.delete('camera_area');
    params.set('limit', '20'); params.set('offset', String(offset));
    setLoading(true); setError(''); setTrail(null);
    fetchMovementTrail(vehicleId, params, controller.signal)
      .then(result => { if (!controller.signal.aborted) setTrail(result); })
      .catch(err => { if (!controller.signal.aborted) setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [vehicleId, filters, offset, refresh, reload]);

  const review = async (alertKey: string, status: 'CONFIRMED' | 'DISMISSED') => {
    setError('');
    try {
      await reviewMovementAlert(vehicleId, alertKey, status, reviewNotes.trim());
      setReviewKey(''); setReviewNotes(''); setReload(value => value + 1);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not save review'); }
  };

  return <section className="space-y-3">
    <h2 className="text-lg font-semibold">Movement trail {trail ? `(${trail.total})` : ''}</h2>
    <p className="text-xs text-slate-400">Ordered by observation time. Registry sightings, reviewed live-camera crossings and administrator-confirmed camera links have different evidence levels. This is not an approved route or automatic identity finding.</p>
    {loading && <p role="status">Loading movement trail...</p>}
    {error && <p role="alert" className="text-red-300">{error}</p>}
    {!!trail?.alert_total && <div className="space-y-2"><h3 className="font-semibold text-amber-200">Movement findings ({trail.alert_total})</h3>
      <p className="text-xs text-slate-400">Findings require officer review. They do not create a violation or challan automatically.</p>
      {trail.alerts.map(alert => <article className={`${box} border-amber-800/60`} key={alert.alert_key}>
        <div className="flex flex-wrap justify-between gap-2"><strong>{alert.kind.replace(/_/g, ' ')}</strong><time className="text-xs">{date(alert.observed_at)}</time></div>
        <p>{alert.message}</p><p className="text-xs text-slate-400">{alert.route_name} · {alert.camera_id || 'Camera unknown'} · {alert.status.replace(/_/g, ' ')}</p>
        {alert.reviewed_by && <p className="text-xs text-slate-400">Reviewed by {alert.reviewed_by}: {alert.notes}</p>}
        {['Administrator', 'Transport Officer', 'Supervisory Officer'].includes(user?.role || '') && (reviewKey === alert.alert_key ? <div className="space-y-2">
          <textarea className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-sm" rows={2} value={reviewNotes} onChange={event => setReviewNotes(event.target.value)} placeholder="Explain the evidence and review decision (at least 10 characters)" />
          <div className="flex gap-2"><button className={button} disabled={reviewNotes.trim().length < 10} onClick={() => void review(alert.alert_key, 'CONFIRMED')}>Confirm finding</button>
            <button className={button} disabled={reviewNotes.trim().length < 10} onClick={() => void review(alert.alert_key, 'DISMISSED')}>Dismiss</button>
            <button className={button} onClick={() => setReviewKey('')}>Cancel</button></div></div>
          : <button className={button} onClick={() => { setReviewKey(alert.alert_key); setReviewNotes(alert.notes || ''); }}>Review</button>)}
      </article>)}</div>}
    {!loading && !error && trail?.items.length === 0 && <p className={box}>No linked movement observations for this period.</p>}
    {trail?.items.map(item => <article className={box} key={`${item.kind}-${item.id}`}>
      <div className="flex flex-wrap justify-between gap-2"><h3 className="font-semibold">
        {item.kind === 'sighting' ? 'Registry-linked sighting' : item.kind === 'checkpoint_crossing' ? 'Checkpoint crossing' : 'Confirmed camera link'}
      </h3><time className="text-xs text-slate-400">{date(item.at)}</time></div>
      {item.kind === 'sighting' && <p>{item.camera_area || item.camera_id || 'Camera unknown'} · {item.status || 'Status unknown'} · {item.plate_number || 'Plate unavailable'}</p>}
      {item.kind === 'checkpoint_crossing' && <p>{item.checkpoint_name} · {item.camera_id} · {item.direction?.replace(/_/g, ' ')}</p>}
      {item.kind === 'confirmed_link' && <p>{item.from_camera_id} → {item.to_camera_id} · {item.plate_number}</p>}
      <p className="text-xs text-slate-400">Association: {item.association.replace(/_/g, ' ')}
        {item.track_id ? ` · Track ${item.track_id}` : ''}
        {item.confirmed_by ? ` · Confirmed by ${item.confirmed_by}` : ''}</p>
    </article>)}
    {trail && trail.total > 20 && <div className="flex items-center gap-3">
      <button className={button} disabled={offset === 0 || loading} onClick={() => setOffset(value => Math.max(0, value - 20))}>Previous</button>
      <span className="text-xs">Page {Math.floor(offset / 20) + 1}</span>
      <button className={button} disabled={offset + 20 >= trail.total || loading} onClick={() => setOffset(value => value + 20)}>Next</button>
    </div>}
  </section>;
};
