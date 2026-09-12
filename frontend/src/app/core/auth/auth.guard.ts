import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { KeycloakService } from './keycloak.service';

export const authGuard: CanActivateFn = async (route, state) => {
  const keycloakService = inject(KeycloakService);

  if (!keycloakService.isInitialized()) {
    await keycloakService.init();
  }

  if (keycloakService.isAuthenticated()) {
    return true;
  }

  // Redirect to Keycloak login with return target
  await keycloakService.login(window.location.origin + state.url);
  return false;
};
