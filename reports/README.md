# doc-intelligence-reports

Read-only Spring Boot reporting service for the document-intelligence PostgreSQL database.

## Run

Set the database and Keycloak issuer values, then start the service:

```powershell
$env:DB_URL = 'jdbc:postgresql://localhost:15432/doc_intelligence'
$env:DB_USERNAME = 'document_reports'
$env:DB_PASSWORD = 'reports_dev_password'
$env:KEYCLOAK_ISSUER_URI = 'http://localhost:8080/realms/doc-intelligence'
.\mvnw.cmd spring-boot:run
```

Use `mvn spring-boot:run` if Maven is installed globally. The database principal should be granted only `CONNECT` and `SELECT` on the required schema/tables.

## Security

`GET /reports/activity` and `GET /reports/health` require an authenticated Keycloak bearer token containing `realm_access.roles: ["admin"]`. The service maps that claim to `ROLE_ADMIN`. CORS is restricted to `http://localhost:4200`; only `GET` and preflight `OPTIONS` are allowed.

## Read-only design

Hibernate DDL is disabled, the Hikari pool is marked read-only and limited to five connections, all mapped entities are immutable, and report methods run in read-only transactions. The `Document` entity deliberately has no relationships, so Hibernate never scans the pgvector-backed `document_chunks` table.

`reports.stuck-document-threshold` accepts an ISO-8601 duration and defaults to `PT10M`.
