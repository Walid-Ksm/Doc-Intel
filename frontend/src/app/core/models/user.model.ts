export interface UserProfile {
  id: string;
  user_id?: string;
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
  role?: string;
  roles?: string[];
  realm?: string;
  organization?: string;
  created_at?: string;
  is_stub?: boolean;
  auth_provider?: string;
}
