import React, { useEffect, useRef, useState } from 'react';
import { Activity, ArrowRight, RefreshCw } from 'lucide-react';
import { acknowledgeRiskTask, ExecutiveDashboard, fetchExecutiveDashboard } from '../api/client';
import { useAuth } from '../context/AuthContext';

type Destination = 'authorized' | 'spotted' | 'violations';
const panel = 'rounded-xl border border-slate-800 bg-slate-900/70 p-4 sm:p-5';
const colors: Record<string, string> = {
  LOW: 'bg-emerald-400', MEDIUM: 'bg-amber-400', HIGH: 'bg-orange-400',
  CRITICAL: 'bg-rose-400', PENDING_REVIEW: 'bg-violet-400', UNASSESSED: 'bg-slate-500',
};
const label = (value: string) => value.toLowerCase().replace(/_/g, ' ');
const number = (value: number) => value.toLocaleString();

export const ExecutiveDashboardPage: React.FC<{ onNavigate: (tab: Destination) => void }> = ({ onNavigate }) => {
  const { user } = useAuth();
  const [data, setData] = useState<ExecutiveDashboard | null>(null);
  const [draft, setDraft] = useState({ start: '', end: '', department: '' });
  const [filters, setFilters] = useState(draft);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [notice, setNotice] = useState('');
  const [busyTask, setBusyTask] = useState<number | null>(null);
  const initialized = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    let pending = false;
    const load = async () => {
      if (pending) return;
      pending = true;
      setLoading(true);
      try {
        const result = await fetchExecutiveDashboard(filters.start, filters.end, filters.department, controller.signal);
        if (controller.signal.aborted) return;
        setData(result); setError('');
        if (!initialized.current) {
          initialized.current = true;
          setDraft({ start: result.start_date, end: result.end_date, department: result.department });
        }
      } catch (err) {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Unable to load dashboard');
      } finally {
        pending = false;
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    void load();
    const timer = window.setInterval(load, 30000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [filters, refresh]);

  const apply = (event: React.FormEvent) => {
    event.preventDefault();
    if (draft.start > draft.end) { setError('Start date must be on or before end date.'); return; }
    setFilters({ ...draft });
  };
  const acknowledge = async (id: number) => {
    setBusyTask(id); setActionError(''); setNotice('');
    try {
      await acknowledgeRiskTask(id);
      setNotice('Alert acknowledged. Receipt is recorded; enforcement review remains pending.');
      setRefresh(value => value + 1);
    } catch (err) { setActionError(err instanceof Error ? err.message : 'Unable to acknowledge alert'); }
    finally { setBusyTask(null); }
  };

  const summary = data?.summary;
  const riskTotal = data ? Object.values(data.risk_distribution).reduce((a, b) => a + b, 0) : 0;
  const maxTrend = Math.max(1, ...(data?.daily.map(day => Math.max(day.detections, day.sightings, day.violations)) || []));
  const openRecords = (tab: Destination, text: string) => <button onClick={() => onNavigate(tab)}
    className="inline-flex items-center gap-1 text-xs text-sky-300 hover:text-sky-100 underline underline-offset-4">
    {text}<ArrowRight size={12} /></button>;

  return <div className="p-3 sm:p-6 space-y-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><div className="flex items-center gap-2"><Activity size={22} className="text-sky-400" />
        <h1 className="text-xl font-semibold">Executive dashboard</h1></div>
        <p className="mt-1 text-sm text-slate-400">Fleet activity, compliance and officer review.</p></div>
      <button onClick={() => setRefresh(value => value + 1)} disabled={loading}
        className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm hover:bg-slate-800 disabled:opacity-50">
        <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />Refresh</button>
    </div>

    <form onSubmit={apply} className={`${panel} flex flex-wrap items-end gap-3`}>
      <label className="text-xs text-slate-400">From (Pakistan time)
        <input required type="date" value={draft.start} onChange={e => setDraft({ ...draft, start: e.target.value })}
          className="glass-input mt-1 block text-sm [color-scheme:dark]" /></label>
      <label className="text-xs text-slate-400">Through
        <input required type="date" value={draft.end} onChange={e => setDraft({ ...draft, end: e.target.value })}
          className="glass-input mt-1 block text-sm [color-scheme:dark]" /></label>
      <label className="min-w-48 flex-1 text-xs text-slate-400">Department
        <select value={draft.department} onChange={e => setDraft({ ...draft, department: e.target.value })}
          className="glass-input mt-1 block w-full text-sm">
          <option value="">All departments</option>
          {data?.department_options.map(name => <option key={name}>{name}</option>)}
        </select></label>
      <button type="submit" className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium hover:bg-sky-500">Apply filters</button>
      <p className="w-full text-xs text-slate-500">Up to 366 days. Registry totals are current; activity uses the department recorded at capture.</p>
    </form>
    {error && <p role="alert" className="rounded-lg border border-rose-800 bg-rose-950/40 p-3 text-sm text-rose-200">{error}{data && ' The last successful results remain below.'}</p>}
    {loading && !data && <p role="status" className="text-sm text-slate-400">Loading dashboard…</p>}
    {data && summary && <>
      <p className="text-xs text-slate-400">Showing {data.start_date} through {data.end_date} · {data.department || 'All departments'} · Updated {new Date(data.generated_at).toLocaleTimeString('en-GB', { timeZone: 'Asia/Karachi' })} PKT · Refreshes every 30 seconds</p>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {([
          ['Registered fleet', summary.registered_vehicles, 'Current active registry', 'authorized'],
          ['Vehicles observed', summary.observed_vehicles, `${number(summary.sightings)} government sightings`, 'spotted'],
          ['Violations', summary.violations, `${number(summary.lawful)} lawful · ${number(summary.review_required)} unassessed / review`, 'spotted'],
          ['Open review alerts', summary.open_tasks, `${number(summary.acknowledged_tasks)} acknowledged in this selection`, 'violations'],
        ] as [string, number, string, Destination][]).map(([title, count, detail, tab]) => <button key={title} onClick={() => onNavigate(tab)}
          className={`${panel} text-left hover:border-sky-700 transition-colors`}>
          <span className="text-xs text-slate-400">{title}</span><strong className="my-2 block text-3xl font-semibold tabular-nums">{number(count)}</strong>
          <span className="block text-xs text-slate-400">{detail}</span>
        </button>)}
      </div>
      {!summary.sightings && <p role="status" className="text-sm text-slate-400">No government sightings in this selection. Choose another date range or capture a registered vehicle.</p>}

      <div className="grid gap-5 lg:grid-cols-3">
        <section className={`${panel} lg:col-span-2`}>
          <h2 className="font-semibold">Activity over time</h2>
          <p className="mt-1 text-xs text-slate-400">{number(summary.detections)} saved plate detections. Repeated sightings are observations, not unique trips.</p>
          <div className="my-3 flex flex-wrap gap-4 text-xs text-slate-400">
            <span className="text-sky-300">● Plate detections</span><span className="text-emerald-300">● Government sightings</span><span className="text-rose-300">● Violations</span>
          </div>
          <svg viewBox="0 0 720 200" className="w-full" role="img" aria-label="Daily detections, government sightings and violations. Exact values are available in the table below.">
            {[0, 0.5, 1].map(fraction => <g key={fraction}><line x1="35" x2="710" y1={170 - fraction * 145} y2={170 - fraction * 145} stroke="#334155" />
              <text x="30" y={174 - fraction * 145} textAnchor="end" fill="#94a3b8" fontSize="10">{maxTrend * fraction}</text></g>)}
            {data.daily.map((day, index) => {
              const width = 675 / data.daily.length;
              return <g key={day.date}><title>{day.date}: {day.detections} detections, {day.sightings} sightings, {day.violations} violations</title>
                {(['detections', 'sightings', 'violations'] as const).map((key, series) => <rect key={key}
                  x={35 + index * width + width * series / 3} y={170 - day[key] / maxTrend * 145}
                  width={Math.max(0.2, width / 3 - 0.5)} height={day[key] / maxTrend * 145} fill={['#38bdf8', '#34d399', '#fb7185'][series]} />)}
              </g>;
            })}
            <text x="35" y="192" fill="#94a3b8" fontSize="10">{data.start_date}</text>
            <text x="710" y="192" textAnchor="end" fill="#94a3b8" fontSize="10">{data.end_date}</text>
          </svg>
          <details className="mt-2 text-xs text-slate-400"><summary className="cursor-pointer">View daily counts and high-risk trend</summary>
            <div className="mt-3 max-h-64 overflow-auto"><table className="w-full text-right">
              <thead><tr><th className="text-left">Date</th><th>Detections</th><th>Sightings</th><th>Violations</th><th>High / Critical</th></tr></thead>
              <tbody>{data.daily.map(day => <tr key={day.date} className="border-t border-slate-800"><td className="py-2 text-left">{day.date}</td>
                <td>{day.detections}</td><td>{day.sightings}</td><td>{day.violations}</td><td>{day.high_risk}</td></tr>)}</tbody>
            </table></div></details>
        </section>
        <section className={panel}><h2 className="font-semibold">Risk distribution</h2>
          <p className="mt-1 mb-4 text-xs text-slate-400">Risk per violation at the time of assessment.</p>
          <div className="space-y-3">{Object.entries(data.risk_distribution).map(([level, count]) => <div key={level}>
            <div className="mb-1 flex justify-between text-xs"><span className="capitalize text-slate-300">{label(level)}</span><span>{number(count)}</span></div>
            <div className="h-2 rounded-full bg-slate-800"><div className={`h-2 rounded-full ${colors[level]}`} style={{ width: `${riskTotal ? count / riskTotal * 100 : 0}%` }} /></div>
          </div>)}</div>
          {!riskTotal && <p className="mt-4 text-xs text-slate-400">No violations in this selection.</p>}
          {data.legacy_risk_count > 0 && <p className="mt-4 text-xs text-slate-400">Includes {data.legacy_risk_count} historical scores without a versioned assessment. Policies may differ.</p>}
        </section>
      </div>

      <section className={panel}><div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-semibold">Department activity</h2>{openRecords('spotted', 'Open sightings log')}</div>
        <p className="mt-1 text-xs text-slate-400">Observed vehicles are distinct registered identities where available. Sightings do not measure mileage or duty utilization.</p>
        <div className="mt-4 overflow-x-auto"><table className="w-full whitespace-nowrap text-right text-sm">
          <thead className="text-xs text-slate-400"><tr><th className="pb-3 pr-6 text-left">Department</th>
            {['Fleet now', 'Observed', 'Sightings', 'Lawful', 'Violations', 'Review / unassessed', 'Open alerts'].map(name => <th key={name} className="px-3 pb-3">{name}</th>)}</tr></thead>
          <tbody>{data.departments.map(row => <tr key={row.department} className="border-t border-slate-800">
            <th className="py-3 pr-6 text-left font-medium">{row.department}</th>
            {[row.registered_vehicles, row.observed_vehicles, row.sightings, row.lawful, row.violations, row.review_required, row.open_tasks].map((count, i) => <td key={i} className="px-3 tabular-nums">{number(count)}</td>)}</tr>)}</tbody>
        </table>{!data.departments.length && <p className="py-4 text-sm text-slate-400">No registry or activity data available.</p>}</div>
      </section>

      <section className={panel}><div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-semibold">Officer review alerts</h2>{openRecords('violations', 'Open full review queue')}</div>
        <p className="mt-1 text-xs text-slate-400">Showing the highest-scored {data.alerts.length} of {summary.open_tasks} open tasks for sightings in this selection. Acknowledgment records receipt.</p>
        {actionError && <p role="alert" className="mt-3 text-sm text-rose-300">{actionError}</p>}
        {notice && <p role="status" className="mt-3 text-sm text-emerald-300">{notice}</p>}
        <div className="mt-4 space-y-2">{data.alerts.map(alert => <article key={alert.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-950/50 p-3">
          <div><p className="text-sm font-medium">{alert.plate_number} <span className="ml-2 text-xs text-amber-300">{alert.risk_level} · {alert.risk_score}/100</span></p>
            <p className="mt-1 text-xs text-slate-400">{alert.department} · {new Date(alert.timestamp).toLocaleString('en-GB', { timeZone: 'Asia/Karachi' })} PKT</p>
            <p className="mt-1 text-xs text-slate-400">{alert.assigned_role} · {label(alert.recommended_action)}</p></div>
          {(user?.role === 'Administrator' || user?.role === alert.assigned_role) && <button disabled={busyTask !== null}
            onClick={() => acknowledge(alert.id)} className="rounded-lg border border-sky-800 px-3 py-2 text-xs text-sky-300 hover:bg-sky-950 disabled:opacity-50">
            {busyTask === alert.id ? 'Saving…' : 'Acknowledge'}</button>}
        </article>)}
          {!data.alerts.length && <p className="text-sm text-slate-400">No open review alerts for this selection.</p>}
        </div>
      </section>
      <section className={panel}><h2 className="font-semibold">Warning and challan review stages</h2>
        <div className="mt-3 flex flex-wrap gap-8"><p><strong className="mr-2 text-2xl">{summary.warning_stage_vehicles}</strong><span className="text-sm text-slate-300">vehicles at warning stage</span></p>
          <p><strong className="mr-2 text-2xl">{summary.challan_eligible_vehicles}</strong><span className="text-sm text-slate-300">vehicles eligible for challan review</span></p></div>
        <p className="my-3 text-xs text-slate-400">For vehicles with violations in this selection, the stage includes all violations through the end date: 1–3 for warning, 4+ for challan review. Formal issuance and collected fines are not yet recorded.</p>
        {openRecords('violations', 'Open enforcement records')}
      </section>
      <p className="text-xs text-slate-500">Links open the full operational pages; dashboard filters apply only to this overview.</p>
    </>}
  </div>;
};
