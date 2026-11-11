import React, { useEffect, useState } from 'react';
import { MapPin, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { deleteGeofence, fetchCameraAreas, fetchGeofences, GeofenceZone, saveGeofence } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { can } from '../context/permissions';
import { ApprovedRoutesPanel } from '../components/ApprovedRoutesPanel';

const blank = { name: '', camera_area: '', authorized_plates: [] as string[], polygon: [] as Array<{ latitude: number; longitude: number }>,
  kind: 'AUTHORIZED' as 'AUTHORIZED' | 'RESTRICTED', department_id: null as number | null,
  require_assignment: false, require_duty: false };

export const GeofencesPage: React.FC = () => {
  const { user } = useAuth();
  const canManage = can(user?.role, 'manage_geofences');
  const [zones, setZones] = useState<GeofenceZone[]>([]);
  const [areas, setAreas] = useState<string[]>([]);
  const [form, setForm] = useState(blank);
  const [zoneId, setZoneId] = useState('');
  const [vertices, setVertices] = useState('');
  const [plates, setPlates] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true); setError('');
    try { const [items, cameraAreas] = await Promise.all([fetchGeofences(), fetchCameraAreas()]); setZones(items); setAreas(cameraAreas); setForm((prev) => ({ ...prev, camera_area: prev.camera_area || cameraAreas[0] || '' })); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not load geofence settings'); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);

  const edit = (zone: GeofenceZone) => {
    setZoneId(zone.zone_id); setForm({ name: zone.name, camera_area: zone.camera_area, authorized_plates: zone.authorized_plates, polygon: zone.polygon,
      kind: zone.kind || 'AUTHORIZED', department_id: zone.department_id || null,
      require_assignment: !!zone.require_assignment, require_duty: !!zone.require_duty });
    setVertices(zone.polygon.map((p) => `${p.latitude}, ${p.longitude}`).join('\n')); setPlates(zone.authorized_plates.join(', ')); setNotice('Editing zone.');
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setError(''); setNotice('');
    try {
      const polygon = vertices.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map((line) => {
        const [latitude, longitude, ...extra] = line.split(',').map(Number);
        if (extra.length || !Number.isFinite(latitude) || !Number.isFinite(longitude)) throw new Error('Enter one latitude, longitude pair on each line.');
        return { latitude, longitude };
      });
      const result = await saveGeofence({ ...form, polygon, authorized_plates: plates.split(',').map((p) => p.trim().toUpperCase()).filter(Boolean) }, zoneId || undefined);
      setNotice(`Geofence “${result.name}” ${zoneId ? 'updated' : 'created'}.`); setZoneId(''); setForm({ ...blank, camera_area: areas[0] || '' }); setVertices(''); setPlates(''); await load();
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not save geofence'); }
  };

  const remove = async (zone: GeofenceZone) => {
    if (!window.confirm(`Delete geofence “${zone.name}”?`)) return;
    try { await deleteGeofence(zone.zone_id); setNotice(`Geofence “${zone.name}” deleted.`); if (zoneId === zone.zone_id) { setZoneId(''); setForm({ ...blank, camera_area: areas[0] || '' }); setVertices(''); setPlates(''); } await load(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not delete geofence'); }
  };

  return <div className="p-4 sm:p-6 space-y-5">
    <div className="flex justify-between items-start gap-3"><div><h1 className="text-2xl font-bold text-white flex items-center gap-2"><MapPin className="text-violet-400" /> Geofence Zones</h1><p className="text-sm text-slate-400 mt-1">Configure authorized coverage and restricted visit polygons.</p></div><button onClick={() => void load()} className="px-3 py-2 rounded-lg bg-slate-800 text-slate-200 flex gap-2 items-center"><RefreshCw size={15} className={loading ? 'animate-spin' : ''} /> Refresh</button></div>
    <div className="rounded-xl border border-amber-800/60 bg-amber-950/30 p-3 text-sm text-amber-200">Authorized zones determine coverage for matching vehicles and can require a verified assignment or active duty slip. Restricted zones create reviewable movement findings for reviewed sightings; listed plates are exempt. GPS boundary points count as inside. Missing GPS or missing authorized coverage requires manual review.</div>
    {error && <div className="rounded-xl border border-rose-800 bg-rose-950/40 p-3 text-sm text-rose-300">{error}</div>}{notice && <div className="rounded-xl border border-emerald-800 bg-emerald-950/40 p-3 text-sm text-emerald-200">{notice}</div>}
    {canManage && <form onSubmit={(e) => void submit(e)} className="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 space-y-3">
      <h2 className="text-lg font-semibold text-white">{zoneId ? 'Edit geofence' : 'Add geofence'}</h2>
      <div className="grid sm:grid-cols-2 gap-3"><label className="text-xs text-slate-400">Zone name<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-sm text-white" placeholder="Central district boundary" /></label>
      <label className="text-xs text-slate-400">Authorized area<select value={form.camera_area} onChange={(e) => setForm({ ...form, camera_area: e.target.value })} className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-sm text-white">{areas.map((area) => <option key={area}>{area}</option>)}</select></label></div>
      <label className="block text-xs text-slate-400">Plate restrictions (optional, comma separated)<input value={plates} onChange={(e) => setPlates(e.target.value)} className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-sm text-white font-mono" placeholder="ABC123, DEF456" /></label>
      <div className="grid sm:grid-cols-2 gap-3"><label className="text-xs">Zone purpose<select value={form.kind} onChange={e => setForm({ ...form, kind: e.target.value as 'AUTHORIZED' | 'RESTRICTED' })} className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-sm text-white"><option value="AUTHORIZED">Authorized coverage</option><option value="RESTRICTED">Restricted visit</option></select></label>
        <label className="text-xs">Department ID (optional)<input type="number" min="1" value={form.department_id || ''} onChange={e => setForm({ ...form, department_id: e.target.value ? Number(e.target.value) : null })} className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-sm text-white" /></label></div>
      {form.kind === 'AUTHORIZED' && <div className="flex gap-4 text-xs"><label><input type="checkbox" checked={form.require_assignment} onChange={e => setForm({ ...form, require_assignment: e.target.checked })} /> Require verified assignment</label><label><input type="checkbox" checked={form.require_duty} onChange={e => setForm({ ...form, require_duty: e.target.checked })} /> Require active duty slip</label></div>}
      {form.kind === 'RESTRICTED' && <p className="text-xs text-amber-300">Plate restrictions act as exemptions for restricted zones. A reviewed sighting inside this polygon creates a movement finding.</p>}
      <label className="block text-xs text-slate-400">Polygon vertices, one latitude, longitude pair per line (minimum 3)<textarea required rows={5} value={vertices} onChange={(e) => setVertices(e.target.value)} className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-sm text-white font-mono" placeholder="34.3700, 73.4700&#10;34.3800, 73.4700&#10;34.3800, 73.4800&#10;34.3700, 73.4800" /></label>
      <div className="flex gap-2"><button className="px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white flex items-center gap-2"><Plus size={15} />{zoneId ? 'Save changes' : 'Create zone'}</button>{zoneId && <button type="button" onClick={() => { setZoneId(''); setForm({ ...blank, camera_area: areas[0] || '' }); setVertices(''); setPlates(''); }} className="px-4 py-2 rounded-lg bg-slate-800 text-slate-200">Cancel edit</button>}</div>
    </form>}
    <section className="space-y-3"><h2 className="text-lg font-semibold text-white">Configured zones ({zones.length})</h2>{zones.length === 0 ? <div className="text-center py-8 bg-slate-900/50 border border-slate-800 rounded-xl text-slate-400">No zones configured. Polygon enforcement is inactive until a zone is added.</div> : zones.map((zone) => <article key={zone.zone_id} className="bg-slate-900/70 border border-slate-800 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3"><div><div className="font-semibold text-white">{zone.name} <span className="text-xs text-violet-300">· {zone.camera_area}</span></div><div className="text-xs text-slate-400 mt-1">{zone.polygon.length} vertices · {zone.authorized_plates.length ? `Plates: ${zone.authorized_plates.join(', ')}` : 'All authorized vehicles in area'}</div><div className="text-[10px] text-slate-600 font-mono mt-1">{zone.zone_id}</div></div>{canManage && <div className="flex gap-2"><button onClick={() => edit(zone)} className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-200 text-sm">Edit</button><button onClick={() => void remove(zone)} className="px-3 py-1.5 rounded-lg bg-rose-950/60 text-rose-300 text-sm flex items-center gap-1"><Trash2 size={14} />Delete</button></div>}</article>)}</section>
    {canManage && <ApprovedRoutesPanel />}
  </div>;
};
