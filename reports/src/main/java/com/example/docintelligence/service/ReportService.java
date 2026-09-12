package com.example.docintelligence.service;

import com.example.docintelligence.dto.ActivityReportResponse;
import com.example.docintelligence.dto.DailyTrendResponse;
import com.example.docintelligence.dto.HealthReportResponse;
import com.example.docintelligence.dto.SlowDocumentResponse;
import com.example.docintelligence.dto.StuckDocumentResponse;
import com.example.docintelligence.dto.TopUserResponse;
import com.example.docintelligence.entity.DocumentStatus;
import com.example.docintelligence.repository.DocumentRepository;
import java.time.Clock;
import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional(readOnly = true)
public class ReportService {
    private final DocumentRepository documentRepository;
    private final ReportProperties properties;
    private final Clock clock;

    @Autowired
    public ReportService(DocumentRepository documentRepository, ReportProperties properties) {
        this(documentRepository, properties, Clock.systemUTC());
    }

    ReportService(DocumentRepository documentRepository, ReportProperties properties, Clock clock) {
        this.documentRepository = documentRepository;
        this.properties = properties;
        this.clock = clock;
    }

    public ActivityReportResponse getActivityReport() {
        Map<DocumentStatus, Long> statusFunnel = new EnumMap<>(DocumentStatus.class);
        for (DocumentStatus status : DocumentStatus.values()) {
            statusFunnel.put(status, 0L);
        }
        for (DocumentRepository.StatusCountProjection row : documentRepository.countDocumentsGroupedByStatus()) {
            try {
                DocumentStatus status = DocumentStatus.valueOf(row.getStatus());
                statusFunnel.put(status, row.getCount());
            } catch (IllegalArgumentException | NullPointerException ignored) {
            }
        }

        int topUsersLimit = properties.getTopUsersLimit();
        List<TopUserResponse> topUsers = documentRepository.findTopUsers(topUsersLimit).stream()
                .map(row -> new TopUserResponse(row.getEmail(), row.getDocumentCount()))
                .toList();
        int trendDays = properties.getDailyTrendDays();
        LocalDateTime trendCutoff = LocalDateTime.now(clock).minusDays(trendDays);
        List<DailyTrendResponse> dailyTrend = documentRepository.findDailyTrend(trendCutoff).stream()
                .map(row -> new DailyTrendResponse(row.getDate(), row.getCount()))
                .toList();

        return new ActivityReportResponse(
                documentRepository.count(), statusFunnel, topUsers, dailyTrend);
    }

    public HealthReportResponse getHealthReport() {
        int slowThreshold = properties.getSlowThresholdSeconds();
        int slowLimit = properties.getSlowLimit();
        List<SlowDocumentResponse> slowestDocuments = documentRepository.findSlowestDocuments(slowThreshold, slowLimit).stream()
                .map(row -> new SlowDocumentResponse(
                        row.getId(),
                        row.getFileName(),
                        DocumentStatus.valueOf(row.getStatus()),
                        row.getDurationSeconds(),
                        row.getUpdatedAt()))
                .toList();

        LocalDateTime cutoff = LocalDateTime.now(clock).minus(properties.getStuckDocumentThreshold());
        List<StuckDocumentResponse> stuckDocuments = documentRepository.findStuckDocuments(cutoff).stream()
                .map(row -> new StuckDocumentResponse(
                        row.getId(),
                        row.getFileName(),
                        DocumentStatus.valueOf(row.getStatus()),
                        row.getMinutesStuck(),
                        row.getUpdatedAt()))
                .toList();

        return new HealthReportResponse(
                documentRepository.findAverageProcessingTimeSeconds(),
                slowestDocuments,
                stuckDocuments);
    }
}
