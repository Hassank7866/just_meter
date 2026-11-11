import { useEffect, useState } from 'react';
import { fetchVehicleVerifications, reviewVehicleVerification, VehicleVerification } from '../api/client';
import { useAuth } from '../context/AuthContext';

const input = 'w-full rounded border border-slate-700 bg-slate-950 p-2 text-sm';
const fields = ['vehicle_type', 'make', 'model', 'color'] as const;

export function VehicleVerificationPanel({ vehicleId, refresh }: { vehicleId: number; refresh: number }) {
  const { user } = useAuth();
  const [items, setItems] = useState<VehicleVerification[]>([]);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState<number | null>(null);
  const [form, setForm] = useState({ make: '', model: '', color: '', notes: '' });
  const canReview = ['Administrator', 'Transport Officer', 'Supervisory Officer'].includes(user?.role || '');
  const load = async () => {
    try { setItems(await fetchVehicleVerifications(vehicleId)); setError(''); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not load vehicle verifications'); }
  };
  useEffect(() => { void load(); }, [vehicleId, refresh]);
  const review = async (item: VehicleVerification, decision: 'CONFIRMED_MISMATCH' | 'DISMISSED') => {
    try {
      await reviewVehicleVerification(vehicleId, item.id, { ...form, decision });
      setEditing(null); setForm({ make: '', model: '', color: '', notes: '' }); await load();
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not save review'); }
  };
  return <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 space-y-3">
    <h2 className="text-lg font-semibold">Vehicle verification</h2>
    <p className="text-xs text-slate-400">Detector type is compared with trusted VIMS attributes available at capture. Make, model and color require an officer's observation. A confirmed mismatch enters the verification risk queue; it does not create a challan.</p>
    {error && <p role="alert" className="text-rose-300">{error}</p>}
    {!items.length && <p className="text-sm text-slate-400">No verification records for this vehicle yet.</p>}
    {items.map(item => <article key={item.id} className="rounded-lg border border-slate-700 p-3 space-y-2 text-sm">
      <div className="flex justify-between gap-2"><strong>Observation #{item.sighting_id} · {item.status.replace(/_/g, ' ')}</strong><time>{new Date(item.observed_at).toLocaleString()}</time></div>
      {fields.map(field => <p key={field} className="text-xs"><span className="capitalize">{field.replace('_', ' ')}</span>: observed {item.observed[field] || 'unknown'} · registered {item.expected[field] || 'unavailable'} · {item.comparisons[field]}</p>)}
      {item.risk_status !== 'NONE' && <p className="text-amber-300">Risk review: {item.risk_status.replace(/_/g, ' ')}</p>}
      {item.reviewed_by && <p className="text-xs text-slate-400">Reviewed by {item.reviewed_by}: {item.review_notes}</p>}
      {canReview && !item.reviewed_at && (editing === item.id ? <div className="space-y-2">
        <div className="grid sm:grid-cols-3 gap-2">{(['make', 'model', 'color'] as const).map(field => <label key={field} className="text-xs capitalize">Observed {field}<input className={input} value={form[field]} onChange={e => setForm({ ...form, [field]: e.target.value })} /></label>)}</div>
        <label className="text-xs">Evidence notes<textarea className={input} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} /></label>
        <div className="flex gap-2"><button className="rounded bg-amber-700 px-3 py-1 disabled:opacity-40" disabled={form.notes.trim().length < 10} onClick={() => void review(item, 'CONFIRMED_MISMATCH')}>Confirm mismatch</button>
          <button className="rounded bg-slate-700 px-3 py-1 disabled:opacity-40" disabled={form.notes.trim().length < 10} onClick={() => void review(item, 'DISMISSED')}>Dismiss</button>
          <button className="rounded border border-slate-600 px-3 py-1" onClick={() => setEditing(null)}>Cancel</button></div>
      </div> : <button className="rounded border border-slate-600 px-3 py-1" onClick={() => { setEditing(item.id); setForm({ make: item.observed.make || '', model: item.observed.model || '', color: item.observed.color || '', notes: '' }); }}>Review attributes</button>)}
    </article>)}
  </section>;
}
