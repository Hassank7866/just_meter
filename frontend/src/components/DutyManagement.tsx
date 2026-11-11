import React, { useEffect, useState } from 'react';
import { DutyCoverage, DutyObservation, DutyVerification, dutyRequest, snapshotUrl } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { DutyVerificationPanel } from './DutyVerificationPanel';

const input = 'rounded border border-slate-700 bg-slate-950 p-2 text-sm max-w-full';
const button = 'rounded border border-slate-600 px-3 py-2 text-sm disabled:opacity-40 hover:bg-slate-800';

export const DutyManagement: React.FC = () => {
  const { user } = useAuth();
  const admin = user?.role === 'Administrator';
  const reviewer = admin || user?.role === 'Supervisory Officer';
  const [coverage, setCoverage] = useState<DutyCoverage[]>([]);
  const [source, setSource] = useState('');
  const [from, setFrom] = useState(''); const [until, setUntil] = useState('');
  const [maxAge, setMaxAge] = useState(72);
  const [observations, setObservations] = useState<{ total: number; items: DutyObservation[] }>({ total: 0, items: [] });
  const [offset, setOffset] = useState(0); const [pending, setPending] = useState(true);
  const [refresh, setRefresh] = useState(0); const [busy, setBusy] = useState(false);
  const [error, setError] = useState(''); const [notice, setNotice] = useState('');
  const [selected, setSelected] = useState<number | null>(null);
  const [destination, setDestination] = useState('UNRESOLVED'); const [purpose, setPurpose] = useState('UNRESOLVED');
  const [notes, setNotes] = useState('');
  const [plate, setPlate] = useState(''); const [at, setAt] = useState(''); const [area, setArea] = useState('');
  const [check, setCheck] = useState<DutyVerification | null>(null);

  useEffect(() => {
    let current = true;
    Promise.all([dutyRequest<DutyCoverage[]>('coverage'), dutyRequest<{ total: number; items: DutyObservation[] }>(`observations?pending=${pending}&limit=10&offset=${offset}`)])
      .then(([c, o]) => { if (current) { setCoverage(c); setObservations(o); } })
      .catch(e => { if (current) setError(e.message); });
    return () => { current = false; };
  }, [refresh, offset, pending]);

  const perform = async (action: () => Promise<void>) => {
    setBusy(true); setError(''); setNotice('');
    try { await action(); } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };

  return <section className="rounded-xl border border-slate-700 p-4 space-y-4">
    <div className="flex justify-between gap-2"><h2 className="font-semibold">Duty verification</h2><button className={button} disabled={busy} onClick={() => setRefresh(v => v + 1)}>Refresh duty data</button></div>
    <p className="text-sm text-slate-400">Checks use the source snapshot at capture time. Missing or stale coverage requires review. A matching area alone cannot confirm arrival or trip purpose.</p>
    {error && <p role="alert" className="text-sm text-red-300">{error}</p>}{notice && <p role="status" className="text-sm text-emerald-300">{notice}</p>}
    <div className="space-y-1">{coverage.map(c => <p key={c.source} className="text-xs">{c.source} · revision {c.revision} · {c.confirmed ? 'Coverage confirmed' : 'Coverage confirmation needed'}{c.coverage && ` · ${new Date(c.coverage.valid_from).toLocaleString()} to ${new Date(c.coverage.valid_until).toLocaleString()}`}</p>)}</div>
    {admin && <details><summary className="cursor-pointer text-sm">Confirm complete source coverage</summary>
      <p className="text-xs text-amber-300 my-2">Confirm only after checking that all assignments and duty slips for this period are present. This enables missing-authorization violations. Each new import requires confirmation again.</p>
      <form className="flex flex-wrap gap-2 items-end" onSubmit={e => { e.preventDefault(); void perform(async () => {
        const selectedSource = coverage.find(c => c.source === source); if (!selectedSource) throw new Error('Select a source');
        await dutyRequest(`coverage/${encodeURIComponent(source)}`, 'PUT', { expected_revision: selectedSource.revision,
          valid_from: new Date(from).toISOString(), valid_until: new Date(until).toISOString(), max_age_hours: maxAge });
        setRefresh(v => v + 1); setNotice('Source coverage confirmed for the selected revision.');
      }); }}>
        <label className="text-xs">Source<select className={`block ${input}`} required value={source} onChange={e => setSource(e.target.value)}><option value="">Select source</option>{coverage.map(c => <option key={c.source}>{c.source}</option>)}</select></label>
        <label className="text-xs">From (local time)<input className={`block ${input}`} type="datetime-local" required value={from} onChange={e => setFrom(e.target.value)} /></label>
        <label className="text-xs">Until (exclusive)<input className={`block ${input}`} type="datetime-local" required value={until} onChange={e => setUntil(e.target.value)} /></label>
        <label className="text-xs">Maximum export age (hours)<input className={`block w-24 ${input}`} type="number" min={1} max={720} required value={maxAge} onChange={e => setMaxAge(Number(e.target.value))} /></label>
        <button className={button} disabled={busy}>Confirm completeness</button>
      </form></details>}
    <details><summary className="cursor-pointer text-sm">Check a plate and capture time</summary>
      <form className="flex flex-wrap gap-2 my-2" onSubmit={e => { e.preventDefault(); void perform(async () => {
        const query = new URLSearchParams({ plate, observed_at: new Date(at).toISOString(), camera_area: area });
        setCheck(await dutyRequest<DutyVerification>(`check?${query}`));
      }); }}><input className={input} aria-label="Plate" placeholder="Plate" required value={plate} onChange={e => setPlate(e.target.value)} />
        <input className={input} aria-label="Capture time in local timezone" type="datetime-local" required value={at} onChange={e => setAt(e.target.value)} />
        <input className={input} aria-label="Camera area" placeholder="Camera area (exact approved label)" required value={area} onChange={e => setArea(e.target.value)} />
        <button className={button} disabled={busy}>Check without saving</button></form><DutyVerificationPanel duty={check} />
    </details>
    <div className="flex flex-wrap gap-3 items-center"><h3 className="font-semibold text-sm">Observed duty decisions</h3><label className="text-xs"><input type="checkbox" checked={pending} onChange={e => { setPending(e.target.checked); setOffset(0); }} /> Review needed only</label><span className="text-xs text-slate-400">{observations.total} observations</span></div>
    {!observations.items.length && <p className="text-sm text-slate-400">No matching observations. New accepted vehicle detections will appear here.</p>}
    {observations.items.map(o => <div key={o.id} className="rounded-lg bg-slate-900 p-3 space-y-2">
      <p className="text-sm">{o.plate_number} · {new Date(o.timestamp).toLocaleString()} · {o.camera_area} · {o.status}</p>
      <a className="text-xs text-sky-300 underline" href={snapshotUrl(o.image)} target="_blank" rel="noreferrer">Open captured evidence</a>
      <DutyVerificationPanel duty={o.duty_verification} />
      {reviewer && o.duty_verification.reviewable.length > 0 && !o.duty_verification.review && <button className={button} disabled={busy} onClick={() => { setSelected(o.id); setDestination('UNRESOLVED'); setPurpose('UNRESOLVED'); setNotes(''); }}>Review destination and purpose</button>}
      {selected === o.id && <form className="space-y-2" onSubmit={e => { e.preventDefault(); void perform(async () => {
        await dutyRequest(`observations/${o.id}/review`, 'POST', { destination, purpose, notes });
        setSelected(null); setRefresh(v => v + 1); setNotice('Officer decision saved; compliance, risk and linked evidence updated.');
      }); }}>
        <p className="text-xs text-amber-300">Record what supporting evidence establishes. This final review is audited and cannot be submitted twice.</p>
        <div className="flex flex-wrap gap-2">{[{ label: 'Destination', value: destination, setter: setDestination }, { label: 'Purpose', value: purpose, setter: setPurpose }].map(({ label, value, setter }) => <label key={label} className="text-xs">{label}<select className={`block ${input}`} value={value} onChange={e => setter(e.target.value)}><option value="UNRESOLVED">Select conclusion</option><option value="MATCH">Matches approved duty</option><option value="MISMATCH">Does not match</option></select></label>)}</div>
        <textarea className={`w-full ${input}`} aria-label="Duty review evidence and reasons" placeholder="Evidence and reasons for your conclusion" required minLength={10} maxLength={2000} value={notes} onChange={e => setNotes(e.target.value)} />
        <button className={button} disabled={busy}>Save final decision</button><button type="button" className={`${button} ml-2`} onClick={() => setSelected(null)}>Cancel</button>
      </form>}
    </div>)}
    <div className="flex gap-2"><button className={button} disabled={offset === 0 || busy} onClick={() => setOffset(v => Math.max(0, v - 10))}>Previous</button><button className={button} disabled={offset + 10 >= observations.total || busy} onClick={() => setOffset(v => v + 10)}>Next</button></div>
  </section>;
};
