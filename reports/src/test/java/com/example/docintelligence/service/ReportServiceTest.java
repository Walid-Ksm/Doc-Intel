package com.example.docintelligence.service;

import com.example.docintelligence.dto.ActivityReportResponse;
import com.example.docintelligence.dto.HealthReportResponse;
import com.example.docintelligence.entity.DocumentStatus;
import com.example.docintelligence.repository.DocumentRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.Collections;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ReportServiceTest {

    @Mock
    private DocumentRepository documentRepository;

    @Mock
    private ReportProperties reportProperties;

    private Clock fixedClock;
    private ReportService reportService;

    @BeforeEach
    void setUp() {
        fixedClock = Clock.fixed(Instant.parse("2026-09-10T10:00:00Z"), ZoneOffset.UTC);
        reportService = new ReportService(documentRepository, reportProperties, fixedClock);
    }

    @Test
    @DisplayName("Activity report correctly populates status counts, top users, and daily trends")
    void testGetActivityReport() {
        when(documentRepository.count()).thenReturn(150L);
        when(reportProperties.getTopUsersLimit()).thenReturn(5);
        when(reportProperties.getDailyTrendDays()).thenReturn(14);

        DocumentRepository.StatusCountProjection p1 = mock(DocumentRepository.StatusCountProjection.class);
        when(p1.getStatus()).thenReturn("INDEXED");
        when(p1.getCount()).thenReturn(100L);

        DocumentRepository.StatusCountProjection p2 = mock(DocumentRepository.StatusCountProjection.class);
        when(p2.getStatus()).thenReturn("FAILED");
        when(p2.getCount()).thenReturn(10L);

        when(documentRepository.countDocumentsGroupedByStatus()).thenReturn(List.of(p1, p2));
        when(documentRepository.findTopUsers(5)).thenReturn(Collections.emptyList());
        when(documentRepository.findDailyTrend(any(LocalDateTime.class))).thenReturn(Collections.emptyList());

        ActivityReportResponse response = reportService.getActivityReport();

        assertThat(response.totalDocuments()).isEqualTo(150L);
        assertThat(response.statusFunnel().get(DocumentStatus.INDEXED)).isEqualTo(100L);
        assertThat(response.statusFunnel().get(DocumentStatus.FAILED)).isEqualTo(10L);
        assertThat(response.statusFunnel().get(DocumentStatus.PENDING)).isEqualTo(0L);
    }

    @Test
    @DisplayName("Health report calculates average processing time, slowest and stuck documents")
    void testGetHealthReport() {
        when(reportProperties.getStuckDocumentThreshold()).thenReturn(Duration.ofMinutes(10));
        when(reportProperties.getSlowThresholdSeconds()).thenReturn(60);
        when(reportProperties.getSlowLimit()).thenReturn(10);

        when(documentRepository.findAverageProcessingTimeSeconds()).thenReturn(12.45);
        when(documentRepository.findSlowestDocuments(60, 10)).thenReturn(Collections.emptyList());
        when(documentRepository.findStuckDocuments(any(LocalDateTime.class))).thenReturn(Collections.emptyList());

        HealthReportResponse response = reportService.getHealthReport();

        assertThat(response.averageProcessingTimeSeconds()).isEqualTo(12.45);
        assertThat(response.slowestDocuments()).isEmpty();
        assertThat(response.stuckDocuments()).isEmpty();
    }
}
