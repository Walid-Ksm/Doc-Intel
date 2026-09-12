package com.example.docintelligence.dto;

import java.time.LocalDate;

public record DailyTrendResponse(LocalDate date, long count) {
}
