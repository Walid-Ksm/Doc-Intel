package com.example.docintelligence.controller;

import com.example.docintelligence.dto.ActivityReportResponse;
import com.example.docintelligence.dto.HealthReportResponse;
import com.example.docintelligence.service.ReportService;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping(path = "/reports", produces = MediaType.APPLICATION_JSON_VALUE)
public class ReportController {
    private final ReportService reportService;

    public ReportController(ReportService reportService) {
        this.reportService = reportService;
    }

    @GetMapping("/activity")
    public ActivityReportResponse getActivity() {
        return reportService.getActivityReport();
    }

    @GetMapping("/health")
    public HealthReportResponse getHealth() {
        return reportService.getHealthReport();
    }
}
