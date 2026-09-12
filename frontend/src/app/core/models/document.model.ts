export type DocumentStatus =
  | 'PENDING'
  | 'PROCESSING'
  | 'EXTRACTED'
  | 'INDEXING'
  | 'INDEXED'
  | 'FAILED';

export interface DocumentSummary {
  document_id: string;
  file_name: string;
  status: DocumentStatus;
  version: number;
  error_message?: string | null;
  created_at: string;
}

export interface DocumentDetail {
  document_id: string;
  file_name: string;
  status: DocumentStatus;
  version: number;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentExtraction {
  document_id: string;
  extracted_text: string;
  extraction_method: string;
  created_at: string;
  metadata: Record<string, any>;
}

