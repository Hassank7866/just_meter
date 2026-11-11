import React, { useEffect, useState } from 'react';
import { authenticatedResourceUrl, challanRequest, ChallanCase, fetchTwinVehicles, sendViolationNotification,
  snapshotUrl, TwinVehicle } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { VehicleProfileLink } from '../components/VehicleProfileLink';

export interface ChallanSelection { vehicleId?: number; caseId?: number }
const button = 'rounded-lg border border-slate-600 px-3 py-2 text-sm hover:bg-slate-800 disabled:opacity-40';
const input = 'rounded-lg bg-slate-950 border border-slate-700 p-2 text-sm w-full';
const box = 'rounded-xl border border-slate-800 bg-slate-900/70 p-4 space-y-3';

export const ChallansPage: React.FC<{ selection?: ChallanSelection | null }> = ({ selection }) => {
  const { user } = useAuth();
  const writable = !!user && user.role !== 'Auditor';
  const supervisor = user?.role === 'Administrator' || user?.role === 'Supervisory Officer';
  const [vehicleId, setVehicleId] = useState<number | undefined>(selection?.vehicleId);
  const [selectedId, setSelectedId] = useState<number | undefined>(selection?.caseId);
  const [query, setQuery] = useState('');
  const [vehicles, setVehicles] = useState<TwinVehicle[]>([]);
  const [status, setStatus] = useState('');
  const [offset, setOffset] = useState(0);
  const [cases, setCases] = useState<{ total: number; items: ChallanCase[] }>({ total: 0, items: [] });
  const [detail, setDetail] = useState<ChallanCase | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [notes, setNotes] = useState('');
  const [fine, setFine] = useState('');
  const [recipient, setRecipient] = useState('');
  const [channel, setChannel] = useState<'email' | 'whatsapp_direct'>('email');
  useEffect(() => { setVehicleId(selection?.vehicleId); setSelectedId(selection?.caseId); setOffset(0); }, [selection]);
  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => fetchTwinVehicles(query, 0, controller.signal).then(r => setVehicles(r.items))
      .catch(e => { if (!controller.signal.aborted) setError(e.message); }), 200);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [query]);
  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ limit: '20', offset: String(offset) });
    if (status) params.set('status', status);
    if (vehicleId) params.set('vehicle_id', String(vehicleId));
    challanRequest<{ total: number; items: ChallanCase[] }>(`?${params}`, undefined, controller.signal)
      .then(setCases).catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [vehicleId, status, offset, refresh]);
  useEffect(() => {
    setDetail(null); setNotes('');
    if (!selectedId) return;
    const controller = new AbortController();
    challanRequest<ChallanCase>(`/${selectedId}`, undefined, controller.signal).then(data => {
      setDetail(data); setFine(String(data.fine_amount));
    }).catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [selectedId, refresh]);

  async function perform(operation: () => Promise<unknown>) {
    setBusy(true); setError(''); setNotice('');
    try { await operation(); setRefresh(v => v + 1); } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function action(actionName: string) {
    if (!detail) return;
    if (notes.trim().length < 10) { setError('Enter at least 10 characters explaining the decision or appeal.'); return; }
    await perform(async () => {
      await challanRequest(`/${detail.id}/actions`, { action: actionName, expected_version: detail.version,
        notes, ...(actionName === 'approve' ? { review_fingerprint: detail.review_fingerprint } : {}),
        ...(actionName === 'amend' ? { fine_amount: Number(fine) } : {}) });
      setNotice('Case action recorded.');
    });
  }
  const snapshot = detail?.status === 'DRAFT' ? detail.review_snapshot : detail?.snapshot;
  return <div className="p-4 sm:p-6 space-y-5">
    <header><h1 className="text-2xl font-bold">Digital Challan Register</h1>
      <p className="text-sm text-slate-400">Draft, independent approval, issuance and appeal history. Four confirmed violations establish eligibility; issuance requires officer action.</p></header>
    {error && <p role="alert" className="rounded-lg bg-red-950/40 text-red-300 p-3">{error}</p>}
    {notice && <p role="status" className="text-emerald-300">{notice}</p>}
    <div className={`${box} grid sm:grid-cols-2 gap-3`}>
      <label className="text-sm">Find vehicle<input className={input} value={query} placeholder="Plate or fleet ID" onChange={e => setQuery(e.target.value)} /></label>
      <label className="text-sm">Vehicle filter<select className={input} value={vehicleId || ''} onChange={e => { setVehicleId(Number(e.target.value) || undefined); setOffset(0); }}>
        <option value="">All vehicles</option>{vehicleId && !vehicles.some(v => v.id === vehicleId) && <option value={vehicleId}>Selected vehicle #{vehicleId}</option>}
        {vehicles.map(v => <option key={v.id} value={v.id}>{v.plate_number} · {v.vehicle_id}</option>)}</select></label>
      <label className="text-sm">Status<select className={input} value={status} onChange={e => { setStatus(e.target.value); setOffset(0); }}>
        <option value="">All statuses</option>{['DRAFT', 'APPROVED', 'ISSUED', 'APPEALED', 'UPHELD', 'CANCELLED', 'REJECTED'].map(s => <option key={s}>{s}</option>)}</select></label>
      <div className="flex flex-wrap gap-2 items-end"><button className={button} disabled={busy} onClick={() => setRefresh(v => v + 1)}>Refresh</button>
        {writable && <button className={button} disabled={!vehicleId || busy} onClick={() => void perform(async () => {
          const result = await challanRequest<ChallanCase>('', { vehicle_id: vehicleId });
          setSelectedId(result.id); setNotice('Draft opened for the latest eligible observation.');
        })}>Create / open latest draft</button>}</div>
      <p className="text-xs text-slate-400 sm:col-span-2">New eligible detections create drafts automatically. Use the button for existing historical observations. The prototype fine starts at PKR 2,500 with PKR 1,000 per additional observation; a draft amendment requires a recorded reason.</p>
    </div>
    <div className="grid lg:grid-cols-[280px_minmax(0,1fr)] gap-5">
      <aside className={box}><p>{cases.total} cases</p>
        {!cases.items.length && <p className="text-sm text-slate-400">No cases match these filters.</p>}
        {cases.items.map(c => <button key={c.id} className={`${button} block w-full text-left ${selectedId === c.id ? 'border-sky-500' : ''}`} onClick={() => setSelectedId(c.id)}>
          <span className="block text-xs font-mono break-all">{c.reference}</span><span>{c.snapshot.plate_number} · {c.status}</span></button>)}
        <div className="flex gap-2"><button className={button} disabled={!offset} onClick={() => setOffset(v => v - 20)}>Previous</button>
          <button className={button} disabled={offset + 20 >= cases.total} onClick={() => setOffset(v => v + 20)}>Next</button></div>
      </aside>
      <section className="space-y-4 min-w-0">
        {!detail && <p className={box}>{selectedId ? 'Loading case…' : 'Select a case to review its evidence and history.'}</p>}
        {detail && snapshot && <>
          <div className={box}><h2 className="font-semibold text-lg break-all">{detail.reference}</h2>
            <p>{detail.status} · Version {detail.version} · PKR {detail.fine_amount.toLocaleString()}</p>
            <p>{snapshot.plate_number} · Department at capture: {snapshot.department || 'Unknown'}</p>
            <p className="text-sm">Charged observation #{detail.sighting_id} · {snapshot.total_violations} supporting confirmed observations</p>
            <VehicleProfileLink reference={{ id: detail.vehicle_id }} />
            <p className="text-xs text-slate-400">Prepared by {detail.prepared_by}; approved by {detail.approved_by || 'Pending'}; issued by {detail.issued_by || 'Pending'}</p>
            {detail.issued_at && <p className="text-sm">Issued: {new Date(detail.issued_at).toLocaleString()} · Due: {new Date(detail.due_at!).toLocaleString()}</p>}
            {detail.document_sha256 && (user?.role === 'Administrator' || detail.snapshot.image_policy === 'plate_crop') && <><a className="text-sky-400 underline" href={authenticatedResourceUrl(`/api/challans/${detail.id}/pdf`)} target="_blank" rel="noreferrer">Open original issued PDF</a>
              <p className="text-xs text-slate-400 break-all">Archived PDF SHA-256: {detail.document_sha256}</p></>}
            {detail.changed_since_approval && <p className="text-amber-300 text-sm">Current case inputs differ from the approval snapshot. The original issued document remains in the archive. Review the discrepancy before further action.</p>}
          </div>
          <div className={box}><h3 className="font-semibold">{detail.status === 'DRAFT' ? 'Current review evidence' : 'Approval snapshot'}</h3>
            {snapshot.violations_history.map((v, index) => <p key={index} className="text-xs">{String(v.timestamp || '')} · {String(v.plate_number || '')} · {String(v.violation_criteria || '')}</p>)}
            {!snapshot.evidence.length && <p className="text-amber-300">No linked evidence. Approval requires verified evidence for the charged observation.</p>}
            {snapshot.evidence.map(e => <div key={e.id} className="border-t border-slate-800 pt-2 text-sm"><p>{e.evidence_id} · {e.review_status}</p>
              {(user?.role === 'Administrator' || e.plate_crop) && <a className="text-sky-400 underline" href={snapshotUrl(user?.role === 'Administrator' ? e.full_image : e.plate_crop!)} target="_blank" rel="noreferrer">Review archived {user?.role === 'Administrator' ? 'image' : 'plate crop'}</a>}<p className="text-xs break-all text-slate-500">{e.full_image_sha256}</p></div>)}
            <p className="text-xs text-slate-400">Complete evidence review in the Evidence screen before approving. Files are checked again at approval and issuance.</p>
          </div>
          {writable && <div className={box}><label className="text-sm">Decision / appeal reasons<textarea className={input} value={notes} minLength={10} maxLength={2000}
            placeholder="Record evidence, rationale or appellant details and appeal grounds" onChange={e => setNotes(e.target.value)} /></label>
            <div className="flex flex-wrap gap-2">
              {detail.status === 'DRAFT' && supervisor && <button className={button} disabled={busy || detail.prepared_by === user?.email} onClick={() => void action('approve')}>Approve</button>}
              {['DRAFT', 'APPROVED'].includes(detail.status) && supervisor && <button className={button} disabled={busy} onClick={() => void action('reject')}>Reject</button>}
              {['APPROVED', 'REJECTED'].includes(detail.status) && supervisor && <button className={button} disabled={busy} onClick={() => void action('reopen')}>Return to draft</button>}
              {detail.status === 'APPROVED' && <button className={button} disabled={busy || detail.changed_since_approval} onClick={() => void action('issue')}>Issue challan</button>}
              {detail.status === 'ISSUED' && <button className={button} disabled={busy} onClick={() => void action('appeal')}>Record appeal</button>}
              {detail.status === 'APPEALED' && supervisor && <button className={button} disabled={busy} onClick={() => void action('uphold')}>Dismiss appeal / uphold</button>}
              {['ISSUED', 'APPEALED', 'UPHELD'].includes(detail.status) && supervisor && <button className={button} disabled={busy} onClick={() => void action('cancel')}>Cancel challan</button>}
            </div>
            {detail.status === 'DRAFT' && (user?.role === 'Administrator' || user?.role === 'Transport Officer') && <div className="flex gap-2"><label className="text-xs">Proposed fine (PKR)<input type="number" min="0" max="1000000" className={input} value={fine} onChange={e => setFine(e.target.value)} /></label>
              <button className={button} disabled={busy || !fine} onClick={() => void action('amend')}>Amend draft fine</button></div>}
            <p className="text-xs text-slate-400">The preparer cannot approve their own case. An uninvolved supervisory officer must decide an appeal. Appeals suspend sending; cancellation retains the original PDF.</p>
          </div>}
          {supervisor && ['ISSUED', 'UPHELD'].includes(detail.status) && <form className={box} onSubmit={e => { e.preventDefault(); void perform(async () => {
            const response = await sendViolationNotification({ plate_number: detail.snapshot.plate_number, challan_id: detail.reference,
              message_type: 'challan', channel, ...(channel === 'email' ? { recipient_email: recipient } : { recipient_phone: recipient }) });
            setNotice(response.message || 'Delivery request completed.');
          }); }}><h3 className="font-semibold">Send issued document</h3><select aria-label="Delivery channel" className={input} value={channel} onChange={e => setChannel(e.target.value as typeof channel)}><option value="email">Email</option><option value="whatsapp_direct">WhatsApp</option></select>
            <input aria-label="Recipient" type={channel === 'email' ? 'email' : 'tel'} required className={input} value={recipient} onChange={e => setRecipient(e.target.value)} placeholder="Recipient address / phone" />
            <button className={button} disabled={busy}>Send issued PDF</button></form>}
          <div className={box}><h3 className="font-semibold">Case action history</h3>{detail.history?.map(event => <div key={event.id} className="border-t border-slate-800 pt-2 text-sm">
            <p>{event.action} · {event.actor} · {new Date(event.at).toLocaleString()}</p><p className="text-slate-400">{String(event.details.notes || event.details.outcome || '')}</p>
          </div>)}</div>
        </>}
      </section>
    </div>
  </div>;
};
