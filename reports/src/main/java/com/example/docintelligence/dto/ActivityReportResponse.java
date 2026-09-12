package com.example.docintelligence.dto;

import com.example.docintelligence.entity.DocumentStatus;
import java.util.List;
import java.util.Map;

public record ActivityReportResponse(
        long totalDocuments,
        Map<DocumentStatus, Long> statusFunnel,
        List<TopUserResponse> topUsers,
        List<DailyTrendResponse> dailyTrend) {
}
