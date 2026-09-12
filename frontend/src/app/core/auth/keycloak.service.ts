import { Injectable, signal, computed } from '@angular/core';
import Keycloak from 'keycloak-js';
import { environment } from '../../../environments/environment';
import { UserProfile } from '../models/user.model';

@Injectable({
  providedIn: 'root',
})
export class KeycloakService {
  private keycloakInstance: Keycloak | null = null;
  private isRedirectingToLogin = false;
  private visibilityListenerAttached = false;

  readonly isInitialized = signal<boolean>(false);
  readonly isAuthenticated = signal<boolean>(false);
  readonly token = signal<string | null>(null);
  readonly userProfile = signal<UserProfile | null>(null);

  readonly userInitials = computed(() => {
    const user = this.userProfile();
    if (!user) return 'AD';
    const first = user.first_name ? user.first_name[0] : '';
    const last = user.last_name ? user.last_name[0] : '';
    return (first + last).toUpperCase() || user.username.slice(0, 2).toUpperCase();
  });

  async init(): Promise<boolean> {
    if (this.isInitialized()) return this.isAuthenticated();

    try {
      this.keycloakInstance = new Keycloak({
        url: environment.keycloak.url,
        realm: environment.keycloak.realm,
        clientId: environment.keycloak.clientId,
      });

      // Hook token expiration to proactively refresh before requests fail
      this.keycloakInstance.onTokenExpired = () => {
        this.keycloakInstance?.updateToken(30)
          .then((refreshed) => {
            if (refreshed) {
              this.token.set(this.keycloakInstance?.token || null);
            }
          })
          .catch((err) => {
            console.warn('[Keycloak] Background token refresh failed (session expired):', err);
            this.handleSessionExpired();
          });
      };

      this.keycloakInstance.onAuthRefreshError = () => {
        console.warn('[Keycloak] Auth refresh error detected');
        this.handleSessionExpired();
      };

      this.keycloakInstance.onAuthLogout = () => {
        this.handleSessionExpired();
      };

      const authenticated = await this.keycloakInstance.init({
        onLoad: 'check-sso',
        checkLoginIframe: false,
        pkceMethod: 'S256',
      });

      this.isAuthenticated.set(authenticated);
      this.token.set(this.keycloakInstance.token || null);
      this.isInitialized.set(true);

      if (authenticated) {
        await this.loadUserProfile();
        this.setupVisibilityListener();
      }

      return authenticated;
    } catch (err) {
      console.warn('Keycloak initialization skipped or server offline:', err);
      this.isInitialized.set(true);
      return false;
    }
  }

  private setupVisibilityListener(): void {
    if (this.visibilityListenerAttached || typeof document === 'undefined') return;
    this.visibilityListenerAttached = true;

    // When returning from AFK (tab becomes visible again), proactively refresh the token
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible' && this.isAuthenticated()) {
        this.getToken().catch((err) => {
          console.warn('[Keycloak] Visibility refresh error:', err);
        });
      }
    });
  }

  handleSessionExpired(): void {
    this.isAuthenticated.set(false);
    this.token.set(null);
    this.userProfile.set(null);
  }

  async loadUserProfile(): Promise<void> {
    if (!this.keycloakInstance || !this.isAuthenticated()) return;

    try {
      const parsedToken = this.keycloakInstance.tokenParsed as any;
      const realmAccess = parsedToken?.realm_access || {};
      const roles: string[] = realmAccess.roles || [];

      const profile: UserProfile = {
        id: parsedToken?.sub || 'user-unknown',
        username: parsedToken?.preferred_username || 'user',
        email: parsedToken?.email || '',
        first_name: parsedToken?.given_name,
        last_name: parsedToken?.family_name,
        roles: roles.filter((r) => !r.startsWith('default-')),
        realm: environment.keycloak.realm,
        created_at: parsedToken?.iat ? new Date(parsedToken.iat * 1000).toISOString() : new Date().toISOString(),
        auth_provider: 'Keycloak OIDC',
      };

      this.userProfile.set(profile);
    } catch (err) {
      console.error('Failed to parse Keycloak profile:', err);
    }
  }

  async getToken(): Promise<string | null> {
    if (!this.keycloakInstance || !this.isAuthenticated()) return null;

    try {
      // Refresh token if it will expire within 30 seconds
      const refreshed = await this.keycloakInstance.updateToken(30);
      const currentToken = this.keycloakInstance.token || null;
      if (refreshed || currentToken !== this.token()) {
        this.token.set(currentToken);
      }
      return currentToken;
    } catch (err) {
      console.warn('Token refresh failed, session expired:', err);
      this.handleSessionExpired();
      return null;
    }
  }

  async login(redirectUri?: string): Promise<void> {
    if (this.isRedirectingToLogin) return;
    this.isRedirectingToLogin = true;

    if (!this.keycloakInstance) {
      await this.init();
    }
    return this.keycloakInstance?.login({
      redirectUri: redirectUri || (typeof window !== 'undefined' ? window.location.href : '/dashboard'),
    });
  }

  async logout(redirectUri?: string): Promise<void> {
    if (!this.keycloakInstance) return;
    this.handleSessionExpired();
    return this.keycloakInstance.logout({
      redirectUri: redirectUri || (typeof window !== 'undefined' ? window.location.origin + '/' : '/'),
    });
  }
}
