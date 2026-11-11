export type AppRole = 'Administrator' | 'Transport Officer' | 'Supervisory Officer' | 'Auditor';
export type Permission = 'manage_registry' | 'manage_geofences' | 'manage_settings' | 'review_records' | 'challan_actions' | 'operate_camera';

export function can(role: string | undefined, permission: Permission): boolean {
  if (role === 'Administrator') return true;
  if (role === 'Auditor' || !role) return false;
  if (role === 'Transport Officer' || role === 'Supervisory Officer') {
    return ['review_records', 'challan_actions'].includes(permission);
  }
  return false;
}
