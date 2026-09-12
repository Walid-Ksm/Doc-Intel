package com.example.docintelligence.config;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;

import java.time.Instant;
import java.util.Collection;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class KeycloakJwtAuthenticationConverterTest {

    private KeycloakJwtAuthenticationConverter converter;

    @BeforeEach
    void setUp() {
        converter = new KeycloakJwtAuthenticationConverter();
    }

    @Test
    @DisplayName("Should extract realm roles with ROLE_ prefix and uppercase")
    void shouldExtractRealmRoles() {
        Jwt jwt = createJwtWithClaims(Map.of(
            "realm_access", Map.of("roles", List.of("admin", "user", "viewer"))
        ));

        AbstractAuthenticationToken auth = converter.convert(jwt);

        assertThat(auth).isNotNull();
        Collection<String> authorities = auth.getAuthorities().stream()
            .map(GrantedAuthority::getAuthority)
            .toList();

        assertThat(authorities).containsExactlyInAnyOrder("ROLE_ADMIN", "ROLE_USER", "ROLE_VIEWER");
    }

    @Test
    @DisplayName("Should return empty authorities when realm_access claim is missing")
    void shouldHandleMissingRealmAccess() {
        Jwt jwt = createJwtWithClaims(Map.of("sub", "12345"));

        AbstractAuthenticationToken auth = converter.convert(jwt);

        assertThat(auth).isNotNull();
        assertThat(auth.getAuthorities()).isEmpty();
    }

    @Test
    @DisplayName("Should return empty authorities when roles list is empty")
    void shouldHandleEmptyRoles() {
        Jwt jwt = createJwtWithClaims(Map.of(
            "realm_access", Map.of("roles", List.of())
        ));

        AbstractAuthenticationToken auth = converter.convert(jwt);

        assertThat(auth).isNotNull();
        assertThat(auth.getAuthorities()).isEmpty();
    }

    private Jwt createJwtWithClaims(Map<String, Object> claims) {
        return new Jwt(
            "dummy-token",
            Instant.now(),
            Instant.now().plusSeconds(3600),
            Map.of("alg", "none"),
            claims
        );
    }
}
