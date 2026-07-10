export interface AdminUserApiResponse {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface AdminUserListApiResponse {
  items: AdminUserApiResponse[];
  total: number;
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface AdminUser {
  id: string;
  fullName: string;
  email: string;
  role: string;
  isActive: boolean;
  createdAt: string;
}

export interface CreateAdminUserPayload {
  email: string;
  password: string;
  full_name: string;
  role: string;
}

export interface UpdateUserRolePayload {
  role: string;
}

export interface UpdateUserStatusPayload {
  is_active: boolean;
}

export interface ResetUserPasswordPayload {
  new_password: string;
}

export interface RoleDefinition {
  role: string;
  description: string;
  userCount: number;
}

export interface SettingsField {
  id: string;
  label: string;
  value: string;
  type?: "text" | "toggle" | "select";
  options?: string[];
  enabled?: boolean;
}

export interface SettingsSectionData {
  id: string;
  title: string;
  description: string;
  fields: SettingsField[];
}
