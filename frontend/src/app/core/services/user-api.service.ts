import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import { delay } from 'rxjs/operators';
import { UserProfile } from '../models/user.model';

@Injectable({
  providedIn: 'root',
})
export class UserApiService {
  /**
   * Returns current user identity context.
   * Currently backed by a typed local stub — designed so that swapping this
   * implementation with real Keycloak OIDC user info requires changing only
   * this method without touching any component templates.
   */
  getCurrentUser(): Observable<UserProfile> {
    return of({
      id: 'user-123',
      user_id: 'user-123',
      username: 'alex.developer',
      email: 'alex.developer@doc-intelligence.internal',
      role: 'USER (fallback)',
      roles: ['USER'],
      realm: 'doc-intelligence',
      organization: 'DocIntelligence Sandbox',
      created_at: new Date(Date.now() - 14 * 86400000).toISOString(),
      is_stub: true,
      auth_provider: 'Local Development Stub',
    }).pipe(delay(150));
  }
}
