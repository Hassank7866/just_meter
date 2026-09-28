const express = require('express');
const cors = require('cors');
const QRCode = require('qrcode');
const fs = require('fs');
const path = require('path');
const pino = require('pino');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
} = require('@whiskeysockets/baileys');

const app = express();
app.use(cors());
app.use(express.json({ limit: '50mb' }));

const PORT = process.env.PORT || 5005;
const AUTH_DIR = path.join(__dirname, 'auth_info');

if (!fs.existsSync(AUTH_DIR)) {
  fs.mkdirSync(AUTH_DIR, { recursive: true });
}

let sock = null;
let connectionStatus = 'INITIALIZING'; // 'INITIALIZING', 'SCAN_QR', 'CONNECTING', 'CONNECTED', 'DISCONNECTED'
let qrCodeDataUrl = null;
let rawQrCode = null;
let connectedUser = null;
let lastError = null;
let pairingCode = null;
let isStarting = false;

function clearAuthDir() {
  try {
    if (fs.existsSync(AUTH_DIR)) {
      const files = fs.readdirSync(AUTH_DIR);
      for (const file of files) {
        try {
          fs.rmSync(path.join(AUTH_DIR, file), { recursive: true, force: true, maxRetries: 5, retryDelay: 50 });
        } catch (e) {}
      }
    }
  } catch (err) {
    console.error('[WhatsApp Bridge] Error clearing auth directory:', err);
  }
}

function normalizePhone(rawPhone) {
  let digits = String(rawPhone || '').replace(/\D/g, '');
  if (digits.startsWith('0') && digits.length === 11) {
    digits = '92' + digits.slice(1);
  } else if (digits.length === 10 && digits.startsWith('3')) {
    digits = '92' + digits;
  }
  return digits;
}

async function startWhatsAppSocket() {
  if (isStarting) return;
  isStarting = true;

  try {
    if (sock) {
      try {
        sock.ev.removeAllListeners();
        sock.end();
      } catch (e) {}
      sock = null;
    }

    connectionStatus = 'INITIALIZING';
    lastError = null;

    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version } = await fetchLatestBaileysVersion().catch(() => ({ version: [2, 3000, 1015901307] }));

    sock = makeWASocket({
      version,
      auth: state,
      printQRInTerminal: false,
      logger: pino({ level: 'silent' }),
      browser: ['ANPR Fleet Command', 'Chrome', '120.0.0.0'],
      syncFullHistory: false,
      connectTimeoutMs: 60000,
      keepAliveIntervalMs: 25000,
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
      const { connection, lastDisconnect, qr } = update;

      if (qr) {
        connectionStatus = 'SCAN_QR';
        rawQrCode = qr;
        try {
          qrCodeDataUrl = await QRCode.toDataURL(qr, {
            width: 320,
            margin: 2,
            color: {
              dark: '#0f172a',
              light: '#ffffff',
            },
          });
        } catch (e) {
          console.error('Error generating QR data URL', e);
        }
      }

      if (connection === 'connecting') {
        connectionStatus = 'CONNECTING';
      } else if (connection === 'open') {
        connectionStatus = 'CONNECTED';
        qrCodeDataUrl = null;
        rawQrCode = null;
        pairingCode = null;
        const userJid = sock.user?.id || '';
        const userNum = userJid.split(':')[0] || userJid.split('@')[0];
        connectedUser = {
          id: userJid,
          phone: userNum,
          name: sock.user?.name || 'ANPR Dispatcher',
        };
        console.log(`[WhatsApp Bridge] Successfully connected as +${userNum}`);
      } else if (connection === 'close') {
        const statusCode = lastDisconnect?.error?.output?.statusCode;
        const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
        console.log(`[WhatsApp Bridge] Connection closed (code ${statusCode}). Reconnecting: ${shouldReconnect}`);
        
        connectionStatus = 'DISCONNECTED';
        connectedUser = null;
        lastError = `Closed with code ${statusCode}: ${lastDisconnect?.error?.message || lastDisconnect?.error || 'Unknown'}`;

        if (statusCode === DisconnectReason.loggedOut) {
          clearAuthDir();
        }

        setTimeout(() => {
          isStarting = false;
          startWhatsAppSocket();
        }, shouldReconnect ? 2000 : 1000);
      }
    });
  } catch (err) {
    console.error('[WhatsApp Bridge] Startup error:', err);
    connectionStatus = 'DISCONNECTED';
    lastError = String(err.message || err);
    setTimeout(() => {
      isStarting = false;
      startWhatsAppSocket();
    }, 4000);
  } finally {
    isStarting = false;
  }
}

// 1. Status API
app.get('/status', (req, res) => {
  res.json({
    status: connectionStatus,
    connected: connectionStatus === 'CONNECTED',
    user: connectedUser,
    qr: qrCodeDataUrl,
    pairingCode: pairingCode,
    error: lastError,
    timestamp: new Date().toISOString(),
  });
});

// 2. Pairing Code API (Type 8-digit code on phone)
app.post('/pairing-code', async (req, res) => {
  try {
    const { phone } = req.body;
    const cleanPhone = normalizePhone(phone);
    if (!cleanPhone || cleanPhone.length < 10) {
      return res.status(400).json({ success: false, error: 'Please provide a valid mobile number (e.g. 03001234567)' });
    }

    if (!sock) {
      return res.status(503).json({ success: false, error: 'WhatsApp service is initializing. Please retry in 3 seconds.' });
    }

    const code = await sock.requestPairingCode(cleanPhone);
    pairingCode = code;
    console.log(`[WhatsApp Bridge] Pairing Code generated for +${cleanPhone}: ${code}`);
    return res.json({
      success: true,
      code: code,
      phone: cleanPhone,
      message: `Pairing Code: ${code}. Enter this code in WhatsApp > Linked Devices > Link with phone number`,
    });
  } catch (err) {
    console.error('[WhatsApp Bridge] Pairing Code error:', err);
    return res.status(500).json({
      success: false,
      error: `Failed to request pairing code: ${err.message || err}`,
    });
  }
});

// 3. Send Document API (PDF E-Challan)
app.post('/send-document', async (req, res) => {
  try {
    if (connectionStatus !== 'CONNECTED' || !sock) {
      return res.status(503).json({
        success: false,
        error: 'WhatsApp Bridge is not connected. Please scan the QR code or link your phone in the WhatsApp settings modal.',
      });
    }

    const { phone, filename, base64, caption } = req.body;
    const cleanPhone = normalizePhone(phone);
    if (!cleanPhone) {
      return res.status(400).json({ success: false, error: 'Invalid phone number.' });
    }

    if (!base64) {
      return res.status(400).json({ success: false, error: 'Missing PDF binary content.' });
    }

    const jid = `${cleanPhone}@s.whatsapp.net`;
    const pdfBuffer = Buffer.from(base64, 'base64');
    const docName = filename || 'Official_E_Challan.pdf';

    const sentMsg = await sock.sendMessage(jid, {
      document: pdfBuffer,
      mimetype: 'application/pdf',
      fileName: docName,
      caption: caption || undefined,
    });

    console.log(`[WhatsApp Bridge] Document sent to ${jid}, Msg ID: ${sentMsg?.key?.id}`);
    return res.json({
      success: true,
      messageId: sentMsg?.key?.id,
      recipient: cleanPhone,
      message: `Official PDF document delivered directly to +${cleanPhone} via WhatsApp!`,
    });
  } catch (err) {
    console.error('[WhatsApp Bridge] Send Document error:', err);
    return res.status(500).json({
      success: false,
      error: `Failed to deliver PDF via WhatsApp: ${err.message || err}`,
    });
  }
});

// 4. Send Text Notice API
app.post('/send-text', async (req, res) => {
  try {
    if (connectionStatus !== 'CONNECTED' || !sock) {
      return res.status(503).json({
        success: false,
        error: 'WhatsApp Bridge is not connected. Please link your WhatsApp first.',
      });
    }

    const { phone, message } = req.body;
    const cleanPhone = normalizePhone(phone);
    if (!cleanPhone || !message) {
      return res.status(400).json({ success: false, error: 'Missing phone or message.' });
    }

    const jid = `${cleanPhone}@s.whatsapp.net`;
    const sentMsg = await sock.sendMessage(jid, { text: message });

    console.log(`[WhatsApp Bridge] Text sent to ${jid}, Msg ID: ${sentMsg?.key?.id}`);
    return res.json({
      success: true,
      messageId: sentMsg?.key?.id,
      recipient: cleanPhone,
      message: `Official notice delivered to +${cleanPhone} via WhatsApp!`,
    });
  } catch (err) {
    console.error('[WhatsApp Bridge] Send Text error:', err);
    return res.status(500).json({
      success: false,
      error: `Failed to send WhatsApp message: ${err.message || err}`,
    });
  }
});

// 5. Logout / Disconnect API
app.post('/logout', async (req, res) => {
  try {
    if (sock) {
      try {
        await sock.logout().catch(() => {});
      } catch (e) {}
      try {
        sock.ev.removeAllListeners();
        sock.end();
      } catch (e) {}
      sock = null;
    }
    clearAuthDir();
    connectionStatus = 'INITIALIZING';
    connectedUser = null;
    qrCodeDataUrl = null;
    rawQrCode = null;
    pairingCode = null;
    lastError = null;
    isStarting = false;
    setTimeout(() => {
      startWhatsAppSocket();
    }, 500);
    return res.json({ success: true, message: 'Disconnected and session cleared.' });
  } catch (err) {
    return res.status(500).json({ success: false, error: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`[WhatsApp Bridge Server] Running on http://localhost:${PORT}`);
  startWhatsAppSocket();
});
