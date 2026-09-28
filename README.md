# 🚗 Just Meter — AJK Government Car Surveillance & ANPR System

An end-to-end intelligent Automated Number Plate Recognition (ANPR) and government fleet compliance surveillance system. Streams video from any mobile phone or external camera over HTTPS, detects vehicles using YOLO, extracts license plate characters using FastALPR/ONNX OCR, assesses compliance against an authorized government registry in real time, and logs violations with automated fine calculation, challan PDF generation, and multi-channel alerting (Email & WhatsApp).

---

## 🌟 Key Features

- **📱 Zero-Install Mobile Scanner**: Turn any smartphone into an intelligent edge ANPR camera scanner via a responsive web portal over HTTPS.
- **⚡ Real-Time High-Speed Inference**: Powered by Ultralytics YOLOv11 (`yolo11n.pt`) and FastALPR ONNX OCR with plate tracking and duplicate cooldown filtering.
- **🏛️ Authorized Government Fleet Registry**: Validates observed vehicles against department assignments, duty shifts, and authorized administrative divisions (e.g., *Mzd. Division*, *Mirpur Division*, *Poonch Division*, *Federal Territory*, *Pakistan Provinces*).
- **⚠️ Automated Compliance & Violations**: Detects unauthorized division movement or outside-duty-hours usage; categorizes progressive violation tiers (Warning 1, Warning 2, Warning 3, Challan Issued with fines).
- **📄 Instant Challan PDF Generation**: Generates official branded government violation notices with vehicle metadata, violation timestamp, GPS location, and camera snapshot evidence.
- **📲 Multi-Channel Alerting**: Instant notification dispatch via SMTP Email and WhatsApp (Meta Cloud API or Baileys Node.js Bridge).
- **📊 Modern Web Dashboard**: React + TypeScript + Vite dashboard with live WebSocket video feed, interactive stats, compliance charts, registry management, and violation resolution.

---

## 📋 Prerequisites

Before running the project, ensure you have the following installed on your host machine:

1. **Python**: Version `3.10` to `3.12` ([python.org](https://www.python.org/))
2. **Node.js**: Version `18.x` or `20.x` LTS and `npm` ([nodejs.org](https://www.nodejs.org/))
3. **Git**: Installed and configured
4. **Smartphone / Tablet**: Any device with a modern browser (Safari, Chrome) and camera

---

## 🚀 Step-by-Step Setup & Execution Guide

Follow these sequential steps in separate terminal windows (PowerShell or Bash) in the project root directory:

```
c:\Users\IntelPoint\Documents\Codex\2026-08-12\so\outputs\mobile-anpr
```

---

### Step 1: Create and Activate Python Virtual Environment

Open your first terminal in the project root and run:

#### Windows (PowerShell):
```powershell
# 1. Create a virtual environment named .venv
python -m venv .venv

# 2. Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Upgrade pip and install all backend requirements
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> **Note for PowerShell execution policy:** If you encounter a script execution restriction, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and rerun the activation script.

#### macOS / Linux (Bash):
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

### Step 2: Configure Environment Variables

Create your `.env` configuration file from the template:

```powershell
# Copy the example file to .env
Copy-Item .env.example .env   # On Windows
# OR
cp .env.example .env          # On Linux/macOS
```

Edit `.env` to configure your SMTP credentials or leave default settings for local testing.

---

### Step 3: Start the Backend FastAPI / Uvicorn Server

In the **same activated virtual environment terminal**, start the Uvicorn server:

```powershell
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Camera Capture Portal**: [http://localhost:8000/](http://localhost:8000/)

---

### Step 4: Expose Camera via NPX Tunnel (for Mobile Capture)

Mobile web browsers require a secure **HTTPS** connection to access device cameras and GPS coordinates. Open a **second terminal window** and run `localtunnel`:

```powershell
npx localtunnel --port 8000
```

1. LocalTunnel will output a public URL, for example: `https://brave-frog-42.loca.lt`
2. Open this URL on your **mobile phone browser**.
3. (If prompted with LocalTunnel's IP verification page, enter your public IP address displayed on screen and submit).
4. Tap **Start Camera**, grant camera & location permissions, select the operational division/area, and point the phone towards vehicle traffic.

---

### Step 5: Start the Frontend Management Dashboard

Open a **third terminal window** to start the interactive React control dashboard:

```powershell
# 1. Navigate into the frontend directory
cd frontend

# 2. Install Node.js dependencies (first time only)
npm install

# 3. Start the Vite development server
npm run dev
```

The Vite dev server will launch at:
- **Local Dashboard**: [http://localhost:5173](http://localhost:5173)

Log in using the administrator credentials:
- **Email**: `admin@anpr.gov`
- **Password**: `admin123`

---

### Step 6 (Optional): WhatsApp Bridge Service

If you wish to send violation notices and PDF challans directly via WhatsApp without Meta Cloud API keys, start the built-in Baileys bridge in a **fourth terminal**:

```powershell
cd whatsapp-bridge
npm install
npm start
```
Scan the terminal QR code or request a pairing code from the dashboard under **WhatsApp Settings**.

---

## 📂 Project Structure

```
mobile-anpr/
├── backend/
│   ├── config.py              # System paths, timezone, threshold configurations
│   ├── detectors.py           # FastALPR OCR and Ultralytics YOLO inference pipeline
│   ├── mailer.py              # SMTP email dispatch & HTML violation templates
│   ├── main.py                # FastAPI endpoints, WebSocket broadcaster, routes
│   ├── models.py              # Pydantic validation schemas & request models
│   ├── pdf_generator.py       # Official e-challan PDF notice generation
│   ├── storage.py             # CSV database manager & snapshot image writer
│   ├── whatsapp_bridge.py     # Local Baileys Node.js WhatsApp client
│   └── whatsapp_meta.py       # Meta WhatsApp Cloud API client
├── data/
│   ├── approved_government_vehicles.csv  # Authorized government vehicle database
│   ├── detections.csv         # Raw vehicle & plate capture log
│   ├── government_vehicles_spotted.csv   # Filtered government sightings & violations
│   └── snapshots/             # Saved vehicle image evidence
├── frontend/
│   ├── src/
│   │   ├── api/client.ts      # REST API & WebSocket client
│   │   ├── components/        # Modals, Navbar, Header, Sidebar
│   │   ├── context/           # Auth and session context
│   │   ├── pages/             # Live Camera, Spotted, Violations, Registry, Login
│   │   ├── App.tsx            # Main application router
│   │   └── main.tsx           # Application entry point
│   ├── package.json           # Frontend dependencies
│   └── vite.config.ts         # Vite configuration with proxy rules
├── phone/
│   └── camera.html            # Standalone mobile scanner web interface
├── whatsapp-bridge/
│   ├── server.js              # Baileys WhatsApp microservice
│   └── package.json           # Bridge dependencies
├── .env.example               # Environment variables template
├── .gitignore                 # Git ignore rules
├── requirements.txt           # Python backend dependencies
└── yolo11n.pt                 # Ultralytics YOLOv11 nano model weights
```

---

## 🔒 Security & Safe Deployment

- **Sensitive Files Excluded**: `.env` and `whatsapp-bridge/auth_info/` are excluded by `.gitignore` to safeguard secrets and session keys.
- **Authentication**: Admin dashboard access is protected with session state and secure REST endpoints.
- **Network Compatibility**: Local development supports both local LAN (`http://<PC_IP>:8000`) and public HTTPS tunnels (`localtunnel` / `cloudflared`).

---

## 📜 License & Compliance

Designed for authorized governmental fleet monitoring and traffic management. Use solely in compliance with applicable traffic surveillance, privacy, and data protection laws.
