export interface PermissionCapability {
  key: string;
  label: string;
  description: string;
  finance: boolean;
  admin: boolean;
}

export interface RoleInfo {
  role: "finance" | "admin";
  label: string;
  description: string;
}

export interface PermissionsResponse {
  roles: RoleInfo[];
  capabilities: PermissionCapability[];
}

export interface SettingItem {
  key: string;
  label: string;
  value: string;
  group: string;
}

export interface SettingsResponse {
  items: SettingItem[];
  note: string;
}
