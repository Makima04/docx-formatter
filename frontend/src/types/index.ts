export interface TemplateItem {
  id: number;
  name: string;
  description: string;
  is_builtin: boolean;
  created_at: string;
  config_json?: string;
}

export interface TemplateCreate {
  name: string;
  description: string;
  config_json: string;
}

export interface TaskInfo {
  task_id: string;
  status: 'pending' | 'processing' | 'classifying' | 'assembling' | 'rendering' | 'validating' | 'repairing' | 'completed' | 'failed';
  progress: number;
  message: string;
  download_url: string | null;
  classification_result: ClassificationItem[] | null;
}

export interface ClassificationItem {
  index: number;
  type: string;
  confidence: number;
  text: string;
}

export interface RedeemCheck {
  valid: boolean;
  remaining: number;
}

export interface BatchItem {
  filename: string;
  task_id: string;
  status: string;
  error_msg: string;
}

export interface BatchStatus {
  batch_id: string;
  status: string;
  total: number;
  completed: number;
  error_msg: string;
  created_at: string;
  items: BatchItem[];
}

export interface HistoryItem {
  id: string;
  filename: string;
  template: string;
  status: 'completed' | 'failed';
  timestamp: number;
  classification_result?: ClassificationItem[];
}
