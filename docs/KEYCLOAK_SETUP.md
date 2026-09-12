# Keycloak & APISIX Authentication Setup Guide

This document outlines the step-by-step procedure to configure the Keycloak Identity & Access Management (IAM) realm and clients for the Document Intelligence Service.

---

## 1. Accessing the Keycloak Admin Console

1. Ensure the docker containers are running:
   ```bash
   docker compose up -d
   ```
2. Open your browser and navigate to:
   **[http://localhost:8080/admin](http://localhost:8080/admin)**
3. Log in with the initial admin credentials configured in `docker-compose.yml`:
   - **Username**: `admin`
   - **Password**: `admin`

---

## 2. Creating the Realm

1. In the top-left corner, click the realm dropdown (currently `master`) and select **Create Realm**.
2. Set the **Realm name**: `doc-intelligence`
3. Ensure **Enabled** is switched **ON**.
4. Click **Create**.

---

## 3. Creating the Angular Frontend Client (`doc-intelligence-ui`)

1. In the left navigation menu, click **Clients** → **Create client**.
2. **General Settings**:
   - **Client type**: `OpenID Connect`
   - **Client ID**: `doc-intelligence-ui`
   - **Name**: `Document Intelligence Web UI`
   - Click **Next**.
3. **Capability Config**:
   - **Client authentication**: `OFF` (Public Client for Single Page Applications)
   - **Standard flow**: `ON` (Authorization Code Flow with PKCE)
   - **Direct access grants**: `ON`
   - Click **Next**.
4. **Login Settings**:
   - **Root URL**: `http://localhost:4200`
   - **Home URL**: `http://localhost:4200`
   - **Valid redirect URIs**:
     - `http://localhost:4200/*`
     - `http://localhost:4200`
     - `http://localhost:9080/*`
   - **Valid post logout redirect URIs**:
     - `http://localhost:4200/*`
     - `http://localhost:4200`
   - **Web origins**:
     - `http://localhost:4200`
     - `+`
5. Click **Save**.
6. Under the client's **Advanced** tab:
   - Ensure **Proof Key for Code Exchange Code Challenge Method (PKCE)** is set to `S256`.

---

## 4. Configuring Realm Roles

1. In the left navigation menu, click **Realm roles** → **Create role**.
2. Create standard user role:
   - **Role name**: `USER`
   - **Description**: `Standard document processing user`
   - Click **Save**.
3. Create admin user role:
   - **Role name**: `ADMIN`
   - **Description**: `Document intelligence system administrator`
   - Click **Save**.

---

## 5. Creating Test Users

### Developer User (`alex.developer`)
1. Go to **Users** → **Add user**.
2. Fill in:
   - **Username**: `alex.developer`
   - **Email**: `alex.developer@doc-intelligence.internal`
   - **First name**: `Alex`
   - **Last name**: `Developer`
   - **Email verified**: `ON`
3. Click **Create**.
4. Navigate to the **Credentials** tab:
   - Click **Set password**.
   - **Password**: `developer`
   - **Temporary**: `OFF`
   - Click **Save**.
5. Navigate to the **Role mapping** tab:
   - Click **Assign role** → select `USER` → click **Assign**.

### System Admin User (`admin`)
1. Go to **Users** → **Add user**.
2. Fill in:
   - **Username**: `admin`
   - **Email**: `admin@doc-intelligence.internal`
   - **First name**: `System`
   - **Last name**: `Administrator`
   - **Email verified**: `ON`
3. Click **Create**.
4. Set credentials under the **Credentials** tab:
   - **Password**: `admin`
   - **Temporary**: `OFF`
5. Assign roles under the **Role mapping** tab:
   - Assign both `ADMIN` and `USER`.

---

## 6. Configuring APISIX Gateway Route

Run the automated APISIX route configuration script to bind the APISIX gateway with Keycloak OpenID Connect token inspection:

```bash
python infra/apisix/configure_apisix.py
```

This establishes the route on `http://localhost:9080` forwarding authenticated requests to FastAPI at `http://localhost:8000`.
