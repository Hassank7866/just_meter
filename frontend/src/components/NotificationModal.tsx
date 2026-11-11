import React, { useState, useEffect } from 'react';
import { VehicleViolationSummary, authenticatedResourceUrl, sendViolationNotification } from '../api/client';
import { Modal } from './Modal';
import {
  CheckCircle2,
  AlertCircle,
  User,
  Phone,
  ShieldAlert,
  Copy,
  Check,
  MessageCircle,
  Send,
  Settings,
  Share2,
  FileText,
} from 'lucide-react';

interface NotificationModalProps {
  vehicle: VehicleViolationSummary | null;
  isOpen: boolean;
  onClose: () => void;
  onNotificationSent?: () => void;
  onOpenWhatsAppSettings?: () => void;
  onOpenChallanModal?: (vehicle: VehicleViolationSummary) => void;
}

export const NotificationModal: React.FC<NotificationModalProps> = ({
  vehicle,
  isOpen,
  onClose,
  onNotificationSent,
  onOpenWhatsAppSettings,
  onOpenChallanModal,
}) => {
  const [officerName, setOfficerName] = useState('');
  const [recipientPhone, setRecipientPhone] = useState('');
  const [customNote, setCustomNote] = useState('');
  const [copied, setCopied] = useState(false);
  const [isSendingDirect, setIsSendingDirect] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string; isApiConfigErr?: boolean } | null>(null);

  useEffect(() => {
    if (vehicle) {
      setOfficerName(vehicle.officer_name || '');
      setRecipientPhone(vehicle.officer_phone || '');
      setCustomNote('');
      setStatusMessage(null);
      setCopied(false);
    }
  }, [vehicle, isOpen]);

  if (!vehicle) return null;

  const isChallan = vehicle.stage_type === 'challan' || vehicle.total_violations >= 4;
  const tierTitle = isChallan
    ? `OFFICIAL E-CHALLAN (${vehicle.total_violations}th Offense)`
    : `OFFICIAL WARNING #${vehicle.total_violations}`;

  // Clean phone digits for WhatsApp
  const cleanPhoneForWhatsApp = (raw: string) => {
    let digits = (raw || '').replace(/\D/g, '');
    if (digits.startsWith('0') && digits.length === 11) {
      digits = '92' + digits.slice(1);
    } else if (digits.length === 10 && digits.startsWith('3')) {
      digits = '92' + digits;
    }
    return digits;
  };

  // Generate live preview text for WhatsApp
  const previewText = () => {
    const greeting = officerName ? `Officer ${officerName}` : 'Vehicle Custodian';
    const deptStr = vehicle.department ? `(${vehicle.department})` : '';

    if (isChallan) {
      const fineStr = `PKR ${vehicle.fine_amount.toLocaleString()}`;
      const numPart = (vehicle.plate_number.replace(/[^a-zA-Z0-9]/g, '').split('').map(c => c.charCodeAt(0)).join('') + '000000').slice(0, 6);
      const psidNumber = `9926${numPart}${String(vehicle.total_violations).padStart(2, '0')}1`;
      const pdfUrl = 'Retrieve the PDF from the authenticated Just Meter portal.';

      let text = `🚨 *OFFICIAL TRAFFIC / FLEET E-CHALLAN*\n🏛 *AJK / PK Government Fleet Command*\n━━━━━━━━━━━━━━━━━━━━━\nAttention: *${greeting}* ${deptStr}\nVehicle Plate: *${vehicle.plate_number}*\nChallan Number: *${vehicle.challan_id || 'CHL-2026'}*\nTotal Recorded Violations: *${vehicle.total_violations}*\nStatus: *4th Violation Policy Exceeded*\nFine Penalty Levied: *${fineStr}*\n━━━━━━━━━━━━━━━━━━━━━\n🏦 *PAYMENT & BANK PARTICULARS*:\n• Bank: *National Bank of Pakistan (NBP)*\n• Account Title: *Govt Fleet - Traffic Penalty Collection*\n• Bank IBAN: *PK36NBPA0000001284793012*\n• 1Bill / Online PSID: *${psidNumber}*\n• Online Payment: *Easypaisa / JazzCash / 1Bill / Banking Apps*\n━━━━━━━━━━━━━━━━━━━━━\n📄 *Download Official PDF Challan*:\n${pdfUrl}\n━━━━━━━━━━━━━━━━━━━━━\n`;
      if (customNote.trim()) {
        text += `📝 *Command Note*: ${customNote.trim()}\n`;
      }
      text += `\nPlease deposit the penalty within 7 business days.\n— *Automated Just Meter Surveillance System*`;
      return text;
    } else {
      let text = `⚠️ *GOVERNMENT FLEET COMPLIANCE NOTICE*\n🏛 *AJK / PK Government Fleet Command*\n━━━━━━━━━━━━━━━━━━━━━\nAttention: *${greeting}* ${deptStr}\nVehicle Plate: *${vehicle.plate_number}*\nViolation Tier: *Warning #${vehicle.total_violations}*\n━━━━━━━━━━━━━━━━━━━━━\nNotice: This vehicle was spotted in breach of authorized operational areas or duty schedule. This serves as an official formal warning.\n\n⚡ *Policy Warning*: Accumulating 4 or more violations will result in an automated Departmental Fee Challan and disciplinary review.\n`;
      if (customNote.trim()) {
        text += `\n📝 *Command Note*: ${customNote.trim()}\n`;
      }
      text += `\n— *Automated Just Meter Fleet Command*`;
      return text;
    }
  };

  const handleCopyMessage = async () => {
    try {
      await navigator.clipboard.writeText(previewText());
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch (err) {
      console.error('Failed to copy', err);
    }
  };

  // Direct Meta WhatsApp Cloud API Dispatch (sends actual PDF file or direct text)
  const handleDirectWhatsAppApi = async () => {
    setStatusMessage(null);
    if (!recipientPhone.trim()) {
      setStatusMessage({
        type: 'error',
        text: 'Please enter a valid mobile number to dispatch directly via WhatsApp API.',
      });
      return;
    }

    try {
      setIsSendingDirect(true);
      const res = await sendViolationNotification({
        plate_number: vehicle.plate_number,
        channel: 'whatsapp_direct',
        recipient_phone: recipientPhone.trim(),
        officer_name: officerName.trim(),
        violation_count: vehicle.total_violations,
        message_type: isChallan ? 'challan' : 'warning',
        custom_message: customNote.trim() || undefined,
        fine_amount: vehicle.fine_amount,
        challan_id: vehicle.challan_id || undefined,
      });

      setStatusMessage({
        type: 'success',
        text: res.message || (isChallan ? 'Official PDF document delivered directly to officer in WhatsApp!' : 'Official warning notice delivered to WhatsApp!'),
      });

      if (onNotificationSent) onNotificationSent();
    } catch (err: any) {
      const errMsg = err.message || 'Failed to dispatch via WhatsApp Cloud API.';
      const isConfigErr = errMsg.toLowerCase().includes('configured') || errMsg.toLowerCase().includes('token') || errMsg.toLowerCase().includes('phone number id');
      setStatusMessage({
        type: 'error',
        text: errMsg,
        isApiConfigErr: isConfigErr,
      });
    } finally {
      setIsSendingDirect(false);
    }
  };

  // Manual Click-to-Chat Fallback (Auto-downloads PDF & opens chat)
  const handleManualWhatsApp = () => {
    setStatusMessage(null);
    const text = previewText();
    const phoneDigits = cleanPhoneForWhatsApp(recipientPhone);
    const waUrl = phoneDigits
      ? `https://api.whatsapp.com/send?phone=${phoneDigits}&text=${encodeURIComponent(text)}`
      : `https://api.whatsapp.com/send?text=${encodeURIComponent(text)}`;

    // 1. Copy notice to clipboard
    navigator.clipboard.writeText(text).catch(() => {});

    // 2. Auto-download PDF document if challan
    if (isChallan) {
      const pdfUrl = authenticatedResourceUrl(`/api/challan/pdf/${encodeURIComponent(vehicle.plate_number)}`);
      const dlLink = document.createElement('a');
      dlLink.href = pdfUrl;
      dlLink.download = `E-Challan_${vehicle.plate_number}.pdf`;
      document.body.appendChild(dlLink);
      dlLink.click();
      document.body.removeChild(dlLink);
    }

    // 3. Open WhatsApp chat
    window.open(waUrl, '_blank', 'noopener,noreferrer');
    setStatusMessage({
      type: 'success',
      text: isChallan
        ? 'Official PDF Challan downloaded & WhatsApp opened with notice text!'
        : 'WhatsApp opened with pre-filled official violation notice!',
    });

    if (onNotificationSent) onNotificationSent();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`WhatsApp Dispatch Notice: ${vehicle.plate_number}`}
      maxWidth="max-w-2xl"
      footer={
        <div className="flex flex-col sm:flex-row items-center justify-between w-full gap-3">
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <button
              type="button"
              onClick={onClose}
              className="h-9 btn-secondary text-xs px-4 rounded-xl flex items-center justify-center"
            >
              Close
            </button>

            <button
              type="button"
              onClick={handleCopyMessage}
              className="h-9 btn-secondary text-xs px-3 flex items-center justify-center gap-1.5 hover:text-emerald-300 transition-all border-emerald-500/30 rounded-xl"
              title="Copy formatted notice to clipboard"
            >
              {copied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
              <span>{copied ? 'Copied!' : 'Copy Text'}</span>
            </button>

            {onOpenChallanModal && (
              <button
                type="button"
                onClick={() => {
                  onClose();
                  onOpenChallanModal(vehicle);
                }}
                className="h-9 btn-secondary text-xs px-3 flex items-center justify-center gap-1.5 text-rose-300 hover:text-rose-100 border border-rose-500/40 rounded-xl hover:bg-rose-500/10 transition-all"
                title="View and generate official fee challan"
              >
                <FileText size={13} className="text-rose-400" />
                <span>View Challan</span>
              </button>
            )}
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
            {/* Manual Web Link Fallback */}
            <button
              type="button"
              onClick={handleManualWhatsApp}
              className="h-9 btn-secondary text-xs px-3 flex items-center justify-center gap-1.5 text-slate-300 hover:text-white rounded-xl"
              title="Open chat in WhatsApp Web or Mobile App"
            >
              <Share2 size={13} />
              <span>WhatsApp Web</span>
            </button>

            {/* Direct Meta / Gateway API Dispatch */}
            <button
              type="button"
              disabled={isSendingDirect}
              onClick={handleDirectWhatsAppApi}
              className="h-9 text-xs px-4 rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg transition-all bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/30 hover:scale-105 active:scale-95 disabled:opacity-50"
            >
              {isSendingDirect ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>Transmitting...</span>
                </>
              ) : (
                <>
                  <Send size={13} />
                  <span>{isChallan ? 'Send PDF Direct' : 'Send Direct Notice'}</span>
                </>
              )}
            </button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        {/* Status Notification Toast */}
        {statusMessage && (
          <div
            className={`p-3 rounded-lg text-xs flex flex-col gap-2 animate-fade-in ${
              statusMessage.type === 'success'
                ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300'
                : 'bg-rose-500/15 border border-rose-500/30 text-rose-300'
            }`}
          >
            <div className="flex items-center gap-2">
              {statusMessage.type === 'success' ? (
                <CheckCircle2 size={16} className="shrink-0 text-emerald-400" />
              ) : (
                <AlertCircle size={16} className="shrink-0 text-rose-400" />
              )}
              <span className="flex-1">{statusMessage.text}</span>
            </div>
            {statusMessage.isApiConfigErr && onOpenWhatsAppSettings && (
              <div className="mt-1 pl-6">
                <button
                  type="button"
                  onClick={onOpenWhatsAppSettings}
                  className="py-1 px-3 rounded-md text-[11px] font-semibold bg-rose-600/30 hover:bg-rose-600/50 text-rose-200 border border-rose-500/40 inline-flex items-center gap-1.5 transition-all"
                >
                  <Settings size={12} />
                  <span>Configure Meta WhatsApp Cloud API Settings</span>
                </button>
              </div>
            )}
          </div>
        )}

        {/* Vehicle & Escalation Header Banner */}
        <div
          className={`p-3.5 rounded-xl border flex items-center justify-between ${
            isChallan
              ? 'bg-rose-950/30 border-rose-500/40 text-rose-200'
              : 'bg-amber-950/30 border-amber-500/40 text-amber-200'
          }`}
        >
          <div className="flex items-center gap-3">
            <div
              className={`w-9 h-9 rounded-lg flex items-center justify-center font-bold text-sm ${
                isChallan ? 'bg-rose-500/20 text-rose-400' : 'bg-amber-500/20 text-amber-400'
              }`}
            >
              <ShieldAlert size={18} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono font-black text-sm text-white tracking-wider">
                  {vehicle.plate_number}
                </span>
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                    isChallan
                      ? 'bg-rose-500/30 text-rose-200 border border-rose-500/50'
                      : 'bg-amber-500/30 text-amber-200 border border-amber-500/50'
                  }`}
                >
                  {tierTitle}
                </span>
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5">
                {vehicle.department} • {vehicle.total_violations} Total Violation Incident(s)
              </p>
            </div>
          </div>

          {isChallan && (
            <div className="text-right">
              <span className="text-[10px] text-slate-400 uppercase">Penalty Fine</span>
              <div className="font-mono font-extrabold text-sm text-rose-400">
                PKR {vehicle.fine_amount.toLocaleString()}
              </div>
            </div>
          )}
        </div>

        {/* Recipient Input Fields */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 bg-slate-900/60 p-3.5 rounded-xl border border-slate-800">
          <div>
            <label className="block text-[10px] font-semibold text-slate-400 mb-1">
              Officer / Custodian Name
            </label>
            <div className="relative">
              <User size={12} className="absolute left-2.5 top-2.5 text-slate-500" />
              <input
                type="text"
                value={officerName}
                onChange={(e) => setOfficerName(e.target.value)}
                placeholder="e.g. Capt. Tariq"
                className="glass-input text-xs py-1.5 pl-7"
              />
            </div>
          </div>

          <div>
            <label className="block text-[10px] font-semibold text-emerald-400 mb-1 flex items-center justify-between">
              <span>Mobile / WhatsApp Number</span>
              <span className="text-[9px] text-slate-400 font-normal">e.g. 03001234567</span>
            </label>
            <div className="relative">
              <Phone size={12} className="absolute left-2.5 top-2.5 text-emerald-400" />
              <input
                type="text"
                value={recipientPhone}
                onChange={(e) => setRecipientPhone(e.target.value)}
                placeholder="03001234567 (or leave blank to pick contact)"
                className="glass-input text-xs py-1.5 pl-7 font-mono border-emerald-500/30 focus:border-emerald-400"
              />
            </div>
          </div>
        </div>

        {/* Custom Directive / Command Note */}
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">
            Command Directive / Additional Note (Optional)
          </label>
          <input
            type="text"
            value={customNote}
            onChange={(e) => setCustomNote(e.target.value)}
            placeholder="e.g. Vehicle spotted in unauthorized sector after hours without trip permit."
            className="glass-input text-xs py-2"
          />
        </div>

        {/* Live Message Preview Box with Copy Button */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
              <MessageCircle size={13} />
              <span>WhatsApp Formatted Message Preview</span>
            </label>
            <button
              type="button"
              onClick={handleCopyMessage}
              className="text-[11px] text-slate-300 hover:text-emerald-300 flex items-center gap-1 py-0.5 px-2 rounded bg-slate-800/80 hover:bg-slate-800 transition-all border border-slate-700"
            >
              {copied ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
              <span>{copied ? 'Copied!' : 'Copy Text'}</span>
            </button>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 whitespace-pre-line leading-relaxed max-h-52 overflow-y-auto shadow-inner select-all">
            {previewText()}
          </div>
        </div>
      </div>
    </Modal>
  );
};
