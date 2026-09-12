import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { CommonModule, DatePipe, DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { ReportsApiService } from '../../core/services/reports-api.service';
import {
  ActivityReportResponse,
  HealthReportResponse,
} from '../../core/models/reports.model';
import { DocumentStatus } from '../../core/models/document.model';
import { StatusBadgeComponent } from '../documents/components/status-badge/status-badge.component';

export type ReportTab = 'activity' | 'health';

@Component({
  selector: 'app-reports',
  standalone: true,
  imports: [CommonModule, RouterLink, DatePipe, DecimalPipe, StatusBadgeComponent],
  templateUrl: './reports.component.html',
  styleUrl: './reports.component.css',
})
export class ReportsComponent implements OnInit {
  private readonly reportsApi = inject(ReportsApiService);

  readonly activeTab = signal<ReportTab>('activity');
  readonly activityData = signal<ActivityReportResponse | null>(null);
  readonly healthData = signal<HealthReportResponse | null>(null);
  readonly isLoading = signal<boolean>(true);
  readonly isRefreshing = signal<boolean>(false);
  readonly error = signal<string | null>(null);

  readonly funnelKeys: DocumentStatus[] = [
    'PENDING',
    'PROCESSING',
    'EXTRACTED',
    'INDEXING',
    'INDEXED',
    'FAILED',
  ];

  readonly totalDocuments = computed(() => this.activityData()?.totalDocuments ?? 0);

  readonly indexedCount = computed(() => {
    return this.activityData()?.statusFunnel?.['INDEXED'] ?? 0;
  });

  readonly indexedRate = computed(() => {
    const total = this.totalDocuments();
    if (total === 0) return 0;
    return Math.round((this.indexedCount() / total) * 100);
  });

  readonly inFlightCount = computed(() => {
    const funnel = this.activityData()?.statusFunnel;
    if (!funnel) return 0;
    return (funnel['PENDING'] || 0) + (funnel['PROCESSING'] || 0) + (funnel['INDEXING'] || 0);
  });

  readonly failedCount = computed(() => {
    return this.activityData()?.statusFunnel?.['FAILED'] ?? 0;
  });

  readonly maxDailyCount = computed(() => {
    const trend = this.activityData()?.dailyTrend ?? [];
    if (trend.length === 0) return 1;
    const max = Math.max(...trend.map((t) => t.count));
    return max > 0 ? max : 1;
  });

  readonly maxUserCount = computed(() => {
    const users = this.activityData()?.topUsers ?? [];
    if (users.length === 0) return 1;
    const max = Math.max(...users.map((u) => u.documentCount));
    return max > 0 ? max : 1;
  });

  readonly stuckCount = computed(() => {
    return this.healthData()?.stuckDocuments?.length ?? 0;
  });

  readonly avgProcessingTime = computed(() => {
    return this.healthData()?.averageProcessingTimeSeconds ?? null;
  });

  getStatusCount(status: string): number {
    return this.activityData()?.statusFunnel?.[status as DocumentStatus] ?? 0;
  }

  getStatusPercentage(status: string): number {
    const total = this.totalDocuments();
    if (!total) return 0;
    const count = this.getStatusCount(status);
    return Math.round((count / total) * 100);
  }

  ngOnInit(): void {
    this.loadAllReports();
  }

  setTab(tab: ReportTab): void {
    this.activeTab.set(tab);
  }

  loadAllReports(isRefresh = false): void {
    if (isRefresh) {
      this.isRefreshing.set(true);
    } else {
      this.isLoading.set(true);
    }
    this.error.set(null);

    forkJoin({
      activity: this.reportsApi.getActivityReport(),
      health: this.reportsApi.getHealthReport(),
    }).subscribe({
      next: ({ activity, health }) => {
        this.activityData.set(activity);
        this.healthData.set(health);
        this.isLoading.set(false);
        this.isRefreshing.set(false);
      },
      error: (err) => {
        console.error('Failed to load reports from Spring Boot:', err);
        this.error.set(
          err.status === 403
            ? 'Access Forbidden: Only users with the ADMIN role can view reports.'
            : 'Unable to connect to the Spring Boot Reports microservice (http://localhost:8081). Ensure the service is running and accessible.'
        );
        this.isLoading.set(false);
        this.isRefreshing.set(false);
      },
    });
  }

  formatDuration(seconds: number | null | undefined): string {
    if (seconds == null || isNaN(seconds)) return 'N/A';
    if (seconds < 60) {
      return `${seconds.toFixed(1)}s`;
    }
    const mins = Math.floor(seconds / 60);
    const remSecs = Math.round(seconds % 60);
    return `${mins}m ${remSecs}s`;
  }

  formatMinutes(minutes: number | null | undefined): string {
    if (minutes == null || isNaN(minutes)) return 'N/A';
    if (minutes < 1) {
      return `${Math.round(minutes * 60)}s`;
    }
    if (minutes < 60) {
      const mins = Math.floor(minutes);
      const secs = Math.round((minutes - mins) * 60);
      return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
    }
    const hours = Math.floor(minutes / 60);
    const remMins = Math.round(minutes % 60);
    return `${hours}h ${remMins}m`;
  }

  getUserInitials(email: string): string {
    if (!email) return 'U';
    const parts = email.split('@')[0].split('.');
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return email.slice(0, 2).toUpperCase();
  }

  parseLocalUtc(isoString: string): Date {
    if (!isoString) return new Date();
    // Spring Boot returns naive LocalDateTime in UTC e.g. "2026-09-04T10:22:31"
    // Appending 'Z' parses it correctly as UTC in JavaScript Date
    const normalized = isoString.endsWith('Z') ? isoString : `${isoString}Z`;
    return new Date(normalized);
  }
}
