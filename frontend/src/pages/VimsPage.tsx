import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { DutyManagement } from '../components/DutyManagement';
import { authenticatedResourceUrl, vimsRequest, VimsChange, VimsKind, VimsRecord, VimsRun, VimsSource } from '../api/client';

const labels: Record<VimsKind, string> = { departments: 'Departments', vehicles: 'Vehicles', drivers: 'Drivers', assignments: 'Assignments', duty_slips: 'Duty slips' };
const button = 'rounded-lg border border-slate-600 px-3 py-2 text-sm hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed';
const field = 'rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm';
const format = (value: unknown): string => value == null ? '—' : Array.isArray(value) ? value.join(', ') : typeof value === 'boolean' ? value ? 'Yes' : 'No' : String(value);

function Changes({ changes }: { changes: VimsChange[] }) {
  return <div className="max-h-96 overflow-auto space-y-2">{changes.map((change) => <details key={`${change.kind}:${change.external_id}`} className="rounded-lg border border-slate-700 p-3">
    <summary className="cursor-pointer text-sm">{labels[change.kind]} · {change.external_id} · {change.operation}</summary>
    <div className="overflow-x-auto"><table className="w-full mt-2 text-xs text-left"><thead><tr><th className="p-2">Field</th><th className="p-2">Before</th><th className="p-2">After</th></tr></thead><tbody>
      {Object.entries(change.after).filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(change.before?.[key])).map(([key, value]) => <tr key={key} className="border-t border-slate-800"><td className="p-2">{key.replace(/_/g, ' ')}</td><td className="p-2">{format(change.before?.[key])}</td><td className="p-2">{format(value)}</td></tr>)}
    </tbody></table></div>
  </details>)}</div>;
}

export const VimsPage: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'Administrator';
  const [sources, setSources] = useState<VimsSource[]>([]);
  const [runs, setRuns] = useState<{ total: number; items: VimsRun[] }>({ total: 0, items: [] });
  const [historyOffset, setHistoryOffset] = useState(0);
  const [records, setRecords] = useState<{ total: number; items: VimsRecord[] }>({ total: 0, items: [] });
  const [kind, setKind] = useState<VimsKind>('vehicles');
  const [source, setSource] = useState('');
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [batch, setBatch] = useState<unknown>(null);
  const [filename, setFilename] = useState('');
  const [preview, setPreview] = useState<VimsRun | null>(null);
  const [detail, setDetail] = useState<VimsRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    let current = true;
    Promise.all([vimsRequest<VimsSource[]>('sources'), vimsRequest<{ total: number; items: VimsRun[] }>(`runs?limit=10&offset=${historyOffset}`)])
      .then(([s, r]) => { if (current) { setSources(s); setRuns(r); } })
      .catch(e => { if (current) setError(String(e.message)); });
    return () => { current = false; };
  }, [refresh, historyOffset]);

  useEffect(() => {
    let current = true;
    setRecords({ total: 0, items: [] });
    vimsRequest<{ total: number; items: VimsRecord[] }>(`records/${kind}?limit=20&offset=${offset}&source=${encodeURIComponent(source)}`)
      .then(r => { if (current) setRecords(r); }).catch(e => { if (current) setError(String(e.message)); });
    return () => { current = false; };
  }, [kind, source, offset, refresh]);

  const validate = async () => {
    setBusy(true); setError(''); setNotice(''); setPreview(null);
    try { setPreview(await vimsRequest<VimsRun>('preview', batch)); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };
  const apply = async () => {
    if (!preview) return;
    setBusy(true); setError('');
    try {
      const result = await vimsRequest<VimsRun>('import', { batch, expected_revision: preview.base_revision });
      setPreview(null); setNotice(`${result.batch_id}: ${result.status === 'ALREADY_APPLIED' ? 'already imported; no duplicate records created.' : 'import applied successfully.'}`);
      setDetail(result);
    } catch (e) { setError((e as Error).message); setPreview(null); }
    finally { setBusy(false); setRefresh(v => v + 1); }
  };

  return <div className="p-4 sm:p-6 space-y-6">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-xl font-bold">VIMS synchronization</h1>
      <p className="mt-1 text-sm text-slate-400">Import department, vehicle, driver, assignment and duty-slip records from an offline export.</p>
      <p className="mt-1 text-xs text-amber-300">Offline imports and duty checks are available. Live institutional VIMS connections are pending.</p></div>
      <button className={button} disabled={busy} onClick={() => setRefresh(v => v + 1)}>Refresh</button></div>
    {error && <div role="alert" className="whitespace-pre-wrap rounded-lg border border-red-700 bg-red-950/30 p-3 text-sm text-red-200">{error}</div>}
    {notice && <div role="status" className="rounded-lg border border-emerald-700 p-3 text-sm text-emerald-300">{notice}</div>}
    {isAdmin && <section className="rounded-xl border border-slate-700 bg-slate-900/50 p-4 space-y-3">
      <h2 className="font-semibold">Preview an import</h2>
      <p className="text-sm text-slate-400">Choose a JSON export up to 5 MiB. Review changes before applying. Records omitted from a file are retained; cancellations and deactivations must be explicit.</p>
      <div className="flex flex-wrap items-center gap-3"><input aria-label="VIMS export file" type="file" accept=".json,application/json" disabled={busy} className="max-w-full text-sm" onChange={async e => {
        const file = e.target.files?.[0]; setBatch(null); setPreview(null); setFilename(''); setError(''); setNotice('');
        if (!file) return;
        setBusy(true);
        try { if (file.size > 5 * 1024 * 1024) throw new Error('Import exceeds the 5 MiB limit'); const data = JSON.parse(await file.text()); setBatch(data); setFilename(file.name); }
        catch (err) { setError((err as Error).message); } finally { setBusy(false); }
      }} />
      <a className="text-sm text-sky-300 underline" href={authenticatedResourceUrl('/api/vims/example')} download>Download sample export</a>
      <a className="text-sm text-sky-300 underline" href={authenticatedResourceUrl('/api/vims/schema')} target="_blank" rel="noreferrer">Import specification</a>
      <button className={button} disabled={!batch || busy} onClick={validate}>{busy ? 'Working…' : 'Validate and preview'}</button></div>
      <p className="text-xs text-slate-400">The sample contains fictional records and will create them only if you apply it. {filename && `Selected: ${filename}`}</p>
      {preview && <div className="space-y-3"><p className="text-sm">Source: <strong>{preview.source}</strong> · Batch: {preview.batch_id} · {preview.status === 'ALREADY_APPLIED' ? 'Already imported' : 'Ready for review'}</p>
        <div className="overflow-x-auto"><table className="w-full text-sm text-left"><thead><tr><th className="p-2">Records</th><th>New</th><th>Linked</th><th>Updated</th><th>Unchanged</th></tr></thead><tbody>{Object.entries(preview.summary).map(([key, count]) => <tr key={key} className="border-t border-slate-700"><td className="p-2">{labels[key as VimsKind]}</td><td>{count.created}</td><td>{count.linked}</td><td>{count.updated}</td><td>{count.unchanged}</td></tr>)}</tbody></table></div>
        <Changes changes={preview.changes || []} />
        {preview.status !== 'ALREADY_APPLIED' && <button className={`${button} bg-sky-900`} disabled={busy} onClick={apply}>Apply reviewed import</button>}
      </div>}
    </section>}
    <DutyManagement />
    <section className="space-y-3"><h2 className="font-semibold">Connected import sources</h2>
      {!sources.length ? <p className="text-sm text-slate-400">No source has been imported yet.</p> : <div className="grid gap-3 sm:grid-cols-2">{sources.map(s => <div key={s.id} className="rounded-lg border border-slate-700 p-3 text-sm"><strong>{s.name}</strong><p className="text-slate-400">Revision {s.revision} · Latest export: {s.exported_at ? new Date(s.exported_at).toLocaleString() : 'No successful import'}</p></div>)}</div>}
    </section>
    <section className="space-y-3"><div className="flex flex-wrap items-center gap-3"><h2 className="font-semibold">Imported records</h2>
      <select aria-label="Record category" className={field} value={kind} onChange={e => { setKind(e.target.value as VimsKind); setOffset(0); }}>{Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
      <select aria-label="Import source" className={field} value={source} onChange={e => { setSource(e.target.value); setOffset(0); }}><option value="">All sources</option>{sources.map(s => <option key={s.id} value={s.name}>{s.name}</option>)}</select>
      <span className="text-sm text-slate-400">{records.total} records</span></div>
      {!records.items.length && <p className="text-sm text-slate-400">No imported records in this category.</p>}
      <div className="grid gap-3 sm:grid-cols-2">{records.items.map(record => <details key={record.local_id} className="rounded-lg border border-slate-700 p-3"><summary className="cursor-pointer text-sm"><strong>{format(record.name || record.plate_number || record.external_id)}</strong> · {record.source}</summary>
        <dl className="mt-3 space-y-1 text-xs">{Object.entries(record).filter(([key]) => key !== 'local_id').map(([key, value]) => <div key={key} className="grid grid-cols-2 gap-2"><dt className="text-slate-400">{key.replace(/_/g, ' ')}</dt><dd className="break-words">{format(value)}</dd></div>)}</dl></details>)}</div>
      <div className="flex gap-2"><button className={button} disabled={offset === 0} onClick={() => setOffset(v => Math.max(0, v - 20))}>Previous</button><button className={button} disabled={offset + 20 >= records.total} onClick={() => setOffset(v => v + 20)}>Next</button></div>
    </section>
    <section className="space-y-3"><h2 className="font-semibold">Synchronization history</h2>
      {!runs.items.length && <p className="text-sm text-slate-400">No import attempts yet. Previews do not change the database.</p>}
      <div className="overflow-x-auto"><table className="w-full text-sm text-left"><thead><tr><th className="p-2">Batch / source</th><th>Time</th><th>Actor</th><th>Result</th><th>Changes</th></tr></thead><tbody>{runs.items.map(run => <tr key={run.id} className="border-t border-slate-700"><td className="p-2">{run.batch_id}<div className="text-xs text-slate-400">{run.source}</div></td><td>{run.occurred_at && new Date(run.occurred_at).toLocaleString()}</td><td>{run.actor}</td><td className={run.status === 'FAILED' ? 'text-red-300' : 'text-emerald-300'}>{run.status}</td><td><button className="text-sky-300 underline" onClick={async () => { try { setDetail(await vimsRequest<VimsRun>(`runs/${run.id}`)); } catch (e) { setError((e as Error).message); } }}>View</button></td></tr>)}</tbody></table></div>
      <div className="flex gap-2"><button className={button} disabled={historyOffset === 0} onClick={() => setHistoryOffset(v => Math.max(0, v - 10))}>Previous runs</button><button className={button} disabled={historyOffset + 10 >= runs.total} onClick={() => setHistoryOffset(v => v + 10)}>Next runs</button></div>
      {detail && <div className="rounded-lg border border-slate-700 p-3 space-y-3"><div className="flex justify-between"><h3>{detail.batch_id} · {detail.status}</h3><button className="text-sm underline" onClick={() => setDetail(null)}>Close details</button></div>{detail.error && <p className="text-red-300 text-sm">{detail.error}</p>}<Changes changes={detail.changes || []} /></div>}
    </section>
  </div>;
};
