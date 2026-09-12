import { DocumentStatus } from './document.model';

export interface DocumentMetricsSummary {
  total_documents: number;
  indexed_count: number;
  failed_count: number;
  pending_count: number;
  processing_count: number;
  extracted_count: number;
  indexing_count: number;
  error_rate_percentage: number;
  avg_processing_time_seconds: number | null;
  status_breakdown: Record<DocumentStatus, number>;
}
