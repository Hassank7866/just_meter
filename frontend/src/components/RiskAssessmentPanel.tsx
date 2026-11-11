import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { acknowledgeRiskTask, fetchRiskPolicy, fetchRiskTasks, fetchVehicleVerificationRiskQueue, saveRiskPolicy, RiskPolicy, RiskTask, VehicleVerification } from '../api/client';
import { VehicleProfileLink } from './VehicleProfileLink';

const labels: Record<string, string> = {
  recurrence_days: 'History window (days)', repeat_points: 'Points per repeat', repeat_cap: 'Repeat points cap',
  sensitive_assignment_points: 'Sensitive assignment points', critical_assignment_points: 'Critical assignment points',
  severe_history_points: 'Points per prior High/Critical event', severe_history_cap: 'Severe history cap',
  medium_threshold: 'Medium starts at', high_threshold: 'High starts at', critical_threshold: 'Critical starts at',
  challan_review_threshold: 'Challan review starts at',
};

export const RiskAssessmentPanel: React.FC = () => {
  const { user } = useAuth();
  const [policy, setPolicy] = useState<RiskPolicy | null>(null);
  const [tasks, setTasks] = useState<RiskTask[]>([]);
  const [verificationRisks, setVerificationRisks] = useState<VehicleVerification[]>([]);
  const [status, setStatus] = useState('OPEN');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const loadTasks = async () => {
    try { const [risk, verification] = await Promise.all([fetchRiskTasks(status), fetchVehicleVerificationRiskQueue()]); setTasks(risk); setVerificationRisks(verification); }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to load risk tasks'); }
  };
  useEffect(() => {
    fetchRiskPolicy().then(setPolicy).catch(err => setError(err.message));
  }, []);
  useEffect(() => {
    loadTasks();
    const timer = window.setInterval(loadTasks, 15000);
    return () => window.clearInterval(timer);
  }, [status]);

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!policy) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const updated = await saveRiskPolicy(policy);
      setPolicy(updated);
      setNotice(`Policy ${updated.version} saved. Future assessments use this policy; existing assessments retain their original scores.`);
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save policy'); }
    finally { setBusy(false); }
  };

  return <section className="glass-card rounded-xl border border-slate-800 p-4 space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 className="font-semibold text-white">Risk assessment and officer review</h2>
        <p className="text-xs text-slate-400">Tasks are ordered by risk score. Acknowledgment records receipt; challan approval remains a separate decision.</p></div>
      <select aria-label="Risk task status" value={status} onChange={e => setStatus(e.target.value)} className="glass-input text-xs w-auto">
        <option value="OPEN">Open tasks</option><option value="ACKNOWLEDGED">Acknowledged</option><option value="ALL">All tasks</option>
      </select>
    </div>
    <div className="border-t border-slate-800 pt-3 space-y-2">
      <h3 className="text-sm font-semibold text-amber-200">Confirmed vehicle attribute mismatches ({verificationRisks.length})</h3>
      {verificationRisks.map(item => <div key={item.id} className="rounded-lg border border-amber-900/60 p-3 text-xs">
        <p>Observation #{item.sighting_id} · High review · {new Date(item.observed_at).toLocaleString()}</p>
        <p>Mismatch: {Object.entries(item.comparisons).filter(([, result]) => result === 'MISMATCH').map(([name]) => name.replace('_', ' ')).join(', ')}</p>
        <p>Confirmed by {item.reviewed_by}. {item.review_notes}</p>
        <VehicleProfileLink reference={{ id: item.vehicle_id }} />
      </div>)}
    </div>
    {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}
    {notice && <p role="status" className="text-sm text-emerald-300">{notice}</p>}
    <div className="max-h-96 overflow-y-auto space-y-2">
      {!tasks.length && <p className="text-sm text-slate-400">No {status === 'ALL' ? '' : status.toLowerCase()} risk tasks. New confirmed violations create tasks automatically.</p>}
      {tasks.map(task => <div key={task.id} className="rounded-lg border border-slate-700 bg-slate-950/50 p-3 text-xs space-y-2">
        <div className="flex flex-wrap justify-between gap-2">
          <strong className="text-sky-300">{task.plate_number} · {task.risk_level} · {task.risk_score}/100</strong>
          <span>{task.priority} priority · {task.assigned_role}</span>
        </div>
        <p>{task.recommended_action.replace(/_/g, ' ')} · Policy {task.risk_policy_version} · {task.risk_prior_count} prior violations in {task.risk_window_days} days</p>
        <p className="text-slate-400">{task.department} · {task.timestamp.replace('T', ' ').slice(0, 19)}</p>
        <details><summary className="cursor-pointer text-slate-300">Score explanation</summary>
          <ul className="mt-2 space-y-1">{task.risk_breakdown.map((item, index) => <li key={index}>{item.factor}: +{item.points}</li>)}</ul>
          {task.risk_missing_context.map(note => <p key={note} className="text-amber-300 mt-1">{note}</p>)}
          <p className="text-slate-500 mt-1">Score capped at 100. This is a policy score, not a probability.</p>
        </details>
        {task.status === 'ACKNOWLEDGED' ? <p className="text-emerald-300">Acknowledged by {task.acknowledged_by}</p> :
          (user?.role === 'Administrator' || user?.role === task.assigned_role) && <button disabled={busy} className="btn-secondary text-xs" onClick={async () => {
            setBusy(true); setError('');
            try { await acknowledgeRiskTask(task.id); await loadTasks(); }
            catch (err) { setError(err instanceof Error ? err.message : 'Acknowledgment failed'); }
            finally { setBusy(false); }
          }}>Acknowledge review task</button>}
      </div>)}
    </div>
    {policy && <details className="border-t border-slate-800 pt-3">
      <summary className="text-sm cursor-pointer">Risk policy · version {policy.version}</summary>
      <p className="text-xs text-slate-400 my-2">Overlapping route checks use their highest weight. Confirmed integrity mismatches have High/Critical minimum levels.</p>
      <form onSubmit={save} className="space-y-3">
        <fieldset disabled={user?.role !== 'Administrator' || busy} className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {Object.entries(policy.config).filter(([key]) => key !== 'category_weights').map(([key, value]) =>
            <label key={key} className="text-xs text-slate-400">{labels[key] || key}
              <input className="glass-input mt-1" type="number" step="1" min="0" required value={value as number}
                onChange={e => setPolicy({ ...policy, config: { ...policy.config, [key]: Number(e.target.value) } })} />
            </label>)}
          {Object.entries(policy.config.category_weights).map(([key, value]) =>
            <label key={key} className="text-xs text-slate-400">{key.replace(/_/g, ' ')}
              <input className="glass-input mt-1" type="number" step="1" min="0" max="100" required value={value}
                onChange={e => setPolicy({ ...policy, config: { ...policy.config, category_weights: { ...policy.config.category_weights, [key]: Number(e.target.value) } } })} />
            </label>)}
        </fieldset>
        {user?.role === 'Administrator' && <div className="flex gap-2">
          <button disabled={busy} type="submit" className="btn-primary text-xs">Save new policy version</button>
          <button disabled={busy} type="button" className="btn-secondary text-xs" onClick={() => fetchRiskPolicy().then(setPolicy).catch(err => setError(err.message))}>Reload saved policy</button>
        </div>}
      </form>
    </details>}
  </section>;
};
