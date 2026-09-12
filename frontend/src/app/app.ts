import { Component, computed, inject, signal, HostListener, ElementRef } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet, NavigationEnd } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { filter, map } from 'rxjs';
import { KeycloakService } from './core/auth/keycloak.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  private readonly router = inject(Router);
  private readonly elementRef = inject(ElementRef);
  readonly keycloak = inject(KeycloakService);

  readonly isProfileDropdownOpen = signal<boolean>(false);

  private readonly currentUrl = toSignal(
    this.router.events.pipe(
      filter((e): e is NavigationEnd => e instanceof NavigationEnd),
      map((e) => {
        this.isProfileDropdownOpen.set(false);
        return e.urlAfterRedirects;
      })
    ),
    { initialValue: this.router.url }
  );

  readonly isLandingPage = computed(() => {
    const url = this.currentUrl();
    const cleanUrl = url.split('?')[0].split('#')[0];
    return cleanUrl === '/' || cleanUrl === '/landing' || cleanUrl === '';
  });

  readonly isAdmin = computed(() => {
    const profile = this.keycloak.userProfile();
    return profile?.roles?.includes('ADMIN') ?? false;
  });

  toggleProfileDropdown(event: MouseEvent): void {
    event.stopPropagation();
    this.isProfileDropdownOpen.update((open) => !open);
  }

  closeProfileDropdown(): void {
    this.isProfileDropdownOpen.set(false);
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (!this.elementRef.nativeElement.contains(event.target)) {
      this.closeProfileDropdown();
    }
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    this.closeProfileDropdown();
  }

  logout(): void {
    this.closeProfileDropdown();
    this.keycloak.logout();
  }
}
