import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { KeycloakService } from './keycloak.service';

export const adminGuard: CanActivateFn = async (route, state) => {
  const keycloakService = inject(KeycloakService);
  const router = inject(Router);

  if (!keycloakService.isInitialized()) {
    await keycloakService.init();
  }

  if (!keycloakService.isAuthenticated()) {
    await keycloakService.login(window.location.origin + state.url);
    return false;
  }

  const profile = keycloakService.userProfile();
  const isAdmin = profile?.roles?.includes('ADMIN') ?? false;

  if (isAdmin) {
    return true;
  }

  // Non-admin users are safely redirected to the main dashboard
  await router.navigate(['/dashboard']);
  return false;
};
