package com.example.docintelligence.repository;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.security.oauth2.jwt.JwtDecoder;

import java.net.InetSocketAddress;
import java.net.Socket;
import java.time.LocalDateTime;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@EnabledIf("isDatabaseAvailable")
class DocumentRepositoryIntegrationTest {

    @Autowired
    private DocumentRepository documentRepository;

    @MockBean
    private JwtDecoder jwtDecoder;

    static boolean isDatabaseAvailable() {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress("localhost", 15432), 1000);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    @Test
    @DisplayName("Verify native status grouping query against live PostgreSQL")
    void testCountDocumentsGroupedByStatus() {
        List<DocumentRepository.StatusCountProjection> results = documentRepository.countDocumentsGroupedByStatus();
        assertThat(results).isNotNull();
    }

    @Test
    @DisplayName("Verify native findTopUsers query against live PostgreSQL")
    void testFindTopUsers() {
        List<DocumentRepository.TopUserProjection> topUsers = documentRepository.findTopUsers(5);
        assertThat(topUsers).isNotNull();
    }

    @Test
    @DisplayName("Verify native findDailyTrend query with generate_series against live PostgreSQL")
    void testFindDailyTrend() {
        List<DocumentRepository.DailyTrendProjection> trends = documentRepository.findDailyTrend(LocalDateTime.now().minusDays(14));
        assertThat(trends).isNotNull().isNotEmpty();
    }

    @Test
    @DisplayName("Verify native findAverageProcessingTimeSeconds against live PostgreSQL")
    void testFindAverageProcessingTimeSeconds() {
        Double avg = documentRepository.findAverageProcessingTimeSeconds();
        assertThat(avg).isNotNull().isGreaterThanOrEqualTo(0.0);
    }

    @Test
    @DisplayName("Verify native findSlowestDocuments against live PostgreSQL")
    void testFindSlowestDocuments() {
        List<DocumentRepository.SlowestDocumentProjection> slowest = documentRepository.findSlowestDocuments(0, 5);
        assertThat(slowest).isNotNull();
    }

    @Test
    @DisplayName("Verify native findStuckDocuments against live PostgreSQL")
    void testFindStuckDocuments() {
        List<DocumentRepository.StuckDocumentProjection> stuck = documentRepository.findStuckDocuments(LocalDateTime.now().minusMinutes(10));
        assertThat(stuck).isNotNull();
    }
}
