import { DocumentStatus } from './document.model';

export interface TopUserResponse {
  email: string;
  documentCount: number;
}

export interface DailyTrendResponse {
  date: string;
  count: number;
}

export interface ActivityReportResponse {
  totalDocuments: number;
  statusFunnel: Record<DocumentStatus, number>;
  topUsers: TopUserResponse[];
  dailyTrend: DailyTrendResponse[];
}

export interface SlowDocumentResponse {
  id: string;
  fileName: string;
  status: DocumentStatus;
  durationSeconds: number;
  updatedAt: string;
}

export interface StuckDocumentResponse {
  id: string;
  fileName: string;
  status: DocumentStatus;
  minutesStuck: number;
  updatedAt: string;
}

export interface HealthReportResponse {
  averageProcessingTimeSeconds: number | null;
  slowestDocuments: SlowDocumentResponse[];
  stuckDocuments: StuckDocumentResponse[];
}
