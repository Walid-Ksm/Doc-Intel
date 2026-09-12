package com.example.docintelligence.repository;

import com.example.docintelligence.entity.Document;
import com.example.docintelligence.entity.DocumentStatus;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface DocumentRepository extends JpaRepository<Document, String> {

    long countByStatus(DocumentStatus status);

    @Query(value = "SELECT status, count(*) as count FROM documents GROUP BY status", nativeQuery = true)
    List<StatusCountProjection> countDocumentsGroupedByStatus();

    @Query(value = """
            SELECT COALESCE(u.email, d.user_id) AS email, COUNT(*) AS "documentCount"
            FROM documents d
            LEFT JOIN users u ON u.id = d.user_id
            GROUP BY COALESCE(u.email, d.user_id)
            ORDER BY COUNT(*) DESC, COALESCE(u.email, d.user_id) ASC
            LIMIT :limit
            """, nativeQuery = true)
    List<TopUserProjection> findTopUsers(@Param("limit") int limit);

    default List<TopUserProjection> findTopUsers() {
        return findTopUsers(5);
    }

    @Query(value = """
            SELECT CAST(days.day AS date) AS date, COUNT(d.id) AS count
            FROM generate_series(
                    CAST(:cutoff AS timestamp),
                    date_trunc('day', timezone('UTC', now())),
                    interval '1 day') AS days(day)
            LEFT JOIN documents d
                ON d.created_at >= days.day
               AND d.created_at < days.day + interval '1 day'
            GROUP BY days.day
            ORDER BY days.day ASC
            """, nativeQuery = true)
    List<DailyTrendProjection> findDailyTrend(@Param("cutoff") LocalDateTime cutoff);

    default List<DailyTrendProjection> findDailyTrend() {
        return findDailyTrend(LocalDateTime.now().minusDays(29));
    }

    @Query(value = """
            SELECT COALESCE(AVG(EXTRACT(EPOCH FROM (updated_at - created_at))), 0)
            FROM documents
            WHERE status IN ('INDEXED', 'FAILED')
            """, nativeQuery = true)
    Double findAverageProcessingTimeSeconds();

    @Query(value = """
            SELECT id AS id,
                   file_name AS "fileName",
                   CAST(status AS text) AS status,
                   EXTRACT(EPOCH FROM (updated_at - created_at)) AS "durationSeconds",
                   updated_at AS "updatedAt"
            FROM documents
            WHERE status IN ('INDEXED', 'FAILED')
              AND EXTRACT(EPOCH FROM (updated_at - created_at)) >= :thresholdSeconds
            ORDER BY (updated_at - created_at) DESC, id ASC
            LIMIT :limit
            """, nativeQuery = true)
    List<SlowestDocumentProjection> findSlowestDocuments(@Param("thresholdSeconds") int thresholdSeconds, @Param("limit") int limit);

    default List<SlowestDocumentProjection> findSlowestCompletedDocuments() {
        return findSlowestDocuments(0, 5);
    }

    @Query(value = """
            SELECT id AS id,
                   file_name AS "fileName",
                   CAST(status AS text) AS status,
                   EXTRACT(EPOCH FROM (timezone('UTC', now()) - updated_at)) / 60.0 AS "minutesStuck",
                   updated_at AS "updatedAt"
            FROM documents
            WHERE status IN ('PROCESSING', 'INDEXING')
              AND updated_at < :cutoff
            ORDER BY updated_at ASC, id ASC
            """, nativeQuery = true)
    List<StuckDocumentProjection> findStuckDocuments(@Param("cutoff") LocalDateTime cutoff);

    interface TopUserProjection {
        String getEmail();
        long getDocumentCount();
    }

    interface DailyTrendProjection {
        LocalDate getDate();
        long getCount();
    }

    interface SlowestDocumentProjection {
        String getId();
        String getFileName();
        String getStatus();
        double getDurationSeconds();
        LocalDateTime getUpdatedAt();
    }

    interface StuckDocumentProjection {
        String getId();
        String getFileName();
        String getStatus();
        double getMinutesStuck();
        LocalDateTime getUpdatedAt();
    }

    interface StatusCountProjection {
        String getStatus();
        long getCount();
    }
}
