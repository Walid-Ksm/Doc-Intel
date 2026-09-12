package com.example.docintelligence.dto;

import com.example.docintelligence.entity.DocumentStatus;
import java.time.LocalDateTime;

public record StuckDocumentResponse(
        String id,
        String fileName,
        DocumentStatus status,
        double minutesStuck,
        LocalDateTime updatedAt) {
}
