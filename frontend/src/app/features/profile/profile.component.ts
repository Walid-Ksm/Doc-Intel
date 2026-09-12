import { Component, inject, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { KeycloakService } from '../../core/auth/keycloak.service';
import { UserApiService } from '../../core/services/user-api.service';
import { UserProfile } from '../../core/models/user.model';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.css',
})
export class ProfileComponent implements OnInit {
  readonly keycloak = inject(KeycloakService);
  private readonly userApi = inject(UserApiService);

  readonly user = signal<UserProfile | null>(null);
  readonly isLoading = signal<boolean>(true);
  readonly copiedId = signal<boolean>(false);

  readonly initials = computed(() => {
    const u = this.user();
    if (!u) return 'U';
    const first = u.first_name ? u.first_name[0] : '';
    const last = u.last_name ? u.last_name[0] : '';
    return (first + last).toUpperCase() || u.username.slice(0, 2).toUpperCase();
  });

  ngOnInit(): void {
    this.loadProfile();
  }

  loadProfile(): void {
    this.isLoading.set(true);

    // If Keycloak user is already loaded, use it
    if (this.keycloak.userProfile()) {
      this.user.set(this.keycloak.userProfile());
      this.isLoading.set(false);
      return;
    }

    // Fallback to API user stub
    this.userApi.getCurrentUser().subscribe({
      next: (profile) => {
        this.user.set(profile);
        this.isLoading.set(false);
      },
      error: () => {
        this.isLoading.set(false);
      },
    });
  }

  copyUserId(userId: string): void {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(userId).then(() => {
      this.copiedId.set(true);
      setTimeout(() => this.copiedId.set(false), 2000);
    });
  }

  logout(): void {
    this.keycloak.logout();
  }
}
