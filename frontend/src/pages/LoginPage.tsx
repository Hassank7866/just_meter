import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Radio, Lock, Mail, AlertCircle, ArrowRight, ShieldCheck, Eye, EyeOff, KeyRound } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const [email, setEmail] = useState('admin@justmeter.gov');
  const [password, setPassword] = useState('admin123');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
    } catch (err: any) {
      setError(err.message || 'Invalid credentials. Please verify your email & password.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleFillDemo = () => {
    setEmail('admin@justmeter.gov');
    setPassword('admin123');
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden bg-slate-950">
      {/* Dynamic Background Glows */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-sky-500/10 rounded-full blur-3xl pointer-events-none"></div>
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none"></div>

      <div className="w-full max-w-md glass-panel p-8 relative z-10 border border-sky-500/20 shadow-2xl animate-fade-in">
        {/* Header Icon & Title */}
        <div className="text-center mb-8">
          <div className="inline-flex w-16 h-16 rounded-2xl bg-gradient-to-tr from-sky-600 to-indigo-600 items-center justify-center shadow-lg shadow-sky-500/25 mb-4 border border-sky-400/30">
            <Radio className="text-white animate-pulse" size={32} />
          </div>
          <h1 className="text-2xl font-extrabold text-white tracking-wider">
            JUST <span className="text-sky-400">METER</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1 font-medium">
            AJK Government Car Surveillance System
          </p>
        </div>

        {/* Error Alert Banner */}
        {error && (
          <div className="mb-6 p-3.5 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2.5 animate-fade-in">
            <AlertCircle size={18} className="shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wider">
              Admin Email
            </label>
            <div className="relative flex items-center">
              <div className="absolute left-3.5 flex items-center pointer-events-none text-slate-400 z-10">
                <Mail size={16} />
              </div>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@justmeter.gov"
                className="glass-input has-icon-left !pl-11"
                style={{ paddingLeft: '2.85rem' }}
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wider">
              Password
            </label>
            <div className="relative flex items-center">
              <div className="absolute left-3.5 flex items-center pointer-events-none text-slate-400 z-10">
                <Lock size={16} />
              </div>
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="glass-input has-icon-left has-icon-right !pl-11 !pr-11"
                style={{ paddingLeft: '2.85rem', paddingRight: '2.85rem' }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 flex items-center p-1 text-slate-400 hover:text-slate-200 z-10 transition-colors rounded"
                title={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* Quick Demo Helper / Default Credentials */}
          <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 rounded-xl bg-slate-900/80 border border-slate-800 text-xs">
            <span className="text-slate-400 flex items-center gap-1.5">
              <KeyRound size={13} className="text-sky-400 shrink-0" />
              <span>Default Credentials:</span>
            </span>
            <button
              type="button"
              onClick={handleFillDemo}
              className="text-sky-400 hover:text-sky-300 font-mono font-medium px-2 py-0.5 rounded-lg bg-sky-500/10 hover:bg-sky-500/20 border border-sky-500/20 transition-all text-[11px]"
              title="Click to auto-fill credentials"
            >
              admin@justmeter.gov / admin123
            </button>
          </div>

          {/* Submit Button */}
          <div className="pt-2">
            <button
              type="submit"
              disabled={submitting}
              className="btn-primary w-full py-3 text-sm shadow-lg shadow-sky-600/30"
            >
              {submitting ? (
                <div className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                  <span>Authenticating...</span>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <span>Sign In to Command Portal</span>
                  <ArrowRight size={16} />
                </div>
              )}
            </button>
          </div>
        </form>

        {/* Security badge footer */}
        <div className="mt-8 pt-6 border-t border-slate-800/80 text-center">
          <div className="inline-flex items-center gap-1.5 text-[11px] text-slate-400">
            <ShieldCheck size={14} className="text-emerald-400" />
            <span>Role-Based Operational Access Control (AJK / PK)</span>
          </div>
        </div>
      </div>
    </div>
  );
};
