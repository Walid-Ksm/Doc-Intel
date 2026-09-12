import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, from, switchMap, throwError } from 'rxjs';
import { KeycloakService } from './keycloak.service';
import { environment } from '../../../environments/environment';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const keycloakService = inject(KeycloakService);

  // Attach token to requests going to our API backends (FastAPI or Spring Boot Reports)
  const isTargetApi =
    req.url.startsWith(environment.apiUrl) ||
    req.url.startsWith(environment.reportsApiUrl);

  if (!isTargetApi) {
    return next(req);
  }

  return from(keycloakService.getToken()).pipe(
    switchMap((token) => {
      if (token) {
        const authReq = req.clone({
          setHeaders: {
            Authorization: `Bearer ${token}`,
          },
        });
        return next(authReq);
      }

      // If user was marked authenticated but token is null (session expired while AFK),
      // avoid sending unauthenticated requests that trigger "Bearer token missing".
      if (keycloakService.isAuthenticated()) {
        keycloakService.handleSessionExpired();
        return throwError(() => new Error('Authentication session expired. Please log in again.'));
      }

      return next(req);
    }),
    catchError((err: unknown) => {
      if (err instanceof HttpErrorResponse && err.status === 401) {
        console.warn('[authInterceptor] 401 Unauthorized received from backend.');
        if (keycloakService.isAuthenticated()) {
          keycloakService.handleSessionExpired();
        }
      }
      return throwError(() => err);
    })
  );
};
