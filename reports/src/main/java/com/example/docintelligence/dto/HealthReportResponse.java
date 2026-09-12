package com.example.docintelligence.dto;

import java.util.List;

public record HealthReportResponse(
        Double averageProcessingTimeSeconds,
        List<SlowDocumentResponse> slowestDocuments,
        List<StuckDocumentResponse> stuckDocuments) {
}
