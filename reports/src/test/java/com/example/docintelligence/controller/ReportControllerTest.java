package com.example.docintelligence.controller;

import com.example.docintelligence.dto.ActivityReportResponse;
import com.example.docintelligence.dto.HealthReportResponse;
import com.example.docintelligence.entity.DocumentStatus;
import com.example.docintelligence.service.ReportService;
import com.example.docintelligence.config.KeycloakJwtAuthenticationConverter;
import com.example.docintelligence.config.SecurityConfig;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.web.servlet.MockMvc;

import org.springframework.transaction.CannotCreateTransactionException;

import java.util.Collections;
import java.util.EnumMap;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(ReportController.class)
@Import({SecurityConfig.class, KeycloakJwtAuthenticationConverter.class, GlobalExceptionHandler.class})
class ReportControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private ReportService reportService;

    @MockBean
    private JwtDecoder jwtDecoder;

    @Test
    @WithMockUser(roles = "ADMIN")
    @DisplayName("GET /reports/activity with ROLE_ADMIN returns 200 OK")
    void testGetActivityAuthorized() throws Exception {
        when(reportService.getActivityReport()).thenReturn(
            new ActivityReportResponse(
                42L,
                new EnumMap<>(DocumentStatus.class),
                Collections.emptyList(),
                Collections.emptyList()
            )
        );

        mockMvc.perform(get("/reports/activity"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.totalDocuments").value(42));
    }

    @Test
    @WithMockUser(roles = "USER")
    @DisplayName("GET /reports/activity with non-admin role returns 403 Forbidden")
    void testGetActivityForbiddenForNonAdmin() throws Exception {
        mockMvc.perform(get("/reports/activity"))
            .andExpect(status().isForbidden());
    }

    @Test
    @DisplayName("GET /reports/activity without authentication returns 401 Unauthorized")
    void testGetActivityUnauthorized() throws Exception {
        mockMvc.perform(get("/reports/activity"))
            .andExpect(status().isUnauthorized());
    }

    @Test
    @WithMockUser(roles = "ADMIN")
    @DisplayName("GET /reports/health with ROLE_ADMIN returns 200 OK")
    void testGetHealthAuthorized() throws Exception {
        when(reportService.getHealthReport()).thenReturn(
            new HealthReportResponse(15.5, Collections.emptyList(), Collections.emptyList())
        );

        mockMvc.perform(get("/reports/health"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.averageProcessingTimeSeconds").value(15.5));
    }

    @Test
    @WithMockUser(roles = "ADMIN")
    @DisplayName("GET /reports/activity returns 503 Service Unavailable when DB is unreachable")
    void testGetActivityDatabaseUnreachable() throws Exception {
        when(reportService.getActivityReport())
            .thenThrow(new CannotCreateTransactionException("Connection refused"));

        mockMvc.perform(get("/reports/activity"))
            .andExpect(status().isServiceUnavailable())
            .andExpect(jsonPath("$.status").value(503))
            .andExpect(jsonPath("$.error").value("Service Unavailable"))
            .andExpect(jsonPath("$.message").value("Database service is currently unreachable or connection failed. Please retry later."));
    }

    @Test
    @WithMockUser(roles = "ADMIN")
    @DisplayName("GET /reports/health returns 503 Service Unavailable when DB is unreachable")
    void testGetHealthDatabaseUnreachable() throws Exception {
        when(reportService.getHealthReport())
            .thenThrow(new CannotCreateTransactionException("Connection timed out"));

        mockMvc.perform(get("/reports/health"))
            .andExpect(status().isServiceUnavailable())
            .andExpect(jsonPath("$.status").value(503))
            .andExpect(jsonPath("$.error").value("Service Unavailable"));
    }
}
