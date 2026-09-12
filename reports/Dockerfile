# ==============================================================================
# Document Intelligence Reports & Analytics Service (Spring Boot P2)
# Multi-Stage Production Container Image
# ==============================================================================

# Stage 1: Build stage with Maven and Eclipse Temurin JDK 17
FROM maven:3.9-eclipse-temurin-17-alpine AS builder

WORKDIR /build

COPY pom.xml ./
RUN mvn dependency:resolve -B

COPY src ./src
RUN mvn clean package -DskipTests -B

# Stage 2: Minimal, hardened JRE 17 Alpine runtime
FROM eclipse-temurin:17-jre-alpine AS runtime

WORKDIR /app

# Create unprivileged system user for container security
RUN addgroup -g 10002 spring && \
    adduser -u 10002 -G spring -s /bin/sh -D spring

# Copy packaged jar from builder stage
COPY --from=builder /build/target/*.jar app.jar

RUN chown -R spring:spring /app

USER spring

ENV PORT=8081 \
    JAVA_OPTS="-Xms256m -Xmx512m -XX:+UseG1GC"

EXPOSE 8081

HEALTHCHECK --interval=15s --timeout=5s --start-period=25s --retries=3 \
    CMD wget --no-verbose --spider http://127.0.0.1:8081/reports/status-funnel 2>&1 | grep -q "401\|200" || exit 1

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
