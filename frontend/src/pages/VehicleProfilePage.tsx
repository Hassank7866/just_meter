import React, { useEffect, useRef, useState } from 'react';
import { DigitalTwin, TwinEvent, TwinReference, TwinVehicle, fetchDigitalTwin, fetchTwinVehicles,
  resolveTwinReference, snapshotUrl } from '../api/client';
import { DutyVerificationPanel } from '../components/DutyVerificationPanel';
import { MovementTrailPanel } from '../components/MovementTrailPanel';
import { VehicleVerificationPanel } from '../components/VehicleVerificationPanel';
import { useAuth } from '../context/AuthContext';

const box = 'rounded-xl border border-slate-800 bg-slate-900/70 p-4 space-y-2 min-w-0';
const input = 'rounded-lg bg-slate-950 border border-slate-700 p-2 text-sm w-full';
const button = 'rounded-lg border border-slate-700 px-3 py-2 text-sm hover:bg-slate-800 disabled:opacity-40';
const value = (data: Record<string, unknown>, key: string) => {
  const result = data[key];
  return typeof result === 'string' || typeof result === 'number' ? String(result) : '';
};
const date = (when?: string | null) => when ? new Date(when).toLocaleString() : 'Unknown';
const titles: Record<TwinEvent['kind'], string> = { sighting: 'Vehicle sighting', risk: 'Risk assessment',
  evidence: 'Evidence captured', duty_review: 'Duty review', assignment: 'Assignment begins', duty_slip: 'Duty slip begins', challan: 'Challan action' };

function TimelineEvent({ event }: { event: TwinEvent }) {
  const { user } = useAuth();
  const data = event.data;
  const task = data.task as Record<string, unknown> | null | undefined;
  return <article className={box}>
    <div className="flex flex-wrap justify-between gap-2"><h3 className="font-semibold">{titles[event.kind]}</h3>
      <time className="text-xs text-slate-400">{date(event.at)}</time></div>
    {event.kind === 'sighting' && <>
      <p>{value(data, 'plate_number')} · {value(data, 'camera_area')} · {value(data, 'status')}</p>
      <p className="text-sm text-slate-400">Department at capture: {value(data, 'department') || 'Unknown'}</p>
      <p className="text-sm">{value(data, 'decision_reason')}</p>
      {value(data, 'violation_id') && <p className="text-xs">Violation: {value(data, 'violation_id')}</p>}
    </>}
    {event.kind === 'risk' && <>
      <p>{value(data, 'score')}/100 · {value(data, 'level')}</p>
      {task && <p className="text-sm">Task #{value(task, 'id')}: {value(task, 'recommended_action')} · {value(task, 'status')} · {value(task, 'assigned_role')}</p>}
    </>}
    {event.kind === 'duty_review' && <><p>{value(data, 'notes')}</p><p className="text-sm text-slate-400">Reviewed by {value(data, 'reviewed_by')}</p></>}
    {(event.kind === 'assignment' || event.kind === 'duty_slip') && <>
      <p>{value(data, 'external_id')} · {value(data, 'status')}</p>
      <p className="text-sm">{date(value(data, 'valid_from'))} – {date(value(data, 'valid_until'))}</p>
      <p>{value(data, 'officer_name') || value(data, 'destination')}</p><p>{value(data, 'purpose')}</p>
    </>}
    {event.kind === 'evidence' && <>
      <p>{value(data, 'evidence_id')} · {value(data, 'review_status')} · {value(data, 'case_status')}</p>
      {value(data, 'related_violation_id') && <p className="text-sm">Violation: {value(data, 'related_violation_id')}</p>}
      {value(data, user?.role === 'Administrator' ? 'full_image' : 'plate_crop') && <a href={snapshotUrl(value(data, user?.role === 'Administrator' ? 'full_image' : 'plate_crop'))} target="_blank" rel="noreferrer" className="text-sky-400 underline">Open archived {user?.role === 'Administrator' ? 'image' : 'plate crop'}</a>}
    </>}
    {event.kind === 'challan' && <><p>{value(data, 'reference')} · {value(data, 'action')} · {value(data, 'current_status')}</p>
      <button className="text-sky-400 underline" onClick={() => window.dispatchEvent(new CustomEvent('justmeter:challan', { detail: { caseId: Number(data.case_id) } }))}>Open challan case</button></>}
  </article>;
}

export const VehicleProfilePage: React.FC<{ reference?: TwinReference | null }> = ({ reference }) => {
  const [query, setQuery] = useState('');
  const [vehicles, setVehicles] = useState<TwinVehicle[]>([]);
  const [totalVehicles, setTotalVehicles] = useState(0);
  const [listOffset, setListOffset] = useState(0);
  const [listError, setListError] = useState('');
  const [listLoading, setListLoading] = useState(false);
  const [selected, setSelected] = useState<TwinReference | null>(reference || null);
  const resolved = useRef<{ reference: TwinReference; id: number } | null>(null);
  const [profile, setProfile] = useState<DigitalTwin | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [offset, setOffset] = useState(0);
  const [asOf, setAsOf] = useState('');
  const [area, setArea] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [filters, setFilters] = useState('');

  useEffect(() => { if (reference) { setSelected(reference); setOffset(0); } }, [reference]);
  useEffect(() => {
    const controller = new AbortController();
    setListLoading(true); setListError('');
    const timer = window.setTimeout(() => {
      fetchTwinVehicles(query, listOffset, controller.signal).then(data => {
        if (!controller.signal.aborted) { setVehicles(data.items); setTotalVehicles(data.total); }
      }).catch(err => { if (!controller.signal.aborted) setListError(err.message); })
        .finally(() => { if (!controller.signal.aborted) setListLoading(false); });
    }, 200);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [query, listOffset, refresh]);

  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    setLoading(true); setError(''); setProfile(null);
    const params = new URLSearchParams(filters);
    params.set('offset', String(offset)); params.set('history_limit', '20');
    const identity = resolved.current?.reference === selected
      ? Promise.resolve(resolved.current.id) : resolveTwinReference(selected, controller.signal);
    identity.then(id => {
      if (controller.signal.aborted) throw new DOMException('Request cancelled', 'AbortError');
      resolved.current = { reference: selected, id };
      return fetchDigitalTwin(id, params, controller.signal);
    })
      .then(data => { if (!controller.signal.aborted) setProfile(data); })
      .catch(err => { if (!controller.signal.aborted) setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [selected, filters, offset, refresh]);

  // Refresh source and observations while the profile is visible, including new camera events.
  useEffect(() => {
    const timer = window.setInterval(() => { if (!document.hidden) setRefresh(v => v + 1); }, 60000);
    return () => window.clearInterval(timer);
  }, []);

  function applyFilters(event: React.FormEvent) {
    event.preventDefault();
    if (from && to && new Date(from) > new Date(to)) { setError('History start must be before its end.'); return; }
    const params = new URLSearchParams();
    if (asOf) params.set('as_of', new Date(asOf).toISOString());
    if (from) params.set('from', new Date(from).toISOString());
    if (to) params.set('to', new Date(to).toISOString());
    if (area.trim()) params.set('camera_area', area.trim());
    setFilters(params.toString()); setOffset(0); setRefresh(v => v + 1);
  }

  return <div className="p-4 sm:p-6 space-y-5">
    <header className="flex flex-wrap justify-between gap-3"><div><h1 className="text-2xl font-bold">Vehicle Digital Twin</h1>
      <p className="text-sm text-slate-400 mt-1">Registry, duty context, compliance, risk and evidence in one vehicle profile.</p></div>
      <button className={button} onClick={() => setRefresh(v => v + 1)} disabled={loading}>Refresh</button></header>
    <div className="grid lg:grid-cols-[240px_minmax(0,1fr)] gap-5">
      <aside className={box}>
        <label className="text-sm">Find a vehicle<input className={`${input} mt-2`} value={query}
          placeholder="Plate or fleet ID" onChange={e => { setQuery(e.target.value); setListOffset(0); }} /></label>
        <p className="text-xs text-slate-400">{totalVehicles} vehicles, including archived records</p>
        {listError && <p role="alert" className="text-red-300">{listError}</p>}
        {listLoading && <p className="text-sm text-slate-400">Searching…</p>}
        {!listLoading && !listError && !vehicles.length && <p>No matching vehicles.</p>}
        {vehicles.map(v => <button key={v.id} className={`block w-full text-left rounded-lg p-2 border ${profile?.vehicle.id === v.id ? 'border-sky-500 bg-sky-950/40' : 'border-slate-800 hover:bg-slate-800'}`}
          onClick={() => { setSelected({ id: v.id }); setOffset(0); }}>
          <span className="font-mono">{v.plate_number}</span><span className="block text-xs text-slate-400">{v.vehicle_id}{!v.active ? ' · Archived' : ''}</span></button>)}
        <div className="flex gap-2"><button className={button} disabled={listOffset === 0 || listLoading} onClick={() => setListOffset(v => v - 20)}>Previous</button>
          <button className={button} disabled={listOffset + 20 >= totalVehicles || listLoading} onClick={() => setListOffset(v => v + 20)}>Next</button></div>
      </aside>
      <section className="space-y-4 min-w-0">
        <form className={`${box} grid sm:grid-cols-2 gap-3`} onSubmit={applyFilters}>
          <label className="text-xs">Duty/source time (local)<input type="datetime-local" className={input} value={asOf} onChange={e => setAsOf(e.target.value)} /></label>
          <label className="text-xs">Observed area for duty check<input className={input} value={area} onChange={e => setArea(e.target.value)} placeholder="Optional; missing context requires review" /></label>
          <label className="text-xs">History from (local)<input type="datetime-local" className={input} value={from} onChange={e => setFrom(e.target.value)} /></label>
          <label className="text-xs">History to (local)<input type="datetime-local" className={input} value={to} onChange={e => setTo(e.target.value)} /></label>
          <button className={button} type="submit">Apply filters</button>
          <p className="text-xs text-slate-400">Duty/source time selects historical VIMS context. Registry and summary cards show current records and all-time totals.</p>
        </form>
        {!selected && <p className={box}>Select a vehicle to open its profile.</p>}
        {loading && <p role="status">Loading vehicle profile…</p>}
        {error && <p role="alert" className="rounded-lg bg-red-950/40 p-4 text-red-300">{error}</p>}
        {profile && <>
          <div className={box}><h2 className="text-xl font-mono font-bold">{profile.vehicle.plate_number} {!profile.vehicle.active && '(Archived)'}</h2>
            <p>{profile.vehicle.department || 'Department unknown'} · {profile.vehicle.vehicle_id || 'Fleet ID unknown'}</p>
            <p>{[profile.vehicle.make, profile.vehicle.model, profile.vehicle.color, profile.vehicle.vehicle_type].filter(Boolean).join(' · ') || 'Vehicle appearance attributes unavailable'}</p>
            <p className="text-sm">Officer: {profile.vehicle.officer_name || 'Not recorded'} · Schedule: {profile.vehicle.duty_schedule || 'Unknown'}</p>
            <p className="text-sm">Authorized areas: {profile.vehicle.authorized_areas.join(', ') || 'Not recorded'}</p>
            <p className="text-xs text-slate-400">Updated {date(profile.generated_at)} · Refreshes every minute</p>
          </div>
          <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-3">
            {[['Sightings', profile.compliance.total_sightings], ['Violations', profile.compliance.total_violations],
              ['Latest risk', profile.risk ? `${profile.risk.score}/100 · ${profile.risk.level}` : 'Not assessed'], ['Open review tasks', profile.open_tasks]]
              .map(([label, amount]) => <div key={label} className={box}><p className="text-xs text-slate-400">{label}</p><p className="font-semibold">{amount}</p></div>)}
          </div>
          <div className={box}><h2 className="font-semibold">Latest sighting</h2>
            {profile.latest_sighting ? <><p>{value(profile.latest_sighting, 'camera_area')} · {date(profile.latest_sighting.observed_at)}</p>
              <p className="text-sm">{value(profile.latest_sighting, 'status')} · Department at capture: {value(profile.latest_sighting, 'department') || 'Unknown'}</p></> : <p>No linked sightings.</p>}
            {profile.risk && <p className="text-xs text-slate-400">Latest risk assessment: {date(profile.risk.assessed_at)}</p>}
          </div>
          <div className={box}><h2 className="font-semibold">VIMS and duty context at {date(profile.as_of)}</h2>
            <p>{profile.source_context.source || 'No linked source'} · Export: {date(profile.source_context.exported_at)}</p>
            {profile.source_context.age_hours != null && <p className="text-xs text-slate-400">Export age at selected time: {profile.source_context.age_hours} hours</p>}
            {profile.source_context.assignments.map(a => <p key={value(a, 'external_id')}>Assignment {value(a, 'external_id')} · Department: {value((a.department || {}) as Record<string, unknown>, 'name') || 'Unknown'} · Officer: {value(a, 'officer_name')} · Driver: {value((a.driver || {}) as Record<string, unknown>, 'name') || 'Unknown'}</p>)}
            {!profile.source_context.assignments.length && <p>No active assignment in the available source snapshot.</p>}
            {profile.source_context.duty_slips.map(d => <p key={value(d, 'external_id')}>Slip {value(d, 'external_id')} · {value(d, 'destination')} · {value(d, 'purpose')}</p>)}
            <DutyVerificationPanel duty={profile.duty_verification} />
          </div>
          {profile.warnings.length > 0 && <div className="rounded-xl border border-amber-700/50 bg-amber-950/20 p-4 text-sm text-amber-200"><h2 className="font-semibold mb-2">Data and review notices</h2><ul className="list-disc pl-5 space-y-1">{profile.warnings.map(w => <li key={w}>{w}</li>)}</ul></div>}
          <VehicleVerificationPanel vehicleId={profile.vehicle.id} refresh={refresh} />
          <MovementTrailPanel vehicleId={profile.vehicle.id} filters={filters} refresh={refresh} />
          <div className="space-y-3"><h2 className="text-lg font-semibold">Activity timeline ({profile.timeline.total})</h2>
            <p className="text-xs text-slate-400">Ordered by observation, assessment, review, challan action or validity-start time. Review statuses and assignment/slip records show their latest saved state. Payment collection is not integrated.</p>
            {profile.timeline.items.map(event => <TimelineEvent key={`${event.kind}-${event.id}`} event={event} />)}
            {!profile.timeline.items.length && <p className={box}>No linked activity for this period.</p>}
            <div className="flex items-center gap-3"><button className={button} disabled={!offset} onClick={() => setOffset(v => v - 20)}>Previous</button>
              <span className="text-xs">Page {Math.floor(offset / 20) + 1}</span>
              <button className={button} disabled={offset + 20 >= profile.timeline.total} onClick={() => setOffset(v => v + 20)}>Next</button></div>
          </div>
        </>}
      </section>
    </div>
  </div>;
};
