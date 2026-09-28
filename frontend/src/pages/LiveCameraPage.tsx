import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Play,
  Square,
  Maximize2,
  Minimize2,
  Volume2,
  VolumeX,
  Activity,
  MapPin,
  Smartphone,
  Laptop,
  CheckCircle2,
  QrCode,
  ShieldCheck,
} from 'lucide-react';
import {
  LiveFrameData,
  getLiveCameraWebSocketUrl,
  fetchLatestLiveFrame,
  analyzeCameraFrame,
  fetchCameraAreas,
} from '../api/client';

interface LiveEventLog {
  id: string;
  timestamp: string;
  plate_number: string;
  confidence: number;
  is_violation: boolean;
  camera_area: string;
  violation_reason?: string;
  department?: string;
  vehicle_type?: string;
  image_snapshot?: string;
}

const SurveillanceCameraLogo: React.FC<{
  streamSource: 'mobile' | 'local';
  connectionStatus: 'connecting' | 'connected' | 'offline';
  onPairMobile: () => void;
  onStartLocal: () => void;
}> = ({ streamSource, connectionStatus, onPairMobile, onStartLocal }) => {
  return (
    <div className="flex flex-col items-center justify-center p-6 text-center select-none animate-fade-in max-w-sm">
      {/* CCTV Security Camera SVG Graphic */}
      <div className="relative mb-3 flex items-center justify-center">
        {/* Glow halo */}
        <div className="absolute w-28 h-28 rounded-full bg-sky-500/5 border border-sky-500/15 animate-pulse" />
        <div className="absolute w-36 h-36 rounded-full border border-dashed border-slate-700/50 animate-[spin_40s_linear_infinite]" />

        <svg
          className="w-24 h-24 text-sky-400 drop-shadow-[0_10px_20px_rgba(0,0,0,0.6)] relative z-10"
          viewBox="0 0 100 100"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Wall / Ceiling mounting plate */}
          <path d="M16 26H28V38H16V26Z" fill="#1e293b" stroke="#475569" strokeWidth="2" strokeLinejoin="round" />
          <path d="M22 26V20" stroke="#64748b" strokeWidth="2.5" strokeLinecap="round" />
          <path d="M28 32H38" stroke="#64748b" strokeWidth="4" strokeLinecap="round" />

          {/* Articulated joint */}
          <circle cx="42" cy="32" r="5" fill="#0f172a" stroke="#38bdf8" strokeWidth="1.5" />

          {/* Camera mounting arm */}
          <path d="M42 36L48 46" stroke="#475569" strokeWidth="4" strokeLinecap="round" />

          {/* Camera housing / body (tactical bullet shape) */}
          <path
            d="M38 46L76 34C78 33 80 34 81 36L86 52C87 54 86 56 84 57L46 69C44 70 42 69 41 67L36 51C35 49 36 47 38 46Z"
            fill="#0f172a"
            stroke="#334155"
            strokeWidth="2"
          />

          {/* Sunshield visor over lens */}
          <path
            d="M37 43L79 30C81 29 83 30 84 32L90 50"
            stroke="#38bdf8"
            strokeWidth="2.5"
            strokeLinecap="round"
          />

          {/* Front camera lens bezel */}
          <ellipse cx="82" cy="46" rx="6" ry="11" fill="#020617" stroke="#38bdf8" strokeWidth="2" />
          {/* Lens glass reflections */}
          <ellipse cx="82" cy="46" rx="3.5" ry="6.5" fill="#0284c7" fillOpacity="0.7" />
          <circle cx="83" cy="44" r="1.5" fill="#ffffff" />

          {/* IR LED sensors */}
          <circle cx="78" cy="39" r="1" fill="#94a3b8" />
          <circle cx="79" cy="52" r="1" fill="#94a3b8" />

          {/* Standby / Active Blinking Red LED */}
          <circle cx="50" cy="48" r="2" fill="#ef4444" className="animate-ping" opacity="0.8" />
          <circle cx="50" cy="48" r="1.8" fill="#ef4444" />

          {/* Radiating radar / surveillance scanning waves */}
          <path d="M90 38C93 42 93 48 90 52" stroke="#38bdf8" strokeWidth="1.5" strokeLinecap="round" opacity="0.6" />
          <path d="M94 33C99 39 99 51 94 57" stroke="#38bdf8" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="2 2" opacity="0.4" />
        </svg>
      </div>

      {/* Title & Status */}
      <div className="space-y-1">
        <div className="flex items-center justify-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${
            connectionStatus === 'connected' ? 'bg-amber-400 animate-ping' : 'bg-rose-500'
          }`} />
          <h3 className="text-xs sm:text-sm font-bold tracking-wider text-zinc-200 uppercase font-mono">
            {streamSource === 'mobile'
              ? (connectionStatus === 'connected' ? 'Waiting for Live Stream' : 'Camera Feed Disconnected')
              : 'Laptop Camera Standby'}
          </h3>
        </div>
        <p className="text-[11px] sm:text-xs text-zinc-400 max-w-[280px] leading-relaxed mx-auto">
          {streamSource === 'mobile'
            ? 'Open scanner URL on your smartphone. Video feed and AI plates will appear automatically.'
            : 'Laptop camera is paused. Click below to start local optical surveillance.'}
        </p>
      </div>

      {/* Action Button */}
      {streamSource === 'mobile' ? (
        <button
          onClick={onPairMobile}
          className="mt-3 px-3 py-1.5 bg-zinc-800/90 hover:bg-zinc-700 text-sky-400 hover:text-sky-300 border border-zinc-700/80 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all shadow-sm"
        >
          <QrCode size={13} />
          <span>Connect Mobile Device</span>
        </button>
      ) : (
        <button
          onClick={onStartLocal}
          className="mt-3 px-3 py-1.5 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all shadow-md shadow-sky-600/30"
        >
          <Play size={13} />
          <span>Start Local Webcam</span>
        </button>
      )}
    </div>
  );
};

export const LiveCameraPage: React.FC = () => {
  // Stream Source Selection
  const [streamSource, setStreamSource] = useState<'mobile' | 'local'>('mobile');
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'offline'>('connecting');
  const [liveData, setLiveData] = useState<LiveFrameData | null>(null);
  const [isMobileFeedActive, setIsMobileFeedActive] = useState(false);
  const lastFrameReceivedRef = useRef<number>(0);
  const [latencyMs, setLatencyMs] = useState<number>(0);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [showPhoneQrModal, setShowPhoneQrModal] = useState(false);
  const [totalDetectionsCount, setTotalDetectionsCount] = useState({ vehicles: 0, plates: 0, violations: 0 });
  const [eventLogs, setEventLogs] = useState<LiveEventLog[]>([]);
  
  // Display & HUD Toggles
  const [showVehicleBoxes, setShowVehicleBoxes] = useState(true);
  const [showPlateBoxes, setShowPlateBoxes] = useState(true);
  const [showLabels, setShowLabels] = useState(true);

  // Local Webcam State
  const [localCameraRunning, setLocalCameraRunning] = useState(false);
  const localCameraRunningRef = useRef(false);
  const isAnalyzingRef = useRef(false);

  // Computed feed active indicator
  const isFeedActive = streamSource === 'local' ? localCameraRunning : isMobileFeedActive;
  const [selectedCameraArea, setSelectedCameraArea] = useState('Mzd. Division');
  const [availableAreas, setAvailableAreas] = useState<string[]>([
    'Mzd. Division',
    'Mirpur Division',
    'Poonch Division',
    'Federal Territory',
    'Pakistan Provinces',
  ]);

  // DOM & Media Refs
  const viewportRef = useRef<HTMLDivElement>(null);
  const localVideoRef = useRef<HTMLVideoElement>(null);
  const localMediaStreamRef = useRef<MediaStream | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const lastSoundTimeRef = useRef<number>(0);

  // Audio synthesize beep/chime
  const playChime = (isViolation = false) => {
    if (!soundEnabled) return;
    const now = Date.now();
    if (now - lastSoundTimeRef.current < 800) return; // debounce
    lastSoundTimeRef.current = now;

    try {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = isViolation ? 'sawtooth' : 'sine';
      osc.frequency.setValueAtTime(isViolation ? 440 : 880, ctx.currentTime);
      if (isViolation) {
        osc.frequency.exponentialRampToValueAtTime(220, ctx.currentTime + 0.35);
      } else {
        osc.frequency.exponentialRampToValueAtTime(1320, ctx.currentTime + 0.2);
      }

      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + (isViolation ? 0.35 : 0.2));

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + (isViolation ? 0.35 : 0.2));
    } catch {
      // Audio context might be restricted
    }
  };

  useEffect(() => {
    fetchCameraAreas()
      .then(setAvailableAreas)
      .catch(() => {});
  }, []);

  const handleIncomingFrame = (data: LiveFrameData) => {
    setLiveData(data);

    const numVehicles = data.vehicles?.length || 0;
    const numPlates = data.plates?.length || 0;
    let newViolations = 0;

    data.plates?.forEach((plate) => {
      const isViol = plate.compliance?.status === 'VIOLATION';
      if (isViol) newViolations += 1;

      const newLog: LiveEventLog = {
        id: `${plate.plate_number}-${Date.now()}`,
        timestamp: new Date().toLocaleTimeString('en-PK', { timeZone: 'Asia/Karachi', hour12: true, hour: '2-digit', minute:'2-digit', second:'2-digit' }),
        camera_area: data.camera_area || 'Fixed Camera',
        plate_number: plate.plate_number,
        confidence: plate.confidence,
        is_violation: isViol,
        violation_reason: plate.compliance?.violation_criteria || '',
        department: plate.government_match?.department,
        image_snapshot: data.image_data,
      };

      setEventLogs((prev) => [newLog, ...prev.slice(0, 49)]); // Keep last 50 logs
    });

    if (numVehicles > 0 || numPlates > 0) {
      setTotalDetectionsCount((prev) => ({
        vehicles: prev.vehicles + numVehicles,
        plates: prev.plates + numPlates,
        violations: prev.violations + newViolations,
      }));

      playChime(newViolations > 0);
    }
  };

  useEffect(() => {
    if (streamSource !== 'mobile') {
      setIsMobileFeedActive(false);
      lastFrameReceivedRef.current = 0;
      return;
    }

    let socket: WebSocket | null = null;
    let isMounted = true;
    let pingInterval: any = null;
    let watchdogInterval: any = null;

    const connectWs = () => {
      try {
        setConnectionStatus('connecting');
        const url = getLiveCameraWebSocketUrl();
        socket = new WebSocket(url);
        wsRef.current = socket;

        socket.onopen = () => {
          if (!isMounted) return;
          setConnectionStatus('connected');
          pingInterval = setInterval(() => {
            if (socket?.readyState === WebSocket.OPEN) {
              socket.send('ping');
            }
          }, 15000);
        };

        socket.onmessage = (event) => {
          if (!isMounted) return;
          if (event.data === 'pong') return;
          try {
            const parsed = JSON.parse(event.data);
            if (parsed.timestamp && parsed.image_data) {
              lastFrameReceivedRef.current = Date.now();
              setIsMobileFeedActive(true);
              handleIncomingFrame(parsed);
            }
          } catch (err) {
            console.error('Error parsing live frame payload', err);
          }
        };

        socket.onerror = () => {
          if (!isMounted) return;
          setConnectionStatus('offline');
          setIsMobileFeedActive(false);
          setLiveData(null); // Clear previous frame immediately
        };

        socket.onclose = () => {
          if (!isMounted) return;
          setConnectionStatus('offline');
          setIsMobileFeedActive(false);
          setLiveData(null); // Clear previous frame immediately
          setTimeout(() => {
            if (isMounted && streamSource === 'mobile') {
              connectWs();
            }
          }, 3000);
        };
      } catch {
        setConnectionStatus('offline');
        setIsMobileFeedActive(false);
        setLiveData(null);
      }
    };

    // Watchdog timer: checks every 600ms if incoming frames have stopped
    watchdogInterval = setInterval(() => {
      if (lastFrameReceivedRef.current > 0 && Date.now() - lastFrameReceivedRef.current > 2500) {
        lastFrameReceivedRef.current = 0;
        setIsMobileFeedActive(false);
        setLiveData(null); // Clear frame so it doesn't hang on previous frame!
      }
    }, 600);

    // Only set live data on mount if the latest frame is actually active right now (< 2500ms)
    fetchLatestLiveFrame().then((latest) => {
      if (latest && isMounted && latest.timestamp && latest.image_data) {
        const frameAgeMs = Date.now() - new Date(latest.timestamp).getTime();
        if (frameAgeMs < 2500) {
          lastFrameReceivedRef.current = Date.now();
          setIsMobileFeedActive(true);
          handleIncomingFrame(latest);
        } else {
          setIsMobileFeedActive(false);
          setLiveData(null);
        }
      }
    });

    connectWs();

    return () => {
      isMounted = false;
      if (pingInterval) clearInterval(pingInterval);
      if (watchdogInterval) clearInterval(watchdogInterval);
      if (socket) {
        socket.close();
      }
      setIsMobileFeedActive(false);
      lastFrameReceivedRef.current = 0;
    };
  }, [streamSource]);

  const captureAndAnalyzeLocalFrame = async () => {
    if (isAnalyzingRef.current) return;
    const video = localVideoRef.current;
    if (!video || video.videoWidth === 0) return;
    isAnalyzingRef.current = true;

    try {
      const offscreen = document.createElement('canvas');
      const maxW = 960;
      let targetW = video.videoWidth;
      let targetH = video.videoHeight;
      if (targetW > maxW) {
        const scale = maxW / targetW;
        targetW = maxW;
        targetH = Math.round(targetH * scale);
      }
      offscreen.width = targetW;
      offscreen.height = targetH;
      const ctx = offscreen.getContext('2d');
      if (!ctx) return;
      ctx.drawImage(video, 0, 0, targetW, targetH);

      const blob = await new Promise<Blob | null>((resolve) => offscreen.toBlob(resolve, 'image/jpeg', 0.70));
      if (!blob) return;

      const formData = new FormData();
      formData.append('file', blob, 'webcam_frame.jpg');
      formData.append('camera_area', selectedCameraArea);

      const startT = Date.now();
      const result = await analyzeCameraFrame(formData);
      setLatencyMs(Date.now() - startT);
      handleIncomingFrame(result);
    } catch (err) {
      console.error('Local frame analysis error', err);
    } finally {
      isAnalyzingRef.current = false;
    }
  };

  const startLocalWebcam = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'environment' },
        audio: false,
      });
      if (localVideoRef.current) {
        localVideoRef.current.srcObject = stream;
      }
      localMediaStreamRef.current = stream;
      localCameraRunningRef.current = true;
      setLocalCameraRunning(true);

      stream.getVideoTracks().forEach((track) => {
        track.onended = () => {
          stopLocalWebcam();
        };
      });

      const runLoop = async () => {
        while (localCameraRunningRef.current) {
          await captureAndAnalyzeLocalFrame();
          await new Promise((r) => setTimeout(r, 120));
        }
      };
      runLoop();
    } catch (err) {
      alert('Could not start local camera: ' + (err instanceof Error ? err.message : String(err)));
      stopLocalWebcam();
    }
  };

  const stopLocalWebcam = () => {
    localCameraRunningRef.current = false;
    if (localMediaStreamRef.current) {
      localMediaStreamRef.current.getTracks().forEach((track) => track.stop());
      localMediaStreamRef.current = null;
    }
    if (localVideoRef.current) {
      localVideoRef.current.srcObject = null;
    }
    setLocalCameraRunning(false);
    setLiveData(null); // Clear previous frame!
  };

  const toggleFullscreen = () => {
    if (!viewportRef.current) return;
    if (!document.fullscreenElement) {
      viewportRef.current.requestFullscreen().catch(() => {});
      setIsFullscreen(true);
    } else {
      document.exitFullscreen().catch(() => {});
      setIsFullscreen(false);
    }
  };

  const frameWidth = liveData?.frame_width || 1280;
  const frameHeight = liveData?.frame_height || 720;

  const vehicleBoxes = useMemo(() => {
    if (!showVehicleBoxes || !liveData?.vehicles) return [];
    return liveData.vehicles.map((v, idx) => {
      const [x1, y1, x2, y2] = v.bbox;
      const left = (x1 / frameWidth) * 100;
      const top = (y1 / frameHeight) * 100;
      const width = ((x2 - x1) / frameWidth) * 100;
      const height = ((y2 - y1) / frameHeight) * 100;

      const getVehicleIcon = (label: string) => {
        const l = label.toLowerCase();
        if (l.includes('motorcycle')) return '🏍️';
        if (l.includes('bus')) return '🚌';
        if (l.includes('truck')) return '🚚';
        return '🚗';
      };

      return {
        id: `veh-${idx}`,
        left: `${Math.max(0, Math.min(100, left))}%`,
        top: `${Math.max(0, Math.min(100, top))}%`,
        width: `${Math.max(0, Math.min(100 - left, width))}%`,
        height: `${Math.max(0, Math.min(100 - top, height))}%`,
        label: v.label.toUpperCase(),
        confidence: Math.round(v.confidence * 100),
        icon: getVehicleIcon(v.label),
      };
    });
  }, [liveData?.vehicles, frameWidth, frameHeight, showVehicleBoxes]);

  const plateBoxes = useMemo(() => {
    if (!showPlateBoxes || !liveData?.plates) return [];
    return liveData.plates.map((p, idx) => {
      const [x1, y1, x2, y2] = p.bbox;
      const left = (x1 / frameWidth) * 100;
      const top = (y1 / frameHeight) * 100;
      const width = ((x2 - x1) / frameWidth) * 100;
      const height = ((y2 - y1) / frameHeight) * 100;

      return {
        id: `plt-${idx}`,
        left: `${Math.max(0, Math.min(100, left))}%`,
        top: `${Math.max(0, Math.min(100, top))}%`,
        width: `${Math.max(0, Math.min(100 - left, width))}%`,
        height: `${Math.max(0, Math.min(100 - top, height))}%`,
        plateNumber: p.plate_number,
        confidence: Math.round(p.confidence * 100),
        isViolation: p.compliance?.status === 'VIOLATION',
        isLawful: p.compliance?.status === 'LAWFUL',
        isGovt: Boolean(p.government_match),
      };
    });
  }, [liveData?.plates, frameWidth, frameHeight, showPlateBoxes]);

  const mobileScannerUrl = `${window.location.protocol}//${window.location.hostname}:8000/`;

  return (
    <div className="flex flex-col h-full w-full max-w-full min-w-0 overflow-hidden bg-zinc-950 text-zinc-300 font-sans p-2.5 sm:p-3.5 gap-2.5 sm:gap-3 select-none">
      
      {/* --- HEADER --- */}
      <header className="flex items-center justify-between bg-zinc-900/40 border border-zinc-800/80 rounded-xl px-4 py-2 shrink-0 shadow-sm backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-blue-600/10 flex items-center justify-center border border-blue-500/20 shrink-0">
            <ShieldCheck className="text-blue-500" size={16} />
          </div>
          <div>
            <h1 className="text-sm sm:text-base font-semibold tracking-wide text-zinc-100">Live ANPR Command</h1>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="relative flex h-2 w-2">
                {isFeedActive && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>}
                <span className={`relative inline-flex rounded-full h-2 w-2 ${
                  isFeedActive ? 'bg-emerald-500' : connectionStatus === 'connected' ? 'bg-amber-400' : 'bg-rose-500'
                }`}></span>
              </span>
              <span className="text-[10px] text-zinc-400 uppercase tracking-widest font-medium">
                {isFeedActive ? 'Streaming' : connectionStatus === 'connected' ? 'Standby' : 'Offline'}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 bg-zinc-950/50 px-2.5 py-1 rounded-lg border border-zinc-800/80 text-xs sm:text-sm">
            <MapPin size={13} className="text-zinc-400 shrink-0" />
            <select
              value={selectedCameraArea}
              onChange={(e) => setSelectedCameraArea(e.target.value)}
              className="bg-transparent text-zinc-200 focus:outline-none cursor-pointer border-none py-0 pl-0 pr-2 text-xs"
            >
              {availableAreas.map((area) => (
                <option key={area} value={area} className="bg-zinc-900 text-white">{area}</option>
              ))}
            </select>
          </div>
          <button
            onClick={() => setSoundEnabled(!soundEnabled)}
            className={`h-8 w-8 flex items-center justify-center rounded-lg border transition-all shrink-0 ${
              soundEnabled ? 'bg-blue-500/10 border-blue-500/30 text-blue-400' : 'bg-zinc-900 border-zinc-800 text-zinc-500'
            }`}
          >
            {soundEnabled ? <Volume2 size={15} /> : <VolumeX size={15} />}
          </button>
        </div>
      </header>

      {/* --- MAIN BODY --- */}
      <main className="flex-1 flex flex-col lg:flex-row gap-2.5 sm:gap-3 min-h-0 min-w-0 overflow-hidden">
        
        {/* LEFT SIDEBAR: Controls & Stats */}
        <aside className="w-full lg:w-52 xl:w-60 flex flex-col gap-2.5 shrink-0 min-w-0 overflow-y-auto custom-scrollbar">
          {/* Stats Box */}
          <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-xl p-3 space-y-3">
            <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1">Session Metrics</h3>
            <div className="grid grid-cols-2 lg:grid-cols-1 gap-1.5">
              <div className="bg-zinc-950/50 p-2.5 rounded-lg border border-zinc-800/60 flex items-center justify-between">
                <span className="text-xs text-zinc-400">Vehicles</span>
                <span className="text-base font-semibold text-zinc-200">{totalDetectionsCount.vehicles}</span>
              </div>
              <div className="bg-zinc-950/50 p-2.5 rounded-lg border border-zinc-800/60 flex items-center justify-between">
                <span className="text-xs text-zinc-400">Plates</span>
                <span className="text-base font-semibold text-blue-400">{totalDetectionsCount.plates}</span>
              </div>
              <div className="bg-zinc-950/50 p-2.5 rounded-lg border border-rose-900/30 flex items-center justify-between">
                <span className="text-xs text-zinc-400">Violations</span>
                <span className="text-base font-semibold text-rose-400">{totalDetectionsCount.violations}</span>
              </div>
            </div>
          </div>

          {/* Controls Box */}
          <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-2xl p-4 space-y-5 flex-1">
            
            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">Feed Source</h3>
              <div className="flex bg-zinc-950/50 rounded-lg border border-zinc-800/80 p-1">
                <button
                  onClick={() => {
                    stopLocalWebcam();
                    setStreamSource('mobile');
                    setLiveData(null);
                    setIsMobileFeedActive(false);
                  }}
                  className={`flex-1 flex items-center justify-center gap-2 py-1.5 rounded-md text-sm font-medium transition-all ${
                    streamSource === 'mobile' ? 'bg-zinc-800 text-white shadow' : 'text-zinc-500 hover:text-zinc-300'
                  }`}
                >
                  <Smartphone size={14} /> Mobile
                </button>
                <button
                  onClick={() => {
                    setStreamSource('local');
                    setLiveData(null);
                    setIsMobileFeedActive(false);
                  }}
                  className={`flex-1 flex items-center justify-center gap-2 py-1.5 rounded-md text-sm font-medium transition-all ${
                    streamSource === 'local' ? 'bg-zinc-800 text-white shadow' : 'text-zinc-500 hover:text-zinc-300'
                  }`}
                >
                  <Laptop size={14} /> Laptop
                </button>
              </div>
            </div>

            {streamSource === 'local' ? (
              localCameraRunning ? (
                <button onClick={stopLocalWebcam} className="w-full py-2.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-500 border border-rose-500/20 rounded-xl text-sm font-medium flex items-center justify-center gap-2 transition-all">
                  <Square size={14} /> Stop Local Cam
                </button>
              ) : (
                <button onClick={startLocalWebcam} className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-medium flex items-center justify-center gap-2 transition-all shadow-lg shadow-blue-900/20">
                  <Play size={14} /> Start Local Cam
                </button>
              )
            ) : (
              <button onClick={() => setShowPhoneQrModal(true)} className="w-full py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 rounded-xl text-sm font-medium flex items-center justify-center gap-2 transition-all">
                <QrCode size={14} /> Pair Mobile Device
              </button>
            )}

            <div className="pt-4 border-t border-zinc-800/80 space-y-3">
              <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">Display Overlays</h3>
              <label className="flex items-center justify-between cursor-pointer group">
                <span className="text-sm text-zinc-400 group-hover:text-zinc-300">Vehicle Tracking</span>
                <input type="checkbox" checked={showVehicleBoxes} onChange={(e) => setShowVehicleBoxes(e.target.checked)} className="rounded border-zinc-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-zinc-900 bg-zinc-800" />
              </label>
              <label className="flex items-center justify-between cursor-pointer group">
                <span className="text-sm text-zinc-400 group-hover:text-zinc-300">Plate Outlines</span>
                <input type="checkbox" checked={showPlateBoxes} onChange={(e) => setShowPlateBoxes(e.target.checked)} className="rounded border-zinc-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-zinc-900 bg-zinc-800" />
              </label>
              <label className="flex items-center justify-between cursor-pointer group">
                <span className="text-sm text-zinc-400 group-hover:text-zinc-300">Class Labels</span>
                <input type="checkbox" checked={showLabels} onChange={(e) => setShowLabels(e.target.checked)} className="rounded border-zinc-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-zinc-900 bg-zinc-800" />
              </label>
            </div>
          </div>
        </aside>

        {/* CENTER VIEWPORT: The Camera */}
        <section className="flex-1 min-w-0 flex flex-col items-center justify-center bg-zinc-900/20 border border-zinc-800/80 rounded-xl relative min-h-0 overflow-hidden shadow-inner p-1 sm:p-2">
          {/* Centered, restricted size video container */}
          <div 
            ref={viewportRef}
            className="relative aspect-video w-full max-w-3xl xl:max-w-4xl max-h-full bg-black rounded-xl border border-zinc-800 overflow-hidden shadow-2xl flex items-center justify-center group"
          >
            {/* Always keep local video ref mounted in DOM */}
            <video
              ref={localVideoRef}
              autoPlay
              playsInline
              muted
              className={isFeedActive && streamSource === 'local' ? "w-full h-full object-contain" : "hidden"}
            />

            {isFeedActive && (streamSource === 'local' ? localCameraRunning : Boolean(liveData?.image_data)) ? (
              <>
                {streamSource === 'mobile' && liveData?.image_data && (
                  <img
                    src={liveData.image_data}
                    alt="Live ANPR Stream"
                    className="w-full h-full object-contain"
                  />
                )}

                {/* Bounding Boxes Layer */}
                <div className="absolute inset-0 pointer-events-none">
                  {vehicleBoxes.map((box) => (
                    <div
                      key={box.id}
                      style={{ position: 'absolute', left: box.left, top: box.top, width: box.width, height: box.height }}
                      className="border border-blue-400/70 rounded bg-blue-500/5 transition-all duration-100"
                    >
                      {showLabels && (
                        <div className="absolute -top-5 left-0 bg-blue-600 text-white text-[10px] px-1.5 py-0.5 rounded shadow flex items-center gap-1 font-mono whitespace-nowrap">
                          <span>{box.icon}</span> <span>{box.label}</span>
                        </div>
                      )}
                    </div>
                  ))}

                  {plateBoxes.map((box) => (
                    <div
                      key={box.id}
                      style={{ position: 'absolute', left: box.left, top: box.top, width: box.width, height: box.height }}
                      className={`border-[1.5px] rounded transition-all duration-100 ${
                        box.isViolation ? 'border-rose-500 bg-rose-500/10' : box.isGovt || box.isLawful ? 'border-blue-400 bg-blue-500/10' : 'border-amber-400 bg-amber-500/10'
                      }`}
                    >
                      {showLabels && (
                        <div className={`absolute -bottom-6 left-1/2 -translate-x-1/2 text-[10px] font-mono font-bold px-1.5 py-0.5 rounded shadow whitespace-nowrap text-white ${
                          box.isViolation ? 'bg-rose-600' : box.isGovt || box.isLawful ? 'bg-blue-600' : 'bg-amber-600'
                        }`}>
                          {box.plateNumber}
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                {/* Viewport UI Overlays */}
                <div className="absolute top-3 left-3 bg-black/60 backdrop-blur text-[10px] font-mono px-2 py-1 rounded text-zinc-300 border border-white/10 flex gap-2">
                   <span>{liveData?.camera_area || selectedCameraArea}</span>
                   <span className="text-zinc-500">|</span>
                   <span>{liveData?.timestamp ? new Date(liveData.timestamp).toLocaleTimeString('en-PK', { hour12: false }) : 'LIVE'}</span>
                   <span className="text-zinc-500">|</span>
                   <span className="text-blue-400">{latencyMs}ms</span>
                </div>
              </>
            ) : (
              /* Surveillance Camera Logo Display */
              <SurveillanceCameraLogo
                streamSource={streamSource}
                connectionStatus={connectionStatus}
                onPairMobile={() => setShowPhoneQrModal(true)}
                onStartLocal={startLocalWebcam}
              />
            )}

            <button onClick={toggleFullscreen} className="absolute top-3 right-3 bg-black/60 hover:bg-black/80 backdrop-blur p-1.5 rounded text-zinc-300 border border-white/10 transition-colors z-20">
              {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            </button>
          </div>
        </section>

        {/* RIGHT SIDEBAR: Live Logs */}
        <aside className="w-full lg:w-64 xl:w-72 flex flex-col bg-zinc-900/40 border border-zinc-800/80 rounded-xl p-3 shrink-0 min-w-0 overflow-hidden min-h-0">
          <div className="flex items-center justify-between mb-3 shrink-0">
            <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider flex items-center gap-2">
              <Activity size={14} className="text-blue-500" /> Live Feed Logs
            </h3>
            <span className="bg-zinc-800 text-zinc-300 text-[10px] px-1.5 py-0.5 rounded font-mono">{eventLogs.length}</span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar min-h-0">
            {eventLogs.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-zinc-600 text-xs gap-2">
                <CheckCircle2 size={24} className="opacity-20" />
                No detections recorded yet
              </div>
            ) : (
              eventLogs.map((log) => (
                <div key={log.id} className={`p-3 rounded-xl border text-xs flex flex-col gap-1.5 transition-colors ${
                  log.is_violation ? 'bg-rose-950/20 border-rose-900/50' : 'bg-zinc-950/50 border-zinc-800/60 hover:border-zinc-700'
                }`}>
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-sm text-zinc-100">{log.plate_number}</span>
                    <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider ${
                      log.is_violation ? 'bg-rose-500/10 text-rose-400' : 'bg-blue-500/10 text-blue-400'
                    }`}>
                      {log.is_violation ? 'Violation' : 'Lawful'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-zinc-500 font-mono">
                    <span>{log.timestamp}</span>
                    {log.violation_reason && <span className="text-rose-400/80 truncate ml-2 max-w-[120px]">{log.violation_reason.replace('_', ' ')}</span>}
                  </div>
                </div>
              ))
            )}
          </div>
        </aside>
      </main>

      {/* --- MODALS --- */}
      {showPhoneQrModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-sm w-full p-6 shadow-2xl">
            <h3 className="text-base font-bold text-white mb-1">Connect Mobile Device</h3>
            <p className="text-xs text-zinc-400 mb-5">Pair your smartphone as a live field camera</p>
            
            <div className="space-y-4 text-sm text-zinc-300">
              <div className="bg-zinc-950/50 p-4 rounded-xl border border-zinc-800">
                <p className="font-medium text-white mb-1 text-sm">1. Same Network Required</p>
                <p className="text-xs text-zinc-500">Ensure your phone is on the exact same Wi-Fi network as this command center.</p>
              </div>
              <div className="bg-zinc-950/50 p-4 rounded-xl border border-zinc-800">
                <p className="font-medium text-white mb-2 text-sm">2. Enter URL on Mobile</p>
                <div className="bg-black p-2.5 rounded border border-zinc-800 font-mono text-blue-400 text-xs text-center select-all">
                  {mobileScannerUrl}
                </div>
              </div>
            </div>

            <button onClick={() => setShowPhoneQrModal(false)} className="w-full mt-6 py-2 bg-zinc-100 hover:bg-white text-zinc-900 rounded-xl text-sm font-semibold transition-colors">
              Close Instructions
            </button>
          </div>
        </div>
      )}
    </div>
  );
};