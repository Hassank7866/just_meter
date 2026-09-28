import React, { useState, useEffect } from 'react';
import { Modal } from './Modal';
import {
  WhatsAppGatewayStatus,
  fetchWhatsAppGatewayStatus,
  logoutWhatsAppGateway,
  requestPairingCode,
  WhatsAppCloudConfig,
  fetchWhatsAppConfig,
  saveWhatsAppConfig,
} from '../api/client';
import {
  QrCode,
  Smartphone,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  LogOut,
  Sparkles,
  Layers,
  Save,
  Eye,
  EyeOff,
  Copy,
  Check,
  KeyRound,
} from 'lucide-react';

interface WhatsAppSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfigSaved?: () => void;
}

export const WhatsAppSettingsModal: React.FC<WhatsAppSettingsModalProps> = ({
  isOpen,
  onClose,
  onConfigSaved,
}) => {
  const [activeTab, setActiveTab] = useState<'qr' | 'pairing' | 'meta'>('qr');

  // Gateway state
  const [gatewayStatus, setGatewayStatus] = useState<WhatsAppGatewayStatus | null>(null);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [isRefreshingQr, setIsRefreshingQr] = useState(false);

  // Pairing code state
  const [pairingPhone, setPairingPhone] = useState('');
  const [pairingCode, setPairingCode] = useState<string | null>(null);
  const [isRequestingCode, setIsRequestingCode] = useState(false);
  const [pairingError, setPairingError] = useState<string | null>(null);
  const [codeCopied, setCodeCopied] = useState(false);

  // Meta Cloud API state
  const [phoneNumberId, setPhoneNumberId] = useState('');
  const [accessToken, setAccessToken] = useState('');
  const [apiVersion, setApiVersion] = useState('v20.0');
  const [showToken, setShowToken] = useState(false);
  const [isSavingMeta, setIsSavingMeta] = useState(false);
  const [saveStatus, setSaveStatus] = useState<{ success: boolean; message: string } | null>(null);
  const [metaConfig, setMetaConfig] = useState<WhatsAppCloudConfig | null>(null);

  const loadGateway = async () => {
    try {
      const data = await fetchWhatsAppGatewayStatus();
      setGatewayStatus(data);
    } catch (e) {
      console.error('Failed to load WhatsApp Gateway status', e);
    }
  };

  const loadMetaConfig = async () => {
    try {
      const data = await fetchWhatsAppConfig();
      setMetaConfig(data);
      setPhoneNumberId(data.phone_number_id || '');
      setApiVersion(data.api_version || 'v20.0');
      if (data.has_token) {
        setAccessToken(data.token_preview || '••••••••');
      }
    } catch (err) {
      console.error('Failed to load Meta WhatsApp configuration', err);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadGateway();
      loadMetaConfig();
      setSaveStatus(null);

      // Poll gateway status every 2 seconds for instant reaction
      const interval = setInterval(loadGateway, 2000);
      return () => clearInterval(interval);
    }
  }, [isOpen]);

  const handleLogoutGateway = async () => {
    try {
      setIsLoggingOut(true);
      await logoutWhatsAppGateway();
      setPairingCode(null);
      await loadGateway();
      if (onConfigSaved) onConfigSaved();
    } catch (e) {
      console.error('Logout error', e);
    } finally {
      setIsLoggingOut(false);
    }
  };

  const handleRequestPairingCode = async () => {
    if (!pairingPhone.trim()) {
      setPairingError('Please enter your WhatsApp mobile number (e.g. 03001234567)');
      return;
    }

    try {
      setIsRequestingCode(true);
      setPairingError(null);
      setPairingCode(null);

      const res = await requestPairingCode(pairingPhone.trim());
      setPairingCode(res.code);
    } catch (err: any) {
      setPairingError(err.message || 'Failed to generate pairing code. Please try again.');
    } finally {
      setIsRequestingCode(false);
    }
  };

  const handleSaveMeta = async () => {
    try {
      setIsSavingMeta(true);
      setSaveStatus(null);

      const tokenToSend = accessToken === metaConfig?.token_preview ? undefined : accessToken;
      const res = await saveWhatsAppConfig({
        phone_number_id: phoneNumberId.trim(),
        access_token: tokenToSend ? tokenToSend.trim() : undefined,
        api_version: apiVersion.trim() || 'v20.0',
      });

      setMetaConfig(res.config);
      setSaveStatus({ success: true, message: 'Meta Cloud API settings saved successfully!' });
      if (onConfigSaved) onConfigSaved();
    } catch (err: any) {
      setSaveStatus({
        success: false,
        message: err.message || 'Failed to save Meta settings.',
      });
    } finally {
      setIsSavingMeta(false);
    }
  };

  const isConnected = Boolean(gatewayStatus?.connected);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="WhatsApp Delivery Gateway"
      maxWidth="max-w-2xl"
      footer={
        <div className="flex items-center justify-between w-full">
          <button type="button" onClick={onClose} className="btn-secondary text-xs py-2 px-4">
            Close
          </button>

          {isConnected ? (
            <button
              type="button"
              disabled={isLoggingOut}
              onClick={handleLogoutGateway}
              className="btn-secondary text-xs py-2 px-3.5 text-rose-300 hover:text-rose-100 hover:bg-rose-950/40 border-rose-500/30 flex items-center gap-1.5"
            >
              <LogOut size={13} />
              <span>{isLoggingOut ? 'Disconnecting...' : 'Unlink Device'}</span>
            </button>
          ) : activeTab === 'qr' ? (
            <button
              type="button"
              disabled={isRefreshingQr}
              onClick={() => {
                setIsRefreshingQr(true);
                loadGateway().finally(() => setIsRefreshingQr(false));
              }}
              className="btn-secondary text-xs py-2 px-3.5 flex items-center gap-1.5"
            >
              <RefreshCw size={13} className={isRefreshingQr ? 'animate-spin' : ''} />
              <span>Refresh QR Code</span>
            </button>
          ) : activeTab === 'meta' ? (
            <button
              type="button"
              disabled={isSavingMeta}
              onClick={handleSaveMeta}
              className="btn-primary text-xs py-2 px-5 font-bold flex items-center gap-2 shadow-lg shadow-sky-600/30"
            >
              <Save size={14} />
              <span>Save Meta Settings</span>
            </button>
          ) : null}
        </div>
      }
    >
      <div className="space-y-4">
        {/* Top Switcher Tabs */}
        <div className="flex rounded-xl bg-slate-900/90 p-1 border border-slate-800">
          <button
            type="button"
            onClick={() => setActiveTab('qr')}
            className={`flex-1 py-2 rounded-lg text-xs font-bold flex items-center justify-center gap-2 transition-all ${
              activeTab === 'qr'
                ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <QrCode size={15} />
            <span>Option 1: Scan QR Code</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('pairing')}
            className={`flex-1 py-2 rounded-lg text-xs font-bold flex items-center justify-center gap-2 transition-all ${
              activeTab === 'pairing'
                ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <KeyRound size={15} />
            <span>Option 2: 8-Digit Pairing Code (No Camera)</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('meta')}
            className={`py-2 px-3 rounded-lg text-xs font-medium flex items-center justify-center gap-1.5 transition-all ${
              activeTab === 'meta'
                ? 'bg-sky-600 text-white shadow-md shadow-sky-600/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers size={13} />
            <span>Meta API</span>
          </button>
        </div>

        {/* Global Connection Header */}
        <div
          className={`p-3.5 rounded-xl border flex items-center justify-between ${
            isConnected
              ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-200'
              : 'bg-slate-900/80 border-slate-800 text-slate-300'
          }`}
        >
          <div className="flex items-center gap-3">
            <div
              className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-base ${
                isConnected
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  : 'bg-slate-800 text-slate-400'
              }`}
            >
              {isConnected ? <ShieldCheck size={22} /> : <Smartphone size={22} />}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm text-white">
                  {isConnected ? 'WhatsApp Bridge: Connected & Online' : 'Device Linking Required'}
                </span>
                <span
                  className={`text-[10px] font-extrabold px-2.5 py-0.5 rounded-full ${
                    isConnected
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                      : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                  }`}
                >
                  {isConnected ? 'Ready for Auto PDF Delivery' : 'Unlinked'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                {isConnected
                  ? `Linked as +${gatewayStatus?.user?.phone || 'Your Number'} • Dispatches PDF Challans in background`
                  : 'Link once via QR code or 8-digit code to enable automated PDF delivery from this computer'}
              </p>
            </div>
          </div>
        </div>

        {/* If Connected */}
        {isConnected ? (
          <div className="p-6 rounded-2xl bg-emerald-950/20 border border-emerald-500/30 text-center space-y-3">
            <div className="w-14 h-14 mx-auto rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 flex items-center justify-center">
              <CheckCircle2 size={32} />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Your WhatsApp is Linked &amp; Ready!</h3>
              <p className="text-xs text-slate-300 max-w-md mx-auto mt-1 leading-relaxed">
                Whenever you click <strong className="text-emerald-300">"Send PDF to WhatsApp"</strong> on any violation or challan, the system will automatically send the real <strong className="text-white">.pdf</strong> document file straight to the recipient in the background.
              </p>
            </div>
          </div>
        ) : (
          <>
            {/* TAB 1: QR CODE */}
            {activeTab === 'qr' && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-center bg-slate-900/60 p-4 rounded-2xl border border-slate-800">
                {/* Left: Live QR */}
                <div className="flex flex-col items-center justify-center p-3 bg-white rounded-xl shadow-2xl">
                  {gatewayStatus?.qr ? (
                    <img
                      src={gatewayStatus.qr}
                      alt="WhatsApp QR Code"
                      className="w-56 h-56 object-contain rounded-lg"
                    />
                  ) : (
                    <div className="w-56 h-56 flex flex-col items-center justify-center gap-3 text-slate-700">
                      <div className="w-8 h-8 border-3 border-emerald-600 border-t-transparent rounded-full animate-spin"></div>
                      <p className="text-xs font-semibold">Generating QR Code...</p>
                    </div>
                  )}
                  <p className="text-[10px] text-slate-500 font-mono mt-1">Refreshes automatically</p>
                </div>

                {/* Right: Steps */}
                <div className="space-y-3 text-xs text-slate-300">
                  <div className="flex items-center gap-1.5 text-emerald-400 font-bold text-sm">
                    <Sparkles size={16} />
                    <span>How to Scan:</span>
                  </div>

                  <ol className="space-y-2.5 text-slate-300">
                    <li className="flex items-start gap-2">
                      <span className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-300 font-mono font-bold flex items-center justify-center shrink-0 text-[11px]">
                        1
                      </span>
                      <span>Open <strong>WhatsApp</strong> on your phone.</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-300 font-mono font-bold flex items-center justify-center shrink-0 text-[11px]">
                        2
                      </span>
                      <span>
                        Tap <strong>Settings</strong> (or <strong>⋮ Menu</strong>) &gt; <strong>Linked Devices</strong> &gt; <strong>Link a Device</strong>.
                      </span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-300 font-mono font-bold flex items-center justify-center shrink-0 text-[11px]">
                        3
                      </span>
                      <span>Point your camera at the QR code on the left!</span>
                    </li>
                  </ol>

                  <div className="pt-2">
                    <button
                      type="button"
                      onClick={() => setActiveTab('pairing')}
                      className="text-[11px] text-sky-400 hover:text-sky-300 underline flex items-center gap-1"
                    >
                      <span>Can't scan with camera? Link with phone number &amp; 8-digit code instead &rarr;</span>
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: 8-DIGIT PAIRING CODE (NO CAMERA NEEDED) */}
            {activeTab === 'pairing' && (
              <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
                <div>
                  <h4 className="text-sm font-bold text-white flex items-center gap-2">
                    <KeyRound size={16} className="text-emerald-400" />
                    <span>Link with Phone Number (No Camera Needed)</span>
                  </h4>
                  <p className="text-xs text-slate-400 mt-1">
                    Enter your phone number to get an 8-digit code, then type the code into WhatsApp on your phone.
                  </p>
                </div>

                <div className="flex gap-2">
                  <input
                    type="text"
                    value={pairingPhone}
                    onChange={(e) => setPairingPhone(e.target.value)}
                    placeholder="e.g. 03001234567"
                    className="glass-input text-xs py-2 flex-1 font-mono"
                  />
                  <button
                    type="button"
                    disabled={isRequestingCode}
                    onClick={handleRequestPairingCode}
                    className="btn-primary text-xs py-2 px-4 font-bold flex items-center gap-1.5"
                  >
                    {isRequestingCode ? (
                      <>
                        <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                        <span>Generating Code...</span>
                      </>
                    ) : (
                      <>
                        <KeyRound size={13} />
                        <span>Get 8-Digit Code</span>
                      </>
                    )}
                  </button>
                </div>

                {pairingError && (
                  <div className="p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-xs text-rose-300 flex items-center gap-2">
                    <AlertCircle size={15} />
                    <span>{pairingError}</span>
                  </div>
                )}

                {pairingCode && (
                  <div className="p-4 rounded-2xl bg-emerald-950/30 border border-emerald-500/40 text-center space-y-3 animate-fade-in">
                    <p className="text-xs text-emerald-300 font-semibold">
                      Enter this 8-digit code in WhatsApp on your phone:
                    </p>
                    <div className="flex items-center justify-center gap-2">
                      <div className="font-mono text-2xl font-black tracking-widest text-white bg-slate-950 py-2.5 px-6 rounded-xl border border-emerald-500/50 shadow-inner">
                        {pairingCode}
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          navigator.clipboard.writeText(pairingCode);
                          setCodeCopied(true);
                          setTimeout(() => setCodeCopied(false), 2000);
                        }}
                        className="btn-secondary py-2.5 px-3 text-xs"
                        title="Copy code"
                      >
                        {codeCopied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
                      </button>
                    </div>

                    <div className="text-[11px] text-slate-400 max-w-md mx-auto space-y-1">
                      <p>
                        1. Open <strong>WhatsApp</strong> on your phone.
                      </p>
                      <p>
                        2. Tap <strong>Linked Devices</strong> &gt; <strong>Link a Device</strong> &gt; <strong>Link with phone number instead</strong>.
                      </p>
                      <p>
                        3. Type the 8-digit code above.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: META CLOUD API */}
            {activeTab === 'meta' && (
              <div className="space-y-3.5">
                {saveStatus && (
                  <div
                    className={`p-3 rounded-lg text-xs flex items-center gap-2 ${
                      saveStatus.success
                        ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300'
                        : 'bg-rose-500/15 border border-rose-500/30 text-rose-300'
                    }`}
                  >
                    {saveStatus.success ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
                    <span>{saveStatus.message}</span>
                  </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 bg-slate-900/60 p-3.5 rounded-xl border border-slate-800">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Phone Number ID</label>
                    <input
                      type="text"
                      value={phoneNumberId}
                      onChange={(e) => setPhoneNumberId(e.target.value)}
                      placeholder="e.g. 104829384729104"
                      className="glass-input text-xs font-mono py-2"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Graph API Version</label>
                    <input
                      type="text"
                      value={apiVersion}
                      onChange={(e) => setApiVersion(e.target.value)}
                      placeholder="v20.0"
                      className="glass-input text-xs font-mono py-2"
                    />
                  </div>

                  <div className="sm:col-span-2">
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Access Token</label>
                    <div className="relative">
                      <input
                        type={showToken ? 'text' : 'password'}
                        value={accessToken}
                        onChange={(e) => setAccessToken(e.target.value)}
                        placeholder="EAAG..."
                        className="glass-input text-xs font-mono py-2 pr-10"
                      />
                      <button
                        type="button"
                        onClick={() => setShowToken(!showToken)}
                        className="absolute right-3 top-2.5 text-slate-400"
                      >
                        {showToken ? <EyeOff size={14} /> : <Eye size={14} />}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </Modal>
  );
};
