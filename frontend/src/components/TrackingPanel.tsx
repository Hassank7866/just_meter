import { useEffect, useState } from 'react';
import {
  CameraCheckpoint, CheckpointCrossing, TrackLinkCandidate,
  confirmTrackLink, fetchCameraCheckpoint, fetchCheckpointCrossings,
  fetchTrackLinkCandidates, saveCameraCheckpoint,
} from '../api/client';

type Config = Omit<CameraCheckpoint, 'camera_id' | 'revision'>;
const defaults: Config = {
  name: 'Checkpoint', x1: 0.5, y1: 0, x2: 0.5, y2: 1,
  direction: 'BOTH', active: true,
};

export function TrackingPanel({ cameraId }: { cameraId: string }) {
  const [config, setConfig] = useState<Config>(defaults);
  const [revision, setRevision] = useState<number | null>(null);
  const [crossings, setCrossings] = useState<CheckpointCrossing[]>([]);
  const [candidates, setCandidates] = useState<TrackLinkCandidate[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const id = cameraId.trim();

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      if (!id) return;
      try {
        const [saved, events, links] = await Promise.all([
          fetchCameraCheckpoint(id), fetchCheckpointCrossings(id), fetchTrackLinkCandidates(),
        ]);
        if (cancelled) return;
        setConfig(saved ? { name: saved.name, x1: saved.x1, y1: saved.y1,
          x2: saved.x2, y2: saved.y2, direction: saved.direction, active: saved.active } : defaults);
        setRevision(saved?.revision ?? null);
        setCrossings(events);
        setCandidates(links);
        setError('');
      } catch (cause) {
        if (!cancelled) setError(cause instanceof Error ? cause.message : 'Could not load tracking data');
      }
    }, 350);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [id]);

  const refresh = async () => {
    if (!id) return;
    try {
      const [events, links] = await Promise.all([
        fetchCheckpointCrossings(id), fetchTrackLinkCandidates(),
      ]);
      setCrossings(events);
      setCandidates(links);
      setError('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not refresh tracking data');
    }
  };

  const save = async () => {
    if (!id) return;
    setBusy(true);
    setMessage('');
    try {
      const saved = await saveCameraCheckpoint(id, config);
      setRevision(saved.revision);
      setMessage(`Saved line revision ${saved.revision}`);
      setError('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not save checkpoint');
    } finally {
      setBusy(false);
    }
  };

  const confirm = async (candidate: TrackLinkCandidate) => {
    setBusy(true);
    setMessage('');
    try {
      await confirmTrackLink(candidate);
      setMessage(`Linked ${candidate.first_camera_id} and ${candidate.second_camera_id}`);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not link tracks');
    } finally {
      setBusy(false);
    }
  };

  const coordinate = (key: 'x1' | 'y1' | 'x2' | 'y2') => (
    <label key={key} className="text-[10px] text-zinc-400 uppercase">
      {key}
      <input type="number" min="0" max="1" step="0.05" value={config[key]}
        onChange={(event) => setConfig((current) => ({ ...current, [key]: Number(event.target.value) }))}
        className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 p-1.5 text-xs text-zinc-200" />
    </label>
  );

  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-3 space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Checkpoint tracking</h3>
        <button type="button" onClick={() => void refresh()} className="text-[11px] text-sky-400">Refresh</button>
      </div>
      <p className="text-[11px] text-zinc-500">Line coordinates run from 0 to 1 across the camera frame. Default: vertical centre line.</p>
      <input value={config.name} maxLength={100}
        onChange={(event) => setConfig((current) => ({ ...current, name: event.target.value }))}
        aria-label="Checkpoint name" className="w-full rounded border border-zinc-700 bg-zinc-950 p-2 text-xs text-zinc-200" />
      <div className="grid grid-cols-4 gap-1">{(['x1', 'y1', 'x2', 'y2'] as const).map(coordinate)}</div>
      <div className="flex gap-2 items-center">
        <select value={config.direction}
          onChange={(event) => setConfig((current) => ({ ...current, direction: event.target.value as Config['direction'] }))}
          aria-label="Counting direction" className="min-w-0 flex-1 rounded border border-zinc-700 bg-zinc-950 p-2 text-xs text-zinc-200">
          <option value="BOTH">Both directions</option>
          <option value="A_TO_B">A to B</option>
          <option value="B_TO_A">B to A</option>
        </select>
        <label className="text-[11px] text-zinc-400">
          <input type="checkbox" checked={config.active}
            onChange={(event) => setConfig((current) => ({ ...current, active: event.target.checked }))} /> Active
        </label>
      </div>
      <button type="button" disabled={!id || busy} onClick={() => void save()}
        className="w-full rounded bg-sky-700 px-2 py-2 text-xs text-white disabled:opacity-50">Save checkpoint line</button>
      <p className="text-[11px] text-zinc-500">{revision ? `Revision ${revision}` : 'No saved line'} · {crossings.length} recent crossings</p>
      {crossings.slice(0, 3).map((item, index) => (
        <p key={`${item.track_id}-${index}`} className="text-[11px] text-zinc-400">
          {item.track_id.slice(-6)} · {item.direction} · {new Date(item.timestamp).toLocaleString()}
        </p>
      ))}
      <div className="border-t border-zinc-800 pt-2">
        <h4 className="text-xs text-zinc-300">Cross-camera candidates</h4>
        <p className="text-[11px] text-zinc-500">Only manually reviewed live plate reads appear. Confirm a match before using it as a movement link.</p>
        {candidates.length === 0 && <p className="text-[11px] text-zinc-500">No candidates in the last seven days.</p>}
        {candidates.slice(0, 5).map((item) => (
          <div key={`${item.first_track_id}-${item.second_track_id}`} className="mt-2 border-t border-zinc-800 pt-2 text-[11px] text-zinc-300">
            <p>{item.plate_number}: {item.first_camera_id} → {item.second_camera_id}</p>
            <p className="text-zinc-500">{Math.round(item.elapsed_seconds / 60)} min apart · {item.confirmed ? 'Confirmed' : 'Needs confirmation'}</p>
            {!item.confirmed && <button type="button" disabled={busy} onClick={() => void confirm(item)}
              className="mt-1 text-sky-400 disabled:opacity-50">Confirm link</button>}
          </div>
        ))}
      </div>
      {message && <p className="text-[11px] text-emerald-400">{message}</p>}
      {error && <p className="text-[11px] text-rose-400">{error}</p>}
    </div>
  );
}
