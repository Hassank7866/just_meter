export interface AuthorizedVehicle {
  risk_context?: '' | 'STANDARD' | 'SENSITIVE' | 'CRITICAL';
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

export interface ComplianceRuleResult {
  rule_id: string;
  outcome: 'PASS' | 'FAIL' | 'REVIEW' | 'NOT_APPLICABLE' | string;
  message: string;
  criteria?: string;
}

export interface SpottedVehicle {
  _record_key?: string;
  duty_verification?: DutyVerification | null;
  risk_policy_version?: number | string;
  notification_priority?: string;
  escalation_role?: string;
  recommended_action?: string;
  risk_missing_context?: string[];
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
  risk_score?: number | string;
  risk_level?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | 'PENDING_REVIEW' | 'NOT_APPLICABLE' | string;
  risk_factors?: string[] | string;
  decision_reason?: string;
  decision_rules?: ComplianceRuleResult[] | string;
  notes: string;
}

export interface ViolationRecord extends SpottedVehicle {}

export interface VehicleViolationSummary {
  database_vehicle_id?: number;
  issued_challan_case_id?: number | null;
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
  tier: 'WARNING_1' | 'WARNING_2' | 'WARNING_3' | 'CHALLAN_ELIGIBLE' | 'CHALLAN_ISSUED';
  stage_label: string;
  stage_type: 'warning' | 'challan';
  fine_amount: number;
  challan_id: string | null;
  first_violation_date: string;
  last_violation_date: string;
  latest_camera_area: string;
  latest_criteria: string;
  risk_score?: number;
  risk_level?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | 'NOT_ASSESSED' | string;
  risk_factors?: string[];
  decision_reason?: string;
  decision_rules?: ComplianceRuleResult[];
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

export interface TwinReference { id?: number; plate?: string; sighting_key?: string; evidence_key?: string }
export interface ChallanSnapshot {
  image_policy?: string;
  plate_number: string; department: string; total_violations: number;
  violations_history: Record<string, unknown>[];
  evidence: { id: number; evidence_id: string; full_image: string; full_image_sha256: string; review_status: string; plate_crop?: string }[];
}
export interface ChallanCase {
  id: number; reference: string; vehicle_id: number; sighting_id: number; status: string; version: number;
  fine_amount: number; created_by: string; prepared_by: string; approved_by: string | null; issued_by: string | null;
  issued_at: string | null; due_at: string | null; document_sha256: string | null;
  snapshot: ChallanSnapshot; review_snapshot?: ChallanSnapshot; review_fingerprint?: string; changed_since_approval?: boolean;
  history?: { id: number; at: string; actor: string; action: string; details: Record<string, unknown> }[];
}
export async function challanRequest<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE}/api/challans${path}`, { signal, method: body === undefined ? 'GET' : 'POST',
    ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check the required case fields.');
  return data;
}
export interface TwinVehicle { id: number; plate_number: string; vehicle_id: string; active: boolean }
export interface TwinEvent {
  id: number; kind: 'sighting' | 'risk' | 'evidence' | 'duty_review' | 'assignment' | 'duty_slip' | 'challan';
  at: string | null; data: Record<string, unknown>;
}
export interface DigitalTwin {
  generated_at: string; as_of: string;
  vehicle: TwinVehicle & { department: string | null; authorized_areas: string[]; duty_schedule: string;
    make?: string; model?: string; color?: string; vehicle_type?: string; officer_name?: string };
  source_context: { source: string | null; exported_at: string | null; age_hours?: number | null;
    assignments: Record<string, unknown>[]; duty_slips: Record<string, unknown>[] };
  duty_verification: DutyVerification;
  compliance: { total_sightings: number; total_violations: number; by_status: Record<string, number> };
  latest_sighting: (Record<string, unknown> & { id: number; observed_at: string }) | null;
  risk: { score: number; level: string; assessed_at: string; sighting_id: number } | null;
  open_tasks: number; warnings: string[];
  timeline: { total: number; limit: number; offset: number; items: TwinEvent[] };
}

async function twinRequest<T>(path: string, params: URLSearchParams, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE}/api/vehicles/${path}?${params}`, { signal });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check the profile filters and try again.');
  return data;
}
export function fetchTwinVehicles(query: string, offset = 0, signal?: AbortSignal) {
  return twinRequest<{ total: number; items: TwinVehicle[] }>('digital-twins', new URLSearchParams({ query, offset: String(offset), limit: '20' }), signal);
}
export async function resolveTwinReference(reference: TwinReference, signal?: AbortSignal): Promise<number> {
  if (reference.id !== undefined) return reference.id;
  const params = new URLSearchParams();
  for (const key of ['plate', 'sighting_key', 'evidence_key'] as const) if (reference[key]) params.set(key, reference[key]!);
  return (await twinRequest<{ id: number }>('digital-twins/resolve', params, signal)).id;
}
export function fetchDigitalTwin(id: number, params: URLSearchParams, signal?: AbortSignal) {
  return twinRequest<DigitalTwin>(`${id}/digital-twin`, params, signal);
}

export interface MovementEvent {
  id: number;
  kind: 'sighting' | 'checkpoint_crossing' | 'confirmed_link';
  at: string;
  camera_id: string;
  camera_area?: string;
  association: 'registry_linked' | 'reviewed_plate' | 'administrator_confirmed';
  sighting_key?: string;
  status?: string;
  plate_number?: string;
  checkpoint_name?: string;
  checkpoint_revision?: number;
  direction?: string;
  track_id?: string;
  from_camera_id?: string;
  to_camera_id?: string;
  from_track_id?: string;
  to_track_id?: string;
  confirmed_by?: string;
  confirmed_at?: string;
}

export interface MovementTrail {
  vehicle_id: number;
  total: number;
  limit: number;
  offset: number;
  items: MovementEvent[];
  alert_total: number;
  alerts: MovementAlert[];
}

export interface MovementAlert {
  alert_key: string;
  route_id: number;
  route_name: string;
  route_revision: number;
  kind: 'ROUTE_DEVIATION' | 'UNAUTHORIZED_VISIT' | 'BOUNDARY_CROSSING' | 'ABNORMAL_SEQUENCE';
  status: 'REVIEW_REQUIRED' | 'CONFIRMED' | 'DISMISSED';
  message: string;
  observed_at: string;
  camera_id: string;
  source_kind: string;
  source_id: number;
  track_id: string;
  zone_id: string;
  reviewed_by?: string;
  reviewed_at?: string;
  notes?: string;
}

export function fetchMovementTrail(id: number, params: URLSearchParams, signal?: AbortSignal) {
  return twinRequest<MovementTrail>(`${id}/movement-trail`, params, signal);
}

export async function reviewMovementAlert(vehicleId: number, alertKey: string,
                                          status: 'CONFIRMED' | 'DISMISSED', notes: string): Promise<MovementAlert> {
  const response = await fetch(`${API_BASE}/api/vehicles/${vehicleId}/movement-alerts/${encodeURIComponent(alertKey)}/review`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status, notes }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not save alert review');
  return data;
}

export interface VehicleVerification {
  id: number; sighting_id: number; vehicle_id: number; observed_at: string;
  expected: Record<string, string>; observed: Record<string, string>;
  comparisons: Record<string, 'MATCH' | 'MISMATCH' | 'UNKNOWN'>;
  status: string; risk_status: string; reviewed_by: string | null;
  reviewed_at: string | null; review_notes: string;
}
export async function fetchVehicleVerifications(vehicleId: number): Promise<VehicleVerification[]> {
  const response = await fetch(`${API_BASE}/api/vehicles/${vehicleId}/verifications`);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not load verifications');
  return data;
}
export async function fetchVehicleVerificationRiskQueue(): Promise<VehicleVerification[]> {
  const response = await fetch(`${API_BASE}/api/vehicle-verification/risk-queue`);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not load verification risk queue');
  return data;
}
export async function reviewVehicleVerification(vehicleId: number, id: number,
  payload: { decision: 'CONFIRMED_MISMATCH' | 'DISMISSED'; make: string; model: string; color: string; notes: string }): Promise<VehicleVerification> {
  const response = await fetch(`${API_BASE}/api/vehicles/${vehicleId}/verifications/${id}/review`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not save verification');
  return data;
}

export interface DashboardAlert {
  id: number; plate_number: string; department: string; timestamp: string;
  risk_level: string; risk_score: number; priority: string; assigned_role: string;
  recommended_action: string; violation_id: string | null;
}

export interface ExecutiveDashboard {
  start_date: string; end_date: string; timezone: string; department: string;
  department_options: string[]; generated_at: string;
  summary: {
    registered_vehicles: number; detections: number; sightings: number; observed_vehicles: number;
    violations: number; lawful: number; review_required: number; open_tasks: number;
    acknowledged_tasks: number; warning_stage_vehicles: number; challan_eligible_vehicles: number;
  };
  departments: { department: string; registered_vehicles: number; observed_vehicles: number;
    sightings: number; violations: number; lawful: number; review_required: number; open_tasks: number }[];
  risk_distribution: Record<string, number>;
  legacy_risk_count: number;
  daily: { date: string; detections: number; sightings: number; violations: number; high_risk: number }[];
  alerts: DashboardAlert[];
}

export async function fetchExecutiveDashboard(start: string, end: string, department: string, signal?: AbortSignal): Promise<ExecutiveDashboard> {
  const params = new URLSearchParams();
  if (start) params.set('start_date', start);
  if (end) params.set('end_date', end);
  if (department) params.set('department', department);
  const response = await fetch(`/api/dashboard?${params}`, { signal });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(typeof payload.detail === 'string' ? payload.detail : 'Unable to load executive dashboard');
  }
  return response.json();
}

export interface User {
  id?: number;
  active?: boolean;
  department_id?: number | null;
  department?: string | null;
  email: string;
  name: string;
  role: string;
}

const API_BASE = '';

export async function governanceRequest<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`/api/${path}`, { method, headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check the required fields and try again.');
  return data as T;
}

export async function downloadReport(params: URLSearchParams, format: 'csv' | 'pdf'): Promise<void> {
  const response = await fetch(`/api/reports/compliance?${params}&format=${format}`);
  if (!response.ok) {
    const data = await response.json();
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not export this report.');
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = response.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1] || `compliance.${format}`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export interface DutyVerification {
  status: 'PASS' | 'FAIL' | 'REVIEW'; review_required: boolean; reviewable: string[];
  source: string | null; source_revision: number | null; observed_at: string;
  assignment: Record<string, unknown> | null; duty_slip: Record<string, unknown> | null;
  rules: ComplianceRuleResult[]; review?: { actor: string; at: string; notes: string };
}
export interface DutyCoverage {
  source: string; revision: number; confirmed: boolean;
  coverage: { valid_from: string; valid_until: string; max_age_hours: number; confirmed_by: string } | null;
}
export interface DutyObservation {
  id: number; plate_number: string; timestamp: string; camera_area: string; status: string;
  image: string; duty_verification: DutyVerification;
}
export async function dutyRequest<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}/api/duty/${path}`, { method,
    headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Invalid duty request; check dates and required fields.');
  return data as T;
}

export type VimsKind = 'departments' | 'vehicles' | 'drivers' | 'assignments' | 'duty_slips';
export interface VimsSource { id: number; name: string; revision: number; exported_at: string | null }
export interface VimsRecord { local_id: number; source: string; external_id: string; [key: string]: unknown }
export interface VimsChange { kind: VimsKind; external_id: string; operation: string; before: Record<string, unknown> | null; after: Record<string, unknown> }
export interface VimsRun {
  id?: number; source: string; batch_id: string; status: string; base_revision: number;
  occurred_at?: string; exported_at?: string; actor?: string; error?: string | null;
  summary: Record<string, { created: number; linked: number; updated: number; unchanged: number }>;
  changes?: VimsChange[];
}
export async function vimsRequest<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}/api/vims/${path}`, body === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) {
    const detail = result.detail;
    throw new Error(Array.isArray(detail) ? detail.map((e: { loc: string[]; msg: string }) => `${e.loc.join('.')}: ${e.msg}`).join('\n') : detail || 'VIMS request failed');
  }
  return result as T;
}

// All API calls pass through this wrapper so credentials and auth errors are consistent.
const fetch: typeof window.fetch = async (input, init) => {
  const token = window.localStorage.getItem('anpr_auth_token');
  const headers = new Headers(init?.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await window.fetch(input, { ...init, headers });
  if (response.status === 401) {
    window.dispatchEvent(new CustomEvent('justmeter:unauthorized'));
  } else if (response.status === 403) {
    const payload = await response.clone().json().catch(() => ({}));
    window.dispatchEvent(new CustomEvent('justmeter:forbidden', {
      detail: payload.detail || 'Your role does not allow this action.',
    }));
  }
  return response;
};

export function authenticatedResourceUrl(path: string): string {
  const token = window.localStorage.getItem('anpr_auth_token');
  if (!token) return path;
  const separator = path.includes('?') ? '&' : '?';
  return `${path}${separator}token=${encodeURIComponent(token)}`;
}

export function snapshotUrl(path: string): string {
  try {
    const user = JSON.parse(window.localStorage.getItem('anpr_auth_user') || '{}');
    if (user.role !== 'Administrator' && !path.startsWith('plates/')) {
      return 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="260"><rect width="100%" height="100%" fill="#0f172a"/><text x="50%" y="50%" text-anchor="middle" fill="#94a3b8" font-size="14">Full frame: administrator access required</text></svg>');
    }
  } catch { /* The API remains the authority for image access. */ }
  return authenticatedResourceUrl(`/snapshots/${path}`);
}

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
  track_id?: string;
}

export interface GeofenceZone {
  zone_id: string;
  name: string;
  camera_area: string;
  authorized_plates: string[];
  polygon: Array<{ latitude: number; longitude: number }>;
  kind?: 'AUTHORIZED' | 'RESTRICTED';
  department_id?: number | null;
  require_assignment?: boolean;
  require_duty?: boolean;
}

export async function fetchGeofences(): Promise<GeofenceZone[]> {
  const res = await fetch(`${API_BASE}/api/geofences`);
  if (!res.ok) throw new Error('Failed to load geofences');
  return res.json();
}

export async function saveGeofence(zone: Omit<GeofenceZone, 'zone_id'>, zoneId?: string): Promise<GeofenceZone> {
  const res = await fetch(`${API_BASE}/api/geofences${zoneId ? `/${encodeURIComponent(zoneId)}` : ''}`, {
    method: zoneId ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(zone),
  });
  if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || 'Could not save geofence'); }
  return res.json();
}

export async function deleteGeofence(zoneId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/geofences/${encodeURIComponent(zoneId)}`, { method: 'DELETE' });
  if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || 'Could not delete geofence'); }
}

export interface ApprovedRoute {
  id: number;
  name: string;
  department_id: number;
  vehicle_id: number | null;
  valid_from: string;
  valid_until: string;
  weekdays: number[];
  camera_ids: string[];
  camera_areas: string[];
  corridor_polygon: Array<{ latitude: number; longitude: number }>;
  require_assignment: boolean;
  require_duty: boolean;
  enforce_dates: boolean;
  active: boolean;
  revision: number;
  approved_by: string;
  approved_at: string;
}

export async function fetchApprovedRoutes(): Promise<ApprovedRoute[]> {
  const response = await fetch(`${API_BASE}/api/approved-routes`);
  if (!response.ok) throw new Error('Could not load approved routes');
  return response.json();
}

export async function saveApprovedRoute(route: Omit<ApprovedRoute, 'id' | 'revision' | 'approved_by' | 'approved_at'>,
                                        routeId?: number): Promise<ApprovedRoute> {
  const response = await fetch(`${API_BASE}/api/approved-routes${routeId ? `/${routeId}` : ''}`, {
    method: routeId ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(route),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check route fields');
  return data;
}

export interface ComplianceDecision {
  status: 'LAWFUL' | 'VIOLATION' | 'UNREGISTERED' | 'REVIEW_REQUIRED' | string;
  violation_criteria?: string;
  decision_reason?: string;
  rules?: ComplianceRuleResult[];
  risk_score?: number;
  risk_level?: string;
  risk_factors?: string[];
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
  compliance?: ComplianceDecision | null;
  track_id?: string;
}

export interface LiveFrameData {
  event_id?: string;
  type?: string;
  active?: boolean;
  timestamp: string;
  camera_id?: string;
  camera_area: string;
  source_type?: 'LIVE_FRAME' | 'RECORDED_VIDEO' | string;
  frame_number?: number | null;
  vehicle_count?: number;
  new_track_count?: number;
  new_crossing_count?: number;
  crossings?: Array<{ track_id: string; direction: string; timestamp: string }>;
  model_name?: string;
  model_version?: string;
  latitude?: number | null;
  longitude?: number | null;
  location_accuracy_m?: number | null;
  frame_width?: number;
  frame_height?: number;
  image_data?: string;
  vehicles: DetectedVehicle[];
  plates: DetectedPlate[];
}

export function getLiveCameraWebSocketUrl(token: string): string {
  const loc = window.location;
  const query = `?token=${encodeURIComponent(token)}`;
  const protocol = loc.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${loc.host}/ws/live-camera${query}`;
}

export async function createMobileCameraSessionToken(): Promise<{ token: string; expires_in: number }> {
  const res = await fetch(`${API_BASE}/api/camera/session-token`, { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Could not create a mobile camera session');
  }
  return res.json();
}

export async function createLiveFeedSessionToken(): Promise<{ token: string; expires_in: number }> {
  const res = await fetch(`${API_BASE}/api/live-camera/session-token`, { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Could not open the authenticated live feed');
  }
  return res.json();
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

export interface VideoAnalysisResult {
  source_type: 'RECORDED_VIDEO';
  camera_id: string;
  camera_area: string;
  filename: string;
  frames_read: number;
  frames_analyzed: number;
  vehicles_detected: number;
  unique_vehicles: number;
  checkpoint_crossings: number;
  events: Array<{
    event_id: string;
    timestamp: string;
    frame_number: number;
    vehicle_count: number;
    new_track_count: number;
    new_crossing_count: number;
    vehicles: DetectedVehicle[];
  }>;
}

export interface CameraCheckpoint {
  camera_id: string;
  name: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  direction: 'BOTH' | 'A_TO_B' | 'B_TO_A';
  active: boolean;
  revision: number;
}

export interface CheckpointCrossing {
  track_id: string;
  camera_id: string;
  timestamp: string;
  direction: string;
  revision: number;
}

export interface TrackLinkCandidate {
  first_recognition_id: string;
  second_recognition_id: string;
  first_track_id: string;
  second_track_id: string;
  first_camera_id: string;
  second_camera_id: string;
  plate_number: string;
  first_seen: string;
  second_seen: string;
  elapsed_seconds: number;
  confirmed: boolean;
}

export async function fetchCameraCheckpoint(cameraId: string): Promise<CameraCheckpoint | null> {
  const res = await fetch(`${API_BASE}/api/camera-checkpoints/${encodeURIComponent(cameraId)}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error('Could not load checkpoint');
  return res.json();
}

export async function saveCameraCheckpoint(cameraId: string, config: Omit<CameraCheckpoint, 'camera_id' | 'revision'>): Promise<CameraCheckpoint> {
  const res = await fetch(`${API_BASE}/api/camera-checkpoints/${encodeURIComponent(cameraId)}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(config),
  });
  if (!res.ok) { const body = await res.json().catch(() => ({})); throw new Error(body.detail || 'Could not save checkpoint'); }
  return res.json();
}

export async function fetchCheckpointCrossings(cameraId: string): Promise<CheckpointCrossing[]> {
  const res = await fetch(`${API_BASE}/api/checkpoint-crossings?camera_id=${encodeURIComponent(cameraId)}&limit=20`);
  if (!res.ok) throw new Error('Could not load checkpoint counts');
  return res.json();
}

export async function fetchTrackLinkCandidates(): Promise<TrackLinkCandidate[]> {
  const res = await fetch(`${API_BASE}/api/track-links/candidates?limit=20`);
  if (!res.ok) throw new Error('Could not load cross-camera candidates');
  return res.json();
}

export async function confirmTrackLink(candidate: TrackLinkCandidate): Promise<void> {
  const res = await fetch(`${API_BASE}/api/track-links`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ first_recognition_id: candidate.first_recognition_id,
      second_recognition_id: candidate.second_recognition_id }),
  });
  if (!res.ok) { const body = await res.json().catch(() => ({})); throw new Error(body.detail || 'Could not confirm track link'); }
}

export async function analyzeRecordedVideo(formData: FormData): Promise<VideoAnalysisResult> {
  const res = await fetch(`${API_BASE}/api/camera/analyze-video`, { method: 'POST', body: formData });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Recorded video analysis failed');
  }
  return res.json();
}

export interface PlateRecognitionRecord {
  recognition_id: string;
  detection_event_id: string;
  timestamp: string;
  camera_id: string;
  camera_area: string;
  raw_text: string;
  normalized_text: string;
  suggested_text: string;
  final_text: string;
  confidence: string | number;
  valid_format: string;
  review_status: 'REVIEW_REQUIRED' | 'ACCEPTED' | 'REJECTED';
  review_reason: string;
  plate_crop: string;
  bbox: string;
  ocr_model: string;
  reviewer: string;
  reviewed_at: string;
  review_notes: string;
}

export async function fetchPlateRecognitions(status?: string): Promise<PlateRecognitionRecord[]> {
  const params = new URLSearchParams({ limit: '500' });
  if (status && status !== 'ALL') params.set('status', status);
  const res = await fetch(`${API_BASE}/api/anpr/recognitions?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to load ANPR recognition records');
  return res.json();
}

export async function reviewPlateRecognition(
  recognitionId: string,
  payload: { corrected_text: string; status: 'ACCEPTED' | 'REJECTED'; reviewer?: string; notes?: string },
): Promise<{
  success: boolean;
  recognition: PlateRecognitionRecord;
  enforcement: {
    compliance: ComplianceDecision;
    saved: boolean;
    reason: string | null;
    violation_id: string;
    challan_id: string;
    evidence_id: string;
  } | null;
}> {
  const res = await fetch(`${API_BASE}/api/anpr/recognitions/${encodeURIComponent(recognitionId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to review plate recognition');
  }
  return res.json();
}

export type EvidenceReviewStatus = 'CAPTURED' | 'UNDER_REVIEW' | 'VERIFIED';
export type EvidenceCaseStatus = 'UNASSIGNED' | 'ATTACHED_TO_VIOLATION' | 'ATTACHED_TO_CHALLAN';

export interface EvidenceRecord {
  duty_verification?: DutyVerification | null;
  evidence_id: string;
  detection_event_id: string;
  recognition_id: string;
  timestamp: string;
  camera_id: string;
  camera_area: string;
  plate_number: string;
  ocr_confidence: string | number;
  vehicle_type: string;
  department: string;
  full_image: string;
  plate_crop: string;
  full_image_sha256: string;
  plate_crop_sha256: string;
  full_image_size: string | number;
  plate_crop_size: string | number;
  frame_width: string | number;
  frame_height: string | number;
  latitude: string | number;
  longitude: string | number;
  review_status: EvidenceReviewStatus;
  case_status: EvidenceCaseStatus;
  integrity_status: 'VERIFIED' | 'FAILED' | string;
  related_violation_id: string;
  related_challan_id: string;
  reviewer: string;
  reviewed_at: string;
  review_notes: string;
}

type EvidenceRecordResponse = Omit<EvidenceRecord, 'review_status' | 'case_status'> & {
  review_status?: EvidenceReviewStatus;
  case_status?: EvidenceCaseStatus;
  status?: string;
};

function normalizeEvidenceRecord(record: EvidenceRecordResponse): EvidenceRecord {
  const legacyStatus = record.status?.toUpperCase();
  const reviewStatus = ['CAPTURED', 'UNDER_REVIEW', 'VERIFIED'].includes(record.review_status ?? '')
    ? record.review_status!
    : ['CAPTURED', 'UNDER_REVIEW', 'VERIFIED'].includes(legacyStatus ?? '')
      ? legacyStatus as EvidenceReviewStatus
      : 'CAPTURED';
  const caseStatus = ['UNASSIGNED', 'ATTACHED_TO_VIOLATION', 'ATTACHED_TO_CHALLAN'].includes(record.case_status ?? '')
    ? record.case_status!
    : ['UNASSIGNED', 'ATTACHED_TO_VIOLATION', 'ATTACHED_TO_CHALLAN'].includes(legacyStatus ?? '')
      ? legacyStatus as EvidenceCaseStatus
      : record.related_challan_id
        ? 'ATTACHED_TO_CHALLAN'
        : record.related_violation_id
          ? 'ATTACHED_TO_VIOLATION'
          : 'UNASSIGNED';

  return {
    ...record,
    review_status: reviewStatus,
    case_status: caseStatus,
    review_notes: record.review_notes ?? '',
  };
}

export interface EvidenceVerification {
  evidence_id: string;
  integrity_status: 'VERIFIED' | 'FAILED';
  valid: boolean;
  files: Record<string, { exists: boolean; expected_sha256: string; actual_sha256: string; valid: boolean }>;
}

export async function fetchEvidenceRecords(
  query?: string, reviewStatus?: string, caseStatus?: string,
): Promise<EvidenceRecord[]> {
  const params = new URLSearchParams({ limit: '500' });
  if (query) params.set('query', query);
  if (reviewStatus && reviewStatus !== 'ALL') params.set('review_status', reviewStatus);
  if (caseStatus && caseStatus !== 'ALL') params.set('case_status', caseStatus);
  const res = await fetch(`${API_BASE}/api/evidence?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to load evidence records');
  const records: EvidenceRecordResponse[] = await res.json();
  return records.map(normalizeEvidenceRecord);
}

export async function verifyEvidence(evidenceId: string): Promise<EvidenceVerification> {
  const res = await fetch(`${API_BASE}/api/evidence/${encodeURIComponent(evidenceId)}/verify`, { method: 'POST' });
  if (!res.ok) throw new Error('Evidence integrity verification failed');
  return res.json();
}

export async function reviewEvidence(
  evidenceId: string,
  payload: { review_status: Exclude<EvidenceReviewStatus, 'CAPTURED'>; reviewer?: string; notes?: string },
): Promise<{ success: boolean; evidence: EvidenceRecord }> {
  const res = await fetch(`${API_BASE}/api/evidence/${encodeURIComponent(evidenceId)}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Evidence review update failed');
  }
  const result: { success: boolean; evidence: EvidenceRecordResponse } = await res.json();
  return { ...result, evidence: normalizeEvidenceRecord(result.evidence) };
}

export function evidenceDownloadUrl(evidenceId: string): string {
  return authenticatedResourceUrl(`${API_BASE}/api/evidence/${encodeURIComponent(evidenceId)}/download`);
}



export interface RiskPolicy {
  version: number;
  config: { category_weights: Record<string, number>; [key: string]: number | Record<string, number> };
}
export interface RiskTask {
  id: number; status: string; plate_number: string; department: string; timestamp: string;
  assigned_role: string; priority: string; recommended_action: string; acknowledged_by?: string;
  risk_level: string; risk_score: number; risk_policy_version: number; risk_prior_count: number;
  risk_window_days: number; risk_breakdown: { factor: string; points: number }[];
  risk_missing_context: string[];
}
async function riskRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}/api/risk/${path}`, init);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || 'Risk request failed'));
  }
  return response.json();
}
export const fetchRiskPolicy = () => riskRequest<RiskPolicy>('policy');
export const fetchRiskTasks = (status = 'OPEN') => riskRequest<RiskTask[]>(`tasks?status=${encodeURIComponent(status)}`);
export const saveRiskPolicy = (policy: RiskPolicy) => riskRequest<RiskPolicy>('policy', {
  method: 'PUT', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ expected_version: policy.version, config: policy.config }),
});
export const acknowledgeRiskTask = (id: number) => riskRequest(`tasks/${id}/acknowledge`, { method: 'PATCH' });
