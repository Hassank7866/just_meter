import React, { useEffect, useState } from 'react';
import { downloadReport, governanceRequest, User } from '../api/client';

type Department = { id: number; name: string };
const field = 'rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm';
const button = 'rounded border border-sky-700 bg-sky-950 px-3 py-2 text-sm disabled:opacity-50';
const errorText = (error: unknown) => error instanceof Error ? error.message : 'Request failed';

export function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const empty = { email: '', name: '', role: 'Transport Officer', department_id: null as number | null, active: true, password: '' };
  const [form, setForm] = useState(empty);
  const [selected, setSelected] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  async function load() {
    const [accounts, groups] = await Promise.all([governanceRequest<User[]>('users'), governanceRequest<Department[]>('departments')]);
    setUsers(accounts); setDepartments(groups);
  }
  useEffect(() => { load().catch(e => setError(errorText(e))); }, []);
  async function save(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      await governanceRequest(selected ? `users/${selected}` : 'users', selected ? 'PUT' : 'POST',
        { ...form, password: form.password || undefined });
      setSelected(null); setForm(empty); await load(); setMessage('Account saved. Previous sessions for this account have been revoked.');
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  function edit(user: User) {
    setSelected(user.id!); setMessage(''); setError('');
    setForm({ email: user.email, name: user.name, role: user.role, department_id: user.department_id || null, active: user.active !== false, password: '' });
  }
  return <section className="p-5 space-y-4">
    <h1 className="text-xl font-semibold">User access</h1>
    <p className="text-sm text-slate-400">Assign officers to a department. Auditors can read platform reports and audit history. Administrators manage the whole platform.</p>
    {error && <p role="alert" className="text-rose-300">{error}</p>}
    {message && <p role="status" className="text-emerald-300">{message}</p>}
    <form onSubmit={save} className="grid sm:grid-cols-2 gap-3 rounded-xl border border-slate-800 p-4">
      <h2 className="sm:col-span-2 font-medium">{selected ? 'Edit account' : 'Create account'}</h2>
      <label className="grid gap-1 text-sm">Name<input required maxLength={200} className={field} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></label>
      <label className="grid gap-1 text-sm">Email<input required type="email" disabled={selected !== null} className={field} value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} /></label>
      <label className="grid gap-1 text-sm">Role<select className={field} value={form.role} onChange={e => setForm({ ...form, role: e.target.value, department_id: null })}>
        {['Administrator', 'Transport Officer', 'Supervisory Officer', 'Auditor'].map(role => <option key={role}>{role}</option>)}
      </select></label>
      <label className="grid gap-1 text-sm">Department<select className={field} disabled={['Administrator', 'Auditor'].includes(form.role)} required={!['Administrator', 'Auditor'].includes(form.role)} value={form.department_id || ''} onChange={e => setForm({ ...form, department_id: Number(e.target.value) || null })}>
        <option value="">Select department</option>{departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
      </select></label>
      <label className="grid gap-1 text-sm">{selected ? 'New password (optional)' : 'Password'}<input type="password" autoComplete="new-password" required={!selected} minLength={10} maxLength={72} className={field} value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} /></label>
      <label className="flex gap-2 items-center text-sm"><input type="checkbox" checked={form.active} onChange={e => setForm({ ...form, active: e.target.checked })} />Account active</label>
      <div className="flex gap-2"><button disabled={busy} className={button}>{busy ? 'Saving…' : 'Save account'}</button>{selected && <button type="button" className={field} onClick={() => { setSelected(null); setForm(empty); }}>Cancel</button>}</div>
    </form>
    <div className="overflow-x-auto"><table className="w-full text-sm text-left"><thead><tr>{['Account', 'Role', 'Department', 'Status', 'Actions'].map(t => <th key={t} className="p-2">{t}</th>)}</tr></thead><tbody>
      {users.map(u => <tr key={u.id} className="border-t border-slate-800"><td className="p-2">{u.name}<br /><span className="text-slate-400">{u.email}</span></td><td className="p-2">{u.role}</td><td className="p-2">{u.department || (['Administrator', 'Auditor'].includes(u.role) ? 'Platform oversight' : 'Unassigned')}</td><td className="p-2">{u.active ? 'Active' : 'Disabled'}</td><td className="p-2 flex gap-2"><button className={button} onClick={() => edit(u)}>Edit</button><button disabled={busy} className={field} onClick={async () => { setBusy(true); setError(''); try { await governanceRequest(`users/${u.id}/revoke`, 'POST'); setMessage(`Sessions revoked for ${u.email}.`); } catch (e) { setError(errorText(e)); } finally { setBusy(false); } }}>Revoke sessions</button></td></tr>)}
    </tbody></table></div>
  </section>;
}

type Report = { start_date: string; end_date: string; timezone: string; notes: string;
  summary: Record<string, number>; departments: { department: string; sightings: number; violations: number; compliance_rate: number | null; rank: number | null }[] };

export function ReportsPage() {
  const [period, setPeriod] = useState('monthly');
  const [anchor, setAnchor] = useState(() => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Karachi' }).format(new Date()));
  const [department, setDepartment] = useState('');
  const [departments, setDepartments] = useState<Department[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const params = () => new URLSearchParams({ period, anchor, department });
  useEffect(() => { governanceRequest<Department[]>('departments').then(setDepartments).catch(e => setError(errorText(e))); }, []);
  useEffect(() => { setReport(null); }, [period, anchor, department]);
  async function run(format?: 'csv' | 'pdf') {
    setBusy(true); setError('');
    try { if (format) await downloadReport(params(), format); else setReport(await governanceRequest<Report>(`reports/compliance?${params()}`)); }
    catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  return <section className="p-5 space-y-4"><h1 className="text-xl font-semibold">Compliance reports</h1>
    <p className="text-sm text-slate-400">Daily, weekly and monthly reports use Pakistan time and your permitted departments. Weeks run Monday to Sunday.</p>
    <div className="flex flex-wrap gap-3"><label className="grid gap-1 text-sm">Period<select className={field} value={period} onChange={e => setPeriod(e.target.value)}>{['daily', 'weekly', 'monthly'].map(p => <option key={p}>{p}</option>)}</select></label>
      <label className="grid gap-1 text-sm">Date within period<input className={field} type="date" value={anchor} onChange={e => setAnchor(e.target.value)} /></label>
      <label className="grid gap-1 text-sm">Department<select className={field} value={department} onChange={e => setDepartment(e.target.value)}><option value="">All accessible departments</option>{departments.map(d => <option key={d.id}>{d.name}</option>)}</select></label>
      <div className="flex items-end gap-2"><button disabled={busy || !anchor} className={button} onClick={() => run()}>Generate</button>{(['csv', 'pdf'] as const).map(format => <button key={format} disabled={busy || !anchor} className={field} onClick={() => run(format)}>Export {format.toUpperCase()}</button>)}</div>
    </div>
    {busy && <p role="status">Preparing report…</p>}{error && <p role="alert" className="text-rose-300">{error}</p>}
    {report && <><p>{report.start_date} – {report.end_date} ({report.timezone})</p><div className="grid sm:grid-cols-3 gap-3">{Object.entries(report.summary).map(([key, value]) => <div key={key} className="rounded border border-slate-800 p-3"><p className="text-xs text-slate-400">{key.replace(/_/g, ' ')}</p><p className="text-xl">{value}</p></div>)}</div>
      <table className="w-full text-sm text-left"><thead><tr>{['Department', 'Sightings', 'Violations', 'Lawful %', 'Rank'].map(label => <th className="p-2" key={label}>{label}</th>)}</tr></thead><tbody>{report.departments.map(row => <tr className="border-t border-slate-800" key={row.department}><td className="p-2">{row.department}</td><td>{row.sightings}</td><td>{row.violations}</td><td>{row.compliance_rate ?? 'N/A'}</td><td>{row.rank ?? 'N/A'}</td></tr>)}</tbody></table><p className="text-xs text-slate-400">{report.notes}</p></>}
  </section>;
}

type AuditRow = { id: number; at: string; actor: string; action: string; entity: string; details: unknown };
export function AuditPage() {
  const [rows, setRows] = useState<AuditRow[]>([]), [total, setTotal] = useState(0), [offset, setOffset] = useState(0);
  const [actor, setActor] = useState(''), [action, setAction] = useState(''), [start, setStart] = useState(''), [end, setEnd] = useState('');
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  async function load(next = 0) {
    setBusy(true); setError('');
    const params = new URLSearchParams({ limit: '50', offset: String(next), actor, action });
    if (start) params.set('start_date', start); if (end) params.set('end_date', end);
    try { const result = await governanceRequest<{ total: number; items: AuditRow[] }>(`audit?${params}`); setRows(result.items); setTotal(result.total); setOffset(next); }
    catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  useEffect(() => { load(); }, []);
  return <section className="p-5 space-y-4"><h1 className="text-xl font-semibold">Audit history</h1><p className="text-sm text-slate-400">Access outcomes and recorded changes. Entries cannot be edited or deleted.</p>
    <form className="flex flex-wrap gap-2" onSubmit={e => { e.preventDefault(); load(); }}><label className="grid text-sm gap-1">Actor email<input className={field} value={actor} onChange={e => setActor(e.target.value)} /></label><label className="grid text-sm gap-1">Action<input className={field} value={action} onChange={e => setAction(e.target.value)} placeholder="e.g. LOGIN" /></label><label className="grid text-sm gap-1">From<input className={field} type="date" value={start} onChange={e => setStart(e.target.value)} /></label><label className="grid text-sm gap-1">To<input className={field} type="date" value={end} onChange={e => setEnd(e.target.value)} /></label><button className={button} disabled={busy}>Filter</button></form>
    {error && <p role="alert" className="text-rose-300">{error}</p>}
    <div className="overflow-x-auto"><table className="w-full text-sm text-left"><thead><tr>{['Time', 'Actor', 'Action', 'Record', 'Details'].map(t => <th key={t} className="p-2">{t}</th>)}</tr></thead><tbody>{rows.map(row => <tr key={row.id} className="border-t border-slate-800"><td className="p-2 whitespace-nowrap">{new Date(row.at).toLocaleString('en-PK', { timeZone: 'Asia/Karachi' })}</td><td className="p-2">{row.actor}</td><td className="p-2">{row.action}</td><td className="p-2 break-all">{row.entity}</td><td className="p-2"><details><summary className="cursor-pointer">View</summary><pre className="whitespace-pre-wrap max-w-md text-xs">{JSON.stringify(row.details, null, 2)}</pre></details></td></tr>)}</tbody></table></div>
    <div className="flex gap-3 items-center"><button className={field} disabled={busy || offset === 0} onClick={() => load(Math.max(0, offset - 50))}>Previous</button><span>{total ? offset + 1 : 0}–{Math.min(offset + 50, total)} of {total}</span><button className={field} disabled={busy || offset + 50 >= total} onClick={() => load(offset + 50)}>Next</button></div>
  </section>;
}
