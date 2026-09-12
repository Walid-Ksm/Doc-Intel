package com.example.docintelligence.service;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "reports")
public class ReportProperties {
    private Duration stuckDocumentThreshold = Duration.ofMinutes(10);
    private int stuckThresholdMinutes = 10;
    private int slowThresholdSeconds = 60;
    private int slowLimit = 10;
    private int topUsersLimit = 5;
    private int dailyTrendDays = 14;

    public Duration getStuckDocumentThreshold() {
        return stuckDocumentThreshold;
    }

    public void setStuckDocumentThreshold(Duration stuckDocumentThreshold) {
        this.stuckDocumentThreshold = stuckDocumentThreshold;
    }

    public int getStuckThresholdMinutes() {
        return stuckThresholdMinutes;
    }

    public void setStuckThresholdMinutes(int stuckThresholdMinutes) {
        this.stuckThresholdMinutes = stuckThresholdMinutes;
        this.stuckDocumentThreshold = Duration.ofMinutes(stuckThresholdMinutes);
    }

    public int getSlowThresholdSeconds() {
        return slowThresholdSeconds;
    }

    public void setSlowThresholdSeconds(int slowThresholdSeconds) {
        this.slowThresholdSeconds = slowThresholdSeconds;
    }

    public int getSlowLimit() {
        return slowLimit;
    }

    public void setSlowLimit(int slowLimit) {
        this.slowLimit = slowLimit;
    }

    public int getTopUsersLimit() {
        return topUsersLimit;
    }

    public void setTopUsersLimit(int topUsersLimit) {
        this.topUsersLimit = topUsersLimit;
    }

    public int getDailyTrendDays() {
        return dailyTrendDays;
    }

    public void setDailyTrendDays(int dailyTrendDays) {
        this.dailyTrendDays = dailyTrendDays;
    }
}
