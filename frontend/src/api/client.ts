export interface AuthorizedVehicle {
  plate_number: string;
  vehicle_id: string;
  department: string;
  authorized_areas: string;
  duty_schedule: string;
  notes: string;
  officer_name?: string;
  officer_phone?: string;
  officer_email?: string;
}

export interface SpottedVehicle {
  timestamp: string;
  camera_area: string;
  plate_number: string;
  confidence: string | number;
  latitude: string | number | null;
  longitude: string | number | null;
  location_accuracy_m: string | number | null;
  vehicle_type: string;
  image: string;
  bbox: string;
  vehicle_id: string;
  department: string;
  authorized_areas: string;
  duty_schedule: string;
  status: 'LAWFUL' | 'VIOLATION' | 'UNASSESSED' | string;
  violation_criteria: string;
  notes: string;
}

export interface ViolationRecord extends SpottedVehicle {}

export interface VehicleViolationSummary {
  plate_number: string;
  normalized_plate: string;
  vehicle_id: string;
  department: string;
  officer_name: string;
  officer_phone: string;
  officer_email: string;
  duty_schedule: string;
  authorized_areas: string;
  total_violations: number;
  tier: 'WARNING_1' | 'WARNING_2' | 'WARNING_3' | 'CHALLAN_ISSUED';
  stage_label: string;
  stage_type: 'warning' | 'challan';
  fine_amount: number;
  challan_id: string | null;
  first_violation_date: string;
  last_violation_date: string;
  latest_camera_area: string;
  latest_criteria: string;
  latest_image: string;
  violations_history: ViolationRecord[];
}

export interface SendNotificationPayload {
  plate_number: string;
  channel: 'email' | 'whatsapp' | 'whatsapp_direct';
  recipient_email?: string;
  recipient_phone?: string;
  officer_name?: string;
  violation_count?: number;
  message_type: 'warning' | 'challan';
  custom_message?: string;
  fine_amount?: number;
  challan_id?: string;
}

export interface SendNotificationResponse {
  success: boolean;
  channel: string;
  plate_number: string;
  officer_name: string;
  recipient_phone: string;
  recipient_email: string;
  whatsapp_url: string;
  whatsapp_message: string;
  meta_dispatched?: boolean;
  email_dispatched?: boolean;
  message: string;
  meta_result?: {
    success: boolean;
    message_id?: string;
    media_id?: string;
    recipient?: string;
    message?: string;
    error?: string;
  };
  email_result?: {
    success: boolean;
    mode: string;
    message: string;
    recipient: string;
  };
}

export interface SystemStats {
  authorized_vehicles_count: number;
  departments_count: number;
  total_government_sightings: number;
  violations_count: number;
  lawful_count: number;
  unique_spotted_plates: number;
  general_detections_count: number;
  vehicles_with_warnings?: number;
  vehicles_with_challans?: number;
  total_fines_levied?: number;
}

export interface User {
  email: string;
  name: string;
  role: string;
}

const API_BASE = '';

export async function loginAdmin(email: string, password: string): Promise<{ success: boolean; token: string; user: User }> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Login failed. Please check credentials.');
  }
  return res.json();
}

export async function fetchAuthorizedVehicles(query?: string, area?: string): Promise<AuthorizedVehicle[]> {
  const params = new URLSearchParams();
  if (query) params.append('query', query);
  if (area && area !== 'ALL') params.append('area', area);
  
  const res = await fetch(`${API_BASE}/api/authorized-vehicles?${params.toString()}`);
  if (!res.ok) {
    throw new Error('Failed to fetch authorized vehicles');
  }
  return res.json();
}

export async function createAuthorizedVehicle(vehicle: AuthorizedVehicle): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/api/authorized-vehicles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(vehicle),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to add vehicle');
  }
  return res.json();
}

export async function updateAuthorizedVehicle(plateNumber: string, vehicle: Partial<AuthorizedVehicle>): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/api/authorized-vehicles/${encodeURIComponent(plateNumber)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(vehicle),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to update vehicle');
  }
  return res.json();
}

export async function deleteAuthorizedVehicle(plateNumber: string): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/api/authorized-vehicles/${encodeURIComponent(plateNumber)}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to delete vehicle');
  }
  return res.json();
}

export async function fetchSpottedVehicles(limit = 1000): Promise<SpottedVehicle[]> {
  const res = await fetch(`${API_BASE}/api/government-vehicles-spotted?limit=${limit}`);
  if (!res.ok) {
    throw new Error('Failed to fetch spotted government vehicles');
  }
  return res.json();
}

export async function fetchViolationsSummary(query?: string, stage?: string): Promise<VehicleViolationSummary[]> {
  const params = new URLSearchParams();
  if (query) params.append('query', query);
  if (stage && stage !== 'ALL') params.append('stage', stage);

  const res = await fetch(`${API_BASE}/api/violations-summary?${params.toString()}`);
  if (!res.ok) {
    throw new Error('Failed to fetch violations summary');
  }
  return res.json();
}

export async function fetchChallanDetails(plateNumber: string): Promise<VehicleViolationSummary> {
  const res = await fetch(`${API_BASE}/api/challan/${encodeURIComponent(plateNumber)}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch challan details');
  }
  return res.json();
}

export async function sendViolationNotification(payload: SendNotificationPayload): Promise<SendNotificationResponse> {
  const res = await fetch(`${API_BASE}/api/send-notification`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to dispatch notification');
  }
  return res.json();
}

export async function fetchSystemStats(): Promise<SystemStats> {
  const res = await fetch(`${API_BASE}/api/stats`);
  if (!res.ok) {
    throw new Error('Failed to fetch system stats');
  }
  return res.json();
}

export interface SmtpConfig {
  configured: boolean;
  host: string;
  port: number;
  user: string;
  password?: string;
  sender_email?: string;
  sender_name?: string;
  use_tls: boolean;
  use_ssl: boolean;
  has_password?: boolean;
  password_preview?: string;
}

export interface TestEmailPayload {
  recipient_email: string;
  config?: Partial<SmtpConfig>;
}

export async function fetchSmtpConfig(): Promise<SmtpConfig> {
  const res = await fetch(`${API_BASE}/api/settings/smtp`);
  if (!res.ok) {
    throw new Error('Failed to fetch SMTP configuration');
  }
  return res.json();
}

export async function saveSmtpConfig(config: Partial<SmtpConfig>): Promise<{ success: boolean; message: string; config: SmtpConfig }> {
  const res = await fetch(`${API_BASE}/api/settings/smtp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to save SMTP configuration');
  }
  return res.json();
}

export async function testSmtpConnection(payload: TestEmailPayload): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/api/settings/smtp/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Test email failed to send');
  }
  return res.json();
}

export interface WhatsAppGatewayStatus {
  status: 'INITIALIZING' | 'SCAN_QR' | 'CONNECTING' | 'CONNECTED' | 'DISCONNECTED' | 'OFFLINE';
  connected: boolean;
  reachable: boolean;
  user?: { id: string; phone: string; name: string } | null;
  qr?: string | null;
  error?: string | null;
  timestamp?: string;
}

export async function fetchWhatsAppGatewayStatus(): Promise<WhatsAppGatewayStatus> {
  const res = await fetch(`${API_BASE}/api/whatsapp-gateway/status`);
  if (!res.ok) {
    return {
      status: 'OFFLINE',
      connected: false,
      reachable: false,
      error: 'WhatsApp Bridge service offline',
    };
  }
  return res.json();
}

export async function logoutWhatsAppGateway(): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/api/whatsapp-gateway/logout`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error('Failed to disconnect WhatsApp Gateway');
  }
  return res.json();
}

export async function requestPairingCode(phone: string): Promise<{ success: boolean; code: string; phone: string; message: string }> {
  const res = await fetch(`${API_BASE}/api/whatsapp-gateway/pair-code`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to request pairing code');
  }
  return res.json();
}

export interface WhatsAppCloudConfig {
  configured: boolean;
  phone_number_id: string;
  access_token?: string;
  has_token?: boolean;
  token_preview?: string;
  api_version: string;
}

export interface TestWhatsAppPayload {
  recipient_phone: string;
  config?: Partial<WhatsAppCloudConfig>;
}

export async function fetchWhatsAppConfig(): Promise<WhatsAppCloudConfig> {
  const res = await fetch(`${API_BASE}/api/settings/whatsapp`);
  if (!res.ok) {
    throw new Error('Failed to fetch WhatsApp configuration');
  }
  return res.json();
}

export async function saveWhatsAppConfig(config: Partial<WhatsAppCloudConfig>): Promise<{ success: boolean; message: string; config: WhatsAppCloudConfig }> {
  const res = await fetch(`${API_BASE}/api/settings/whatsapp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to save WhatsApp configuration');
  }
  return res.json();
}

export async function testWhatsAppConnection(payload: TestWhatsAppPayload): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/api/settings/whatsapp/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Test WhatsApp message failed to send');
  }
  return res.json();
}

export async function fetchCameraAreas(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/camera-areas`);
  if (!res.ok) {
    return [
      'Federal Territory',
      'Pakistan Provinces',
      'Mzd. Division',
      'Mirpur Division',
      'Poonch Division',
    ];
  }
  return res.json();
}

export interface DetectedVehicle {
  label: string;
  confidence: number;
  bbox: [number, number, number, number]; // [x1, y1, x2, y2]
}

export interface DetectedPlate {
  plate_number: string;
  confidence: number;
  bbox: [number, number, number, number]; // [x1, y1, x2, y2]
  saved?: boolean;
  reason?: string | null;
  government_match?: {
    plate_number?: string;
    vehicle_id?: string;
    department?: string;
    authorized_areas?: string;
    duty_schedule?: string;
    officer_name?: string;
    officer_phone?: string;
  } | null;
  compliance?: {
    status: 'LAWFUL' | 'VIOLATION' | string;
    violation_criteria?: string;
  } | null;
}

export interface LiveFrameData {
  type?: string;
  active?: boolean;
  timestamp: string;
  camera_area: string;
  latitude?: number | null;
  longitude?: number | null;
  location_accuracy_m?: number | null;
  frame_width?: number;
  frame_height?: number;
  image_data?: string;
  vehicles: DetectedVehicle[];
  plates: DetectedPlate[];
}

export function getLiveCameraWebSocketUrl(): string {
  const loc = window.location;
  // If Vite dev server on port 5173, connect to backend at port 8000
  if (loc.port === '5173') {
    return `ws://${loc.hostname}:8000/ws/live-camera`;
  }
  const protocol = loc.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${loc.host}/ws/live-camera`;
}

export async function fetchLatestLiveFrame(): Promise<LiveFrameData | null> {
  const res = await fetch(`${API_BASE}/api/live-camera/latest`);
  if (!res.ok) return null;
  const data = await res.json();
  return data.active !== false ? data : null;
}

export async function analyzeCameraFrame(formData: FormData): Promise<LiveFrameData> {
  const res = await fetch(`${API_BASE}/api/camera/analyze`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Frame analysis failed');
  }
  return res.json();
}




