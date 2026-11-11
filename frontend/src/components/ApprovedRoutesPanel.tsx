import React, { useEffect, useState } from 'react';
import { ApprovedRoute, fetchApprovedRoutes, saveApprovedRoute } from '../api/client';

const input = 'w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-sm text-white';
const button = 'rounded-lg border border-slate-700 px-3 py-2 text-sm hover:bg-slate-800';
const localTime = (value: Date) => new Date(value.getTime() - value.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
const fresh = () => ({ name: '', department_id: 0, vehicle_id: '',
  valid_from: localTime(new Date()), valid_until: localTime(new Date(Date.now() + 30 * 86400000)),
  weekdays: '0,1,2,3,4,5,6', camera_ids: '', camera_areas: '', corridor_polygon: '',
  require_assignment: false, require_duty: false, enforce_dates: false, active: true });

export const ApprovedRoutesPanel: React.FC = () => {
  const [routes, setRoutes] = useState<ApprovedRoute[]>([]);
  const [departments, setDepartments] = useState<Array<{ id: number; name: string }>>([]);
  const [draft, setDraft] = useState(fresh());
  const [editing, setEditing] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = async () => {
    const [routeResponse, departmentResponse] = await Promise.all([fetchApprovedRoutes(), fetch('/api/departments')]);
    if (!departmentResponse.ok) throw new Error('Could not load departments');
    setRoutes(routeResponse); setDepartments(await departmentResponse.json());
  };
  useEffect(() => { void load().catch(e => setError(e.message)); }, []);

  const edit = (route: ApprovedRoute) => {
    setEditing(route.id); setError(''); setNotice('');
    setDraft({ name: route.name, department_id: route.department_id,
      vehicle_id: route.vehicle_id ? String(route.vehicle_id) : '',
      valid_from: localTime(new Date(route.valid_from)), valid_until: localTime(new Date(route.valid_until)),
      weekdays: route.weekdays.join(','), camera_ids: route.camera_ids.join('\n'),
      camera_areas: route.camera_areas.join(','),
      corridor_polygon: route.corridor_polygon.map(point => `${point.latitude}, ${point.longitude}`).join('\n'),
      require_assignment: route.require_assignment, require_duty: route.require_duty,
      enforce_dates: route.enforce_dates, active: route.active });
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setError(''); setNotice('');
    try {
      const polygon = draft.corridor_polygon.split(/\r?\n/).map(line => line.trim()).filter(Boolean).map(line => {
        const values = line.split(',').map(Number);
        if (values.length !== 2 || values.some(value => !Number.isFinite(value))) throw new Error('Enter corridor vertices as latitude, longitude.');
        return { latitude: values[0], longitude: values[1] };
      });
      const saved = await saveApprovedRoute({
        name: draft.name.trim(), department_id: Number(draft.department_id),
        vehicle_id: draft.vehicle_id ? Number(draft.vehicle_id) : null,
        valid_from: new Date(draft.valid_from).toISOString(), valid_until: new Date(draft.valid_until).toISOString(),
        weekdays: draft.weekdays.split(',').map(value => Number(value.trim())),
        camera_ids: draft.camera_ids.split(/\r?\n/).map(value => value.trim()).filter(Boolean),
        camera_areas: draft.camera_areas.split(',').map(value => value.trim()).filter(Boolean),
        corridor_polygon: polygon, require_assignment: draft.require_assignment,
        require_duty: draft.require_duty, enforce_dates: draft.enforce_dates, active: draft.active,
      }, editing || undefined);
      setNotice(`Approved route ${saved.name} saved as revision ${saved.revision}.`);
      setEditing(null); setDraft(fresh()); await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not save approved route'); }
  };

  return <section className="space-y-4">
    <div><h2 className="text-xl font-semibold">Approved routes</h2>
      <p className="text-sm text-slate-400">An administrator approves the department, validity window and expected route. Movement findings require reviewed identity evidence and remain in officer review.</p></div>
    {error && <p role="alert" className="text-rose-300">{error}</p>}
    {notice && <p role="status" className="text-emerald-300">{notice}</p>}
    <form onSubmit={event => void submit(event)} className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 space-y-3">
      <h3 className="font-semibold">{editing ? `Edit route #${editing}` : 'Create approved route'}</h3>
      <div className="grid sm:grid-cols-2 gap-3">
        <label className="text-xs">Name<input className={input} required value={draft.name} onChange={event => setDraft({ ...draft, name: event.target.value })} /></label>
        <label className="text-xs">Department<select className={input} required value={draft.department_id || ''} onChange={event => setDraft({ ...draft, department_id: Number(event.target.value) })}>
          <option value="">Select department</option>{departments.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="text-xs">Vehicle database ID (optional)<input type="number" min="1" className={input} value={draft.vehicle_id} onChange={event => setDraft({ ...draft, vehicle_id: event.target.value })} /></label>
        <label className="text-xs">Weekdays (0 Monday to 6 Sunday)<input className={input} value={draft.weekdays} onChange={event => setDraft({ ...draft, weekdays: event.target.value })} /></label>
        <label className="text-xs">Valid from (local)<input type="datetime-local" required className={input} value={draft.valid_from} onChange={event => setDraft({ ...draft, valid_from: event.target.value })} /></label>
        <label className="text-xs">Valid until (local)<input type="datetime-local" required className={input} value={draft.valid_until} onChange={event => setDraft({ ...draft, valid_until: event.target.value })} /></label>
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        <label className="text-xs">Ordered camera IDs, one per line<textarea rows={4} className={input} value={draft.camera_ids} onChange={event => setDraft({ ...draft, camera_ids: event.target.value })} /></label>
        <label className="text-xs">Approved camera areas, comma separated<textarea rows={4} className={input} value={draft.camera_areas} onChange={event => setDraft({ ...draft, camera_areas: event.target.value })} /></label>
      </div>
      <label className="block text-xs">GPS corridor polygon, one latitude, longitude pair per line (optional)<textarea rows={4} className={input} value={draft.corridor_polygon} onChange={event => setDraft({ ...draft, corridor_polygon: event.target.value })} /></label>
      <div className="flex flex-wrap gap-4 text-sm">
        <label><input type="checkbox" checked={draft.require_assignment} onChange={event => setDraft({ ...draft, require_assignment: event.target.checked })} /> Require verified assignment</label>
        <label><input type="checkbox" checked={draft.require_duty} onChange={event => setDraft({ ...draft, require_duty: event.target.checked })} /> Require active duty slip</label>
        <label><input type="checkbox" checked={draft.enforce_dates} onChange={event => setDraft({ ...draft, enforce_dates: event.target.checked })} /> Enforce approved dates</label>
        <label><input type="checkbox" checked={draft.active} onChange={event => setDraft({ ...draft, active: event.target.checked })} /> Active</label>
      </div>
      <div className="flex gap-2"><button className={button} type="submit">Save route</button>
        {editing && <button className={button} type="button" onClick={() => { setEditing(null); setDraft(fresh()); }}>Cancel</button>}</div>
    </form>
    <div className="space-y-2">{routes.map(route => <article key={route.id} className="rounded-xl border border-slate-800 bg-slate-900/70 p-3 flex flex-wrap justify-between gap-2">
      <div><p className="font-semibold">{route.name} · Revision {route.revision} · {route.active ? 'Active' : 'Inactive'}</p>
        <p className="text-xs text-slate-400">Department #{route.department_id}{route.vehicle_id ? ` · Vehicle #${route.vehicle_id}` : ' · All department vehicles'} · {new Date(route.valid_from).toLocaleString()} to {new Date(route.valid_until).toLocaleString()}</p>
        <p className="text-xs text-slate-400">{route.camera_ids.length} cameras · {route.camera_areas.length} areas · {route.corridor_polygon.length} corridor points · Approved by {route.approved_by}</p></div>
      <button className={button} onClick={() => edit(route)}>Edit</button>
    </article>)}{!routes.length && <p className="text-sm text-slate-400">No approved routes configured.</p>}</div>
  </section>;
};
