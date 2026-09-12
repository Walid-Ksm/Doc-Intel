package com.example.docintelligence;

import com.example.docintelligence.service.ReportProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@SpringBootApplication
@EnableConfigurationProperties(ReportProperties.class)
public class DocIntelligenceReportsApplication {
    public static void main(String[] args) {
        SpringApplication.run(DocIntelligenceReportsApplication.class, args);
    }
}
