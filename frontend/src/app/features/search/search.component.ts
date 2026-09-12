import {
  Component,
  inject,
  ViewChild,
  ElementRef,
  AfterViewInit,
  AfterViewChecked,
  effect,
} from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ChatStoreService } from '../../core/services/chat-store.service';
import { KeycloakService } from '../../core/auth/keycloak.service';

@Component({
  selector: 'app-search',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, DatePipe],
  templateUrl: './search.component.html',
  styleUrl: './search.component.css',
})
export class SearchComponent implements AfterViewInit, AfterViewChecked {
  readonly chatStore = inject(ChatStoreService);
  readonly keycloak = inject(KeycloakService);

  @ViewChild('scrollContainer') private scrollContainer?: ElementRef<HTMLDivElement>;
  @ViewChild('bottomAnchor') private bottomAnchor?: ElementRef<HTMLDivElement>;

  // Expose signals directly from ChatStoreService so the template binds effortlessly
  readonly messages = this.chatStore.messages;
  readonly inputQuery = this.chatStore.inputQuery;
  readonly topK = this.chatStore.topK;
  readonly availableTopK = this.chatStore.availableTopK;
  readonly isGenerating = this.chatStore.isGenerating;
  readonly globalError = this.chatStore.globalError;

  private shouldScrollToBottom = false;
  private isInitialLoad = true;

  readonly starterPrompts = [
    'What are the key findings and summaries across my documents?',
    'Are there any deadlines, contractual terms, or expiration dates?',
    'Extract any numerical metrics, financial figures, or statistical data.',
  ];

  constructor() {
    effect(() => {
      // Whenever messages change (new message sent, assistant reply received, or history loaded),
      // ensure we schedule a scroll to bottom
      const msgs = this.messages();
      if (msgs.length > 0) {
        this.shouldScrollToBottom = true;
      }
    });
  }

  ngAfterViewInit(): void {
    // Jump straight to the bottom immediately when entering the chat
    this.scrollToBottom('instant');

    // Follow-up layout passes to account for rendering markdown and font layout shifts
    setTimeout(() => {
      this.scrollToBottom('instant');
      this.isInitialLoad = false;
    }, 60);

    setTimeout(() => {
      this.scrollToBottom('instant');
    }, 250);
  }

  ngAfterViewChecked(): void {
    if (this.shouldScrollToBottom) {
      this.scrollToBottom(this.isInitialLoad ? 'instant' : 'smooth');
      this.shouldScrollToBottom = false;
    }
  }

  sendMessage(overrideQuery?: string): void {
    this.chatStore.sendMessage(overrideQuery);
    this.shouldScrollToBottom = true;
  }

  toggleSources(messageId: string): void {
    this.chatStore.toggleSources(messageId);
  }

  isSourcesOpen(messageId: string): boolean {
    return this.chatStore.isSourcesOpen(messageId);
  }

  clearConversation(): void {
    this.chatStore.clearConversation();
  }

  formatScore(score: number): string {
    const percentage = Math.round(score * 1000) / 10;
    return `${percentage.toFixed(1)}%`;
  }

  private scrollToBottom(behavior: 'auto' | 'smooth' | 'instant' = 'smooth'): void {
    try {
      if (this.bottomAnchor?.nativeElement) {
        this.bottomAnchor.nativeElement.scrollIntoView({
          behavior: behavior === 'instant' ? 'auto' : behavior,
          block: 'end',
        });
      }

      const el = this.scrollContainer?.nativeElement;
      if (!el) return;

      if (behavior === 'instant' || behavior === 'auto') {
        const prevBehavior = el.style.scrollBehavior;
        el.style.scrollBehavior = 'auto';
        el.scrollTop = el.scrollHeight;
        requestAnimationFrame(() => {
          el.style.scrollBehavior = prevBehavior;
        });
      } else {
        el.scrollTo({
          top: el.scrollHeight,
          behavior: 'smooth',
        });
      }
    } catch {
      if (this.scrollContainer?.nativeElement) {
        this.scrollContainer.nativeElement.scrollTop =
          this.scrollContainer.nativeElement.scrollHeight;
      }
    }
  }
}
