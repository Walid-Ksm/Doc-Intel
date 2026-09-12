import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { DocumentApiService } from '../../core/services/document-api.service';
import { DocumentMetricsSummary } from '../../core/models/metrics.model';
import { DocumentStatus, DocumentSummary } from '../../core/models/document.model';
import { StatusBadgeComponent } from '../documents/components/status-badge/status-badge.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink, DatePipe, StatusBadgeComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css',
})
export class DashboardComponent implements OnInit {
  private readonly documentApi = inject(DocumentApiService);

  readonly metrics = signal<DocumentMetricsSummary | null>(null);
  readonly recentDocuments = signal<DocumentSummary[]>([]);
  readonly isLoading = signal<boolean>(true);
  readonly error = signal<string | null>(null);

  readonly hasDocuments = computed(() => {
    const m = this.metrics();
    return m ? m.total_documents > 0 : false;
  });

  readonly statusKeys: DocumentStatus[] = [
    'PENDING',
    'PROCESSING',
    'EXTRACTED',
    'INDEXING',
    'INDEXED',
    'FAILED',
  ];

  ngOnInit(): void {
    this.loadDashboardData();
  }

  loadDashboardData(): void {
    this.isLoading.set(true);
    this.error.set(null);

    this.documentApi.getMetricsSummary().subscribe({
      next: (summary) => {
        this.metrics.set(summary);
        this.isLoading.set(false);
      },
      error: (err) => {
        this.error.set(
          err.message || 'Failed to load metrics from the backend.'
        );
        this.isLoading.set(false);
      },
    });

    this.documentApi.listDocuments().subscribe({
      next: (docs) => {
        // Sort descending by created_at and take top 5
        const sorted = [...docs].sort(
          (a, b) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        );
        this.recentDocuments.set(sorted.slice(0, 5));
      },
      error: () => {
        // Handled silently as recent docs are complementary
      },
    });
  }

  getStatusCount(status: DocumentStatus): number {
    const m = this.metrics();
    if (!m || !m.status_breakdown) return 0;
    return m.status_breakdown[status] || 0;
  }

  getStatusPercentage(status: DocumentStatus): number {
    const m = this.metrics();
    if (!m || m.total_documents === 0) return 0;
    const count = this.getStatusCount(status);
    return Math.round((count / m.total_documents) * 100);
  }

  formatDuration(seconds: number | null): string {
    if (seconds === null || seconds === undefined) return 'N/A';
    if (seconds < 1) return '< 1s';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const remainingSecs = Math.round(seconds % 60);
    return `${mins}m ${remainingSecs}s`;
  }
}
