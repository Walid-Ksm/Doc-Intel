import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ActivityReportResponse, HealthReportResponse } from '../models/reports.model';

@Injectable({
  providedIn: 'root',
})
export class ReportsApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.reportsApiUrl;

  /**
   * Fetch system activity, status funnel, daily trends, and top users from Spring Boot.
   * GET http://localhost:8081/reports/activity
   */
  getActivityReport(): Observable<ActivityReportResponse> {
    return this.http.get<ActivityReportResponse>(`${this.baseUrl}/reports/activity`);
  }

  /**
   * Fetch pipeline health, processing latency, slowest documents, and stuck documents from Spring Boot.
   * GET http://localhost:8081/reports/health
   */
  getHealthReport(): Observable<HealthReportResponse> {
    return this.http.get<HealthReportResponse>(`${this.baseUrl}/reports/health`);
  }
}
