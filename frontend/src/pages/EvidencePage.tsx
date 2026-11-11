import React, { useCallback, useEffect, useState } from 'react';
import { Archive, CheckCircle2, Download, FileCheck2, RefreshCw, Search, ShieldAlert } from 'lucide-react';
import {
  EvidenceRecord,
  EvidenceVerification,
  evidenceDownloadUrl,
  fetchEvidenceRecords,
  reviewEvidence,
  snapshotUrl,
  verifyEvidence,
} from '../api/client';
import { useAuth } from '../context/AuthContext';
import { can } from '../context/permissions';
import { DutyVerificationPanel } from '../components/DutyVerificationPanel';

const REVIEW_FILTERS = ['ALL', 'CAPTURED', 'UNDER_REVIEW', 'VERIFIED'] as const;
const CASE_FILTERS = ['ALL', 'UNASSIGNED', 'ATTACHED_TO_VIOLATION', 'ATTACHED_TO_CHALLAN'] as const;

import { VehicleProfileLink } from '../components/VehicleProfileLink';

export const EvidencePage: React.FC = () => {
  const { user } = useAuth();
  const canReviewEvidence = can(user?.role, 'review_records');
  const [records, setRecords] = useState<EvidenceRecord[]>([]);
  const [reviewFilter, setReviewFilter] = useState<(typeof REVIEW_FILTERS)[number]>('ALL');
  const [caseFilter, setCaseFilter] = useState<(typeof CASE_FILTERS)[number]>('ALL');
  const [query, setQuery] = useState('');
  const [appliedQuery, setAppliedQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [workingId, setWorkingId] = useState('');
  const [error, setError] = useState('');
  const [verification, setVerification] = useState<Record<string, EvidenceVerification>>({});
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setRecords(await fetchEvidenceRecords(appliedQuery, reviewFilter, caseFilter));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load evidence');
    } finally {
      setLoading(false);
    }
  }, [appliedQuery, reviewFilter, caseFilter]);

  useEffect(() => { void load(); }, [load]);

  const runVerification = async (record: EvidenceRecord) => {
    setWorkingId(record.evidence_id);
    setError('');
    try {
      const result = await verifyEvidence(record.evidence_id);
      setVerification((current) => ({ ...current, [record.evidence_id]: result }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verification failed');
    } finally {
      setWorkingId('');
    }
  };

  const updateReview = async (record: EvidenceRecord, review_status: 'UNDER_REVIEW' | 'VERIFIED') => {
    setWorkingId(record.evidence_id);
    setError('');
    try {
      const result = await reviewEvidence(record.evidence_id, {
        review_status,
        reviewer: user?.name || user?.email || 'System Administrator',
        notes: reviewNotes[record.evidence_id] ?? record.review_notes,
      });
      setRecords((current) => current.map((item) => (
        item.evidence_id === record.evidence_id ? result.evidence : item
      )));
      setReviewNotes((current) => ({ ...current, [record.evidence_id]: result.evidence.review_notes }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update review status');
    } finally {
      setWorkingId('');
    }
  };

  const formatBytes = (value: string | number) => {
    const bytes = Number(value || 0);
    return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(0, Math.round(bytes / 1024))} KB`;
  };

  return (
    <div className="min-w-0 p-3 sm:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-white flex items-center gap-2"><Archive className="text-indigo-400 shrink-0" /> Evidence Management</h1>
          <p className="text-sm text-slate-400 mt-1">Review archived detection images, check file integrity, and download evidence packages.</p>
        </div>
        <button onClick={() => void load()} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 text-slate-200 hover:bg-slate-700">
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      <div className="flex flex-col gap-3">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-1 bg-slate-900 border border-slate-800 rounded-xl p-1">
            <span className="px-2 text-[10px] uppercase text-slate-500">Review</span>
            {REVIEW_FILTERS.map((value) => (
              <button key={value} onClick={() => setReviewFilter(value)} className={`px-3 py-2 rounded-lg text-xs whitespace-nowrap ${reviewFilter === value ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'}`}>
                {value.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-1 bg-slate-900 border border-slate-800 rounded-xl p-1">
            <span className="px-2 text-[10px] uppercase text-slate-500">Case</span>
            {CASE_FILTERS.map((value) => (
              <button key={value} onClick={() => setCaseFilter(value)} className={`px-3 py-2 rounded-lg text-xs whitespace-nowrap ${caseFilter === value ? 'bg-amber-600 text-white' : 'text-slate-400 hover:text-white'}`}>
                {value.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        </div>
        <form onSubmit={(event) => { event.preventDefault(); setAppliedQuery(query.trim()); }} className="relative">
          <Search size={16} className="absolute left-3 top-3 text-slate-500" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search evidence ID, plate, camera, area, or department and press Enter" className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-10 pr-3 py-2.5 text-sm text-white outline-none focus:border-indigo-500" />
        </form>
      </div>

      {error && <div className="bg-rose-950/40 border border-rose-800 text-rose-300 rounded-xl p-3 text-sm">{error}</div>}

      {loading ? (
        <div className="text-center py-16 text-slate-500">Loading evidence records…</div>
      ) : records.length === 0 ? (
        <div className="text-center py-16 bg-slate-900/50 border border-slate-800 rounded-2xl text-slate-500">No evidence has been captured for this view.</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
          {records.map((record) => {
            const integrity = verification[record.evidence_id];
            return (
              <article key={record.evidence_id} className="mx-auto w-full max-w-3xl min-w-0 bg-slate-900/70 border border-slate-800 rounded-2xl overflow-hidden lg:max-w-none">
                <div className="flex h-52 sm:h-60 bg-slate-950">
                  <div className="min-w-0 flex-1 flex items-center justify-center bg-black/80 p-2 sm:p-3">
                    {user?.role === 'Administrator' ? <img src={snapshotUrl(record.full_image)} className="block max-h-full max-w-full object-contain" alt="Detection evidence" /> : <p className="p-4 text-center text-xs text-slate-400">Full camera frames require administrator access. Review the plate crop and archived metadata.</p>}
                  </div>
                  <div className="w-24 sm:w-32 shrink-0 border-l border-slate-800 bg-slate-900 flex items-center justify-center p-2">
                    {record.plate_crop ? <img src={snapshotUrl(record.plate_crop)} className="block max-w-full max-h-full object-contain" alt="Plate crop" /> : <Archive className="text-slate-700" />}
                  </div>
                </div>

                <div className="min-w-0 p-3 sm:p-4 space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
                    <div className="min-w-0">
                      <div className="font-mono text-lg sm:text-xl font-bold text-white break-words">{record.plate_number || 'UNCONFIRMED'}</div>
                      <VehicleProfileLink reference={{ evidence_key: record.evidence_id }} />
                      <div className="text-[10px] font-mono text-slate-500 mt-1 break-all">{record.evidence_id}</div>
                    </div>
                    <div className="flex flex-wrap sm:justify-end gap-1 min-w-0">
                      <span className="max-w-full text-[10px] px-2 py-1 rounded-full bg-indigo-500/15 text-indigo-300 break-words">REVIEW · {record.review_status.replace(/_/g, ' ')}</span>
                      <span className="max-w-full text-[10px] px-2 py-1 rounded-full bg-amber-500/15 text-amber-300 break-words">CASE · {record.case_status.replace(/_/g, ' ')}</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                    <div className="min-w-0 bg-slate-950/60 rounded-lg p-2"><span className="text-slate-500">Camera</span><div className="text-slate-200 mt-1 break-words">{record.camera_id} · {record.camera_area}</div></div>
                    <div className="min-w-0 bg-slate-950/60 rounded-lg p-2"><span className="text-slate-500">Captured</span><div className="text-slate-200 mt-1 break-words">{new Date(record.timestamp).toLocaleString()}</div></div>
                    <div className="min-w-0 bg-slate-950/60 rounded-lg p-2"><span className="text-slate-500">OCR confidence</span><div className="text-slate-200 mt-1">{(Number(record.ocr_confidence) * 100).toFixed(1)}%</div></div>
                    <div className="min-w-0 bg-slate-950/60 rounded-lg p-2"><span className="text-slate-500">Files</span><div className="text-slate-200 mt-1 break-words">{formatBytes(record.full_image_size)} + {formatBytes(record.plate_crop_size)}</div></div>
                    <div className="min-w-0 bg-slate-950/60 rounded-lg p-2"><span className="text-slate-500">Vehicle / department</span><div className="text-slate-200 mt-1 break-words">{record.vehicle_type || 'Unknown'} · {record.department || 'Unknown'}</div></div>
                    <div className="min-w-0 bg-slate-950/60 rounded-lg p-2"><span className="text-slate-500">Detection / recognition</span><div className="text-slate-200 mt-1 break-all">{record.detection_event_id} · {record.recognition_id}</div></div>
                  </div>

                  <div className="font-mono text-[10px] text-slate-500 bg-slate-950/60 rounded-lg p-2 break-all space-y-1">
                    <div>Full frame SHA-256: {record.full_image_sha256 || 'Unavailable'}</div>
                    <div>Plate crop SHA-256: {record.plate_crop_sha256 || 'Unavailable'}</div>
                  </div>

                  <DutyVerificationPanel duty={record.duty_verification} />
                  {integrity && (
                    <div className={`rounded-lg p-2 text-xs flex items-center gap-2 ${integrity.valid ? 'bg-emerald-500/10 text-emerald-300' : 'bg-rose-500/10 text-rose-300'}`}>
                      {integrity.valid ? <CheckCircle2 size={15} /> : <ShieldAlert size={15} />}
                      {integrity.valid ? 'All archived file hashes match.' : 'Integrity failure: an archived file changed or is missing.'}
                    </div>
                  )}

                  {record.review_status === 'UNDER_REVIEW' && canReviewEvidence && (
                    <div className="space-y-2 rounded-lg border border-indigo-500/30 bg-indigo-950/20 p-3">
                      <label className="block text-xs text-slate-300">
                        Review notes
                        <textarea
                          value={reviewNotes[record.evidence_id] ?? record.review_notes}
                          onChange={(event) => setReviewNotes((current) => ({
                            ...current, [record.evidence_id]: event.target.value,
                          }))}
                          className="mt-1 w-full min-h-16 rounded-lg border border-slate-700 bg-slate-950 p-2 text-xs text-white outline-none focus:border-indigo-500"
                          placeholder="Add officer review notes"
                        />
                      </label>
                      <button
                        disabled={workingId === record.evidence_id}
                        onClick={() => void updateReview(record, 'VERIFIED')}
                        className="w-full py-2 bg-emerald-700 hover:bg-emerald-600 disabled:opacity-50 rounded-lg text-white text-xs flex justify-center items-center gap-1"
                      >
                        <CheckCircle2 size={14} /> Complete Review
                      </button>
                    </div>
                  )}

                  {record.review_status === 'VERIFIED' && (
                    <div className="rounded-lg border border-emerald-500/20 bg-emerald-950/20 p-3 text-xs text-slate-300 space-y-1">
                      <div>Reviewed by {record.reviewer || 'Unknown reviewer'}{record.reviewed_at ? ` | ${new Date(record.reviewed_at).toLocaleString()}` : ''}</div>
                      {record.review_notes && <div className="text-slate-400 break-words">{record.review_notes}</div>}
                    </div>
                  )}

                  <div className={`grid gap-2 ${canReviewEvidence ? 'grid-cols-1 sm:grid-cols-2 xl:grid-cols-3' : 'grid-cols-1'}`}>
                    {canReviewEvidence && <>
                    <button disabled={workingId === record.evidence_id} onClick={() => void runVerification(record)} className="py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 rounded-lg text-slate-200 text-xs flex justify-center items-center gap-1"><FileCheck2 size={14} /> Verify Integrity</button>
                    <button
                      disabled={workingId === record.evidence_id || record.review_status === 'UNDER_REVIEW'}
                      onClick={() => void updateReview(record, 'UNDER_REVIEW')}
                      className="py-2 bg-indigo-700 hover:bg-indigo-600 disabled:opacity-50 rounded-lg text-white text-xs flex justify-center items-center gap-1"
                    >
                      <CheckCircle2 size={14} /> {record.review_status === 'VERIFIED' ? 'Reopen Review' : 'Review'}
                    </button>
                    </>}
                    <a href={evidenceDownloadUrl(record.evidence_id)} className="py-2 bg-indigo-700 hover:bg-indigo-600 rounded-lg text-white text-xs flex justify-center items-center gap-1"><Download size={14} /> Package</a>
                  </div>

                  {(record.related_violation_id || record.related_challan_id) && <div className="flex flex-wrap gap-2">
                    {record.related_violation_id && (
                      <span className="text-[10px] px-2 py-1 rounded-full bg-rose-500/15 text-rose-300 border border-rose-500/20">
                        Violation · {record.related_violation_id}
                      </span>
                    )}
                    {record.related_challan_id && (
                      <span
                        className="text-[10px] px-2 py-1 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/20 hover:bg-amber-500/25"
                      >
                        Challan · {record.related_challan_id}
                      </span>
                    )}
                  </div>}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
};
