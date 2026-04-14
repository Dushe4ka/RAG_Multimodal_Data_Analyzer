export type UserProfile = {
  login: string;
  admin: boolean;
  name: string;
  surname: string;
  role: string;
  created_at: string;
};

export type AdminUser = UserProfile;

export type CreateUserPayload = {
  login: string;
  password: string;
  name: string;
  surname: string;
  role: string;
  admin: boolean;
};

export type UpdateUserNamePayload = {
  login: string;
  name?: string;
  surname?: string;
};

export type UpdateUserPasswordPayload = {
  login: string;
  new_pwd: string;
};

export type ProfileEditNamePayload = {
  name?: string;
  surname?: string;
};

export type ProfileEditPasswordPayload = {
  old_pwd: string;
  new_pwd: string;
  confirm_pwd: string;
};

export type Chat = {
  chat_id: string;
  user_id: string;
  title: string;
  workspace_ids?: string[];
  created_at: string;
  updated_at: string;
};

export type HistoryMessage = {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  created_at?: string;
};

export type Source = {
  file_id?: string;
  workspace_id?: string;
  score?: number;
  text?: string;
  source?: string;
  download_url?: string;
};

export type ChatMessageResponse = {
  chat_id: string;
  answer: string;
  sources: Source[];
  retrieval_trace?: Array<{
    iteration: number;
    query: string;
    hits: number;
    top_score: number;
  }>;
};

export type Workspace = {
  workspace_id: string;
  owner_user_id: string;
  name: string;
  is_private: boolean;
  created_at: string;
  updated_at: string;
  member_user_ids: string[];
};

export type FileDoc = {
  file_id: string;
  workspace_id: string;
  owner_user_id: string;
  filename: string;
  media_type: string;
  object_key: string;
  content_type: string;
  size_bytes: number;
  extraction_status: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type UploadResponse = {
  file_id: string;
  workspace_id: string;
  filename: string;
  media_type: string;
  extraction_status: string;
  message?: string;
};
