import React, { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, RefreshCw, ScanLine, Search, XCircle } from 'lucide-react';
import {
  fetchPlateRecognitions,
  PlateRecognitionRecord,
  reviewPlateRecognition,
  snapshotUrl,
} from '../api/client';
import { useAuth } from '../context/AuthContext';
import { can } from '../context/permissions';

type Filter = 'ALL' | 'REVIEW_REQUIRED' | 'ACCEPTED' | 'REJECTED';

export const ANPRReviewPage: React.FC = () => {
  const { user } = useAuth();
  const canReview = can(user?.role, 'review_records');
  const [records, setRecords] = useState<PlateRecognitionRecord[]>([]);
  const [filter, setFilter] = useState<Filter>('REVIEW_REQUIRED');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [workingId, setWorkingId] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [edits, setEdits] = useState<Record<string, string>>({});

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchPlateRecognitions(filter);
      setRecords(data);
      setEdits(Object.fromEntries(data.map((item) => [
        item.recognition_id,
        item.suggested_text || item.normalized_text,
      ])));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load ANPR records');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [filter]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return records;
    return records.filter((item) =>
      [item.raw_text, item.normalized_text, item.suggested_text, item.camera_id, item.camera_area]
        .some((value) => value?.toLowerCase().includes(needle)),
    );
  }, [records, query]);

  const submit = async (record: PlateRecognitionRecord, status: 'ACCEPTED' | 'REJECTED') => {
    setWorkingId(record.recognition_id);
    setError('');
    try {
      const result = await reviewPlateRecognition(record.recognition_id, {
        corrected_text: edits[record.recognition_id] || '',
        status,
        reviewer: user?.name || user?.email || 'System Administrator',
        notes: status === 'ACCEPTED' ? 'Visually verified from plate crop' : 'Rejected during manual OCR review',
      });
      if (status === 'REJECTED') {
        setNotice(`Recognition ${record.recognition_id} rejected. It was not sent to compliance enforcement.`);
      } else if (result.enforcement) {
        const { compliance, saved, reason, violation_id, challan_id } = result.enforcement;
        const decision = compliance.status;
        const risk = compliance.risk_level ? ` Risk: ${compliance.risk_level} (${compliance.risk_score ?? 0}/100).` : '';
        const caseLink = challan_id ? ` Challan ${challan_id} is linked to evidence.` :
          violation_id ? ` Violation ${violation_id} is linked to evidence.` : '';
        const duplicate = !saved && reason?.includes('duplicate')
          ? ' This capture was suppressed by the duplicate cooldown; no additional sighting was recorded.'
          : '';
        setNotice(`Plate ${result.recognition.final_text} accepted. Decision: ${decision}. ${compliance.decision_reason || ''}${risk}${caseLink}${duplicate}`);
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Review failed');
    } finally {
      setWorkingId('');
    }
  };

  return (
    <div className="p-4 sm:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2"><ScanLine className="text-cyan-400" /> ANPR Review</h1>
          <p className="text-sm text-slate-400 mt-1">Review low-confidence or invalid-format OCR results before enforcement.</p>
        </div>
        <button onClick={() => void load()} className="btn-secondary flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 text-slate-200">
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      <div className="flex flex-col md:flex-row gap-3">
        <div className="flex bg-slate-900 border border-slate-800 rounded-xl p-1 overflow-x-auto">
          {(['REVIEW_REQUIRED', 'ACCEPTED', 'REJECTED', 'ALL'] as Filter[]).map((value) => (
            <button key={value} onClick={() => setFilter(value)} className={`px-3 py-2 rounded-lg text-xs whitespace-nowrap ${filter === value ? 'bg-cyan-600 text-white' : 'text-slate-400 hover:text-white'}`}>
              {value.replace('_', ' ')}
            </button>
          ))}
        </div>
        <div className="flex-1 relative">
          <Search size={16} className="absolute left-3 top-3 text-slate-500" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search plate, camera, or area" className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-10 pr-3 py-2.5 text-sm text-white outline-none focus:border-cyan-500" />
        </div>
      </div>

      {error && <div className="bg-rose-950/40 border border-rose-800 text-rose-300 rounded-xl p-3 text-sm">{error}</div>}
      {notice && <div className="bg-emerald-950/40 border border-emerald-800 text-emerald-200 rounded-xl p-3 text-sm">{notice}</div>}

      {loading ? (
        <div className="text-center py-16 text-slate-500">Loading ANPR records…</div>
      ) : visible.length === 0 ? (
        <div className="text-center py-16 bg-slate-900/50 border border-slate-800 rounded-2xl text-slate-500">No plate recognitions match this view.</div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {visible.map((record) => (
            <article key={record.recognition_id} className="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 space-y-4">
              <div className="flex gap-4">
                <div className="w-40 h-24 bg-black rounded-xl border border-slate-700 overflow-hidden flex items-center justify-center shrink-0">
                  {record.plate_crop ? <img src={snapshotUrl(record.plate_crop)} className="max-w-full max-h-full object-contain" /> : <ScanLine className="text-slate-700" />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex justify-between gap-2">
                    <span className="font-mono text-lg font-bold text-white truncate">{record.raw_text || 'NO TEXT'}</span>
                    <span className={`text-[10px] px-2 py-1 rounded-full h-fit ${record.review_status === 'ACCEPTED' ? 'bg-emerald-500/15 text-emerald-300' : record.review_status === 'REJECTED' ? 'bg-rose-500/15 text-rose-300' : 'bg-amber-500/15 text-amber-300'}`}>{record.review_status}</span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">Confidence: {(Number(record.confidence) * 100).toFixed(1)}%</p>
                  <p className="text-xs text-slate-500 mt-1">{record.camera_id} · {record.camera_area}</p>
                  <p className="text-[10px] text-slate-600 mt-1 font-mono">{record.recognition_id}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="bg-slate-950/60 rounded-lg p-2"><span className="text-slate-500">Normalized</span><div className="font-mono text-slate-200 mt-1">{record.normalized_text || '—'}</div></div>
                <div className="bg-slate-950/60 rounded-lg p-2"><span className="text-slate-500">Reason</span><div className="font-mono text-amber-300 mt-1">{record.review_reason || 'None'}</div></div>
              </div>

              {record.review_status === 'REVIEW_REQUIRED' && canReview && (
                <div className="space-y-2">
                  <label className="text-xs text-slate-400">Corrected plate number</label>
                  <input value={edits[record.recognition_id] || ''} onChange={(e) => setEdits((current) => ({ ...current, [record.recognition_id]: e.target.value.toUpperCase() }))} className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 font-mono text-white outline-none focus:border-cyan-500" />
                  <div className="grid grid-cols-2 gap-2">
                    <button disabled={workingId === record.recognition_id} onClick={() => void submit(record, 'ACCEPTED')} className="py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg text-white text-sm flex justify-center items-center gap-2"><CheckCircle2 size={15} /> Accept</button>
                    <button disabled={workingId === record.recognition_id} onClick={() => void submit(record, 'REJECTED')} className="py-2 bg-rose-600 hover:bg-rose-500 disabled:opacity-50 rounded-lg text-white text-sm flex justify-center items-center gap-2"><XCircle size={15} /> Reject</button>
                  </div>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
};
