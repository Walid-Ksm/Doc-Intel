package com.example.docintelligence.dto;

import com.example.docintelligence.entity.DocumentStatus;
import java.time.LocalDateTime;

public record SlowDocumentResponse(
        String id,
        String fileName,
        DocumentStatus status,
        double durationSeconds,
        LocalDateTime updatedAt) {
}
