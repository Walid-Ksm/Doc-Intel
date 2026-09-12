import { inject, Injectable, signal } from '@angular/core';
import { DocumentApiService } from './document-api.service';
import { ChatMessage, ChatMessageItem } from '../models/search.model';

const STORAGE_KEY = 'doc_intelligence_chat_history';

@Injectable({
  providedIn: 'root',
})
export class ChatStoreService {
  private readonly apiService = inject(DocumentApiService);

  readonly messages = signal<ChatMessage[]>(this.loadStoredMessages());
  readonly inputQuery = signal<string>('');
  readonly topK = signal<number>(5);
  readonly availableTopK = [3, 5, 10];
  readonly isGenerating = signal<boolean>(false);
  readonly globalError = signal<string | null>(null);

  // Tracks which citation accordions are expanded
  readonly expandedSources = signal<Record<string, boolean>>({});

  sendMessage(overrideQuery?: string): void {
    const q = (overrideQuery || this.inputQuery()).trim();
    if (!q || this.isGenerating()) return;

    this.inputQuery.set('');
    this.globalError.set(null);
    this.isGenerating.set(true);

    const userMessageId = `user_${Date.now()}`;
    const assistantMessageId = `assistant_${Date.now() + 1}`;

    const userMsg: ChatMessage = {
      id: userMessageId,
      role: 'user',
      content: q,
      timestamp: new Date(),
    };

    const assistantMsgPlaceholder: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isLoading: true,
    };

    // Keep the last 6 non-errored messages (3 turns) for multi-turn prompt feeding
    const priorHistory: ChatMessageItem[] = this.messages()
      .filter((m) => !m.isLoading && !m.error && m.content)
      .slice(-6)
      .map((m) => ({
        role: m.role,
        content: m.content,
      }));

    this.messages.update((list) => [...list, userMsg, assistantMsgPlaceholder]);
    this.saveMessages();

    this.apiService.ask(q, this.topK(), priorHistory).subscribe({
      next: (res) => {
        this.messages.update((list) =>
          list.map((m) => {
            if (m.id === assistantMessageId) {
              return {
                ...m,
                content: res.answer,
                sources: res.sources,
                isLoading: false,
              };
            }
            return m;
          })
        );
        this.isGenerating.set(false);
        this.saveMessages();
      },
      error: (err) => {
        const errorDetail =
          err?.error?.detail ||
          'Failed to generate response. Please verify that Ollama is running and accessible.';

        this.messages.update((list) =>
          list.map((m) => {
            if (m.id === assistantMessageId) {
              return {
                ...m,
                content: 'I encountered an issue generating a grounded response.',
                error: errorDetail,
                isLoading: false,
              };
            }
            return m;
          })
        );
        this.isGenerating.set(false);
        this.saveMessages();
      },
    });
  }

  toggleSources(messageId: string): void {
    this.expandedSources.update((state) => ({
      ...state,
      [messageId]: !state[messageId],
    }));
  }

  isSourcesOpen(messageId: string): boolean {
    return !!this.expandedSources()[messageId];
  }

  clearConversation(): void {
    this.messages.set([]);
    this.globalError.set(null);
    this.expandedSources.set({});
    try {
      localStorage.removeItem(STORAGE_KEY);
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // Storage access blocked or unavailable
    }
  }

  private saveMessages(): void {
    try {
      const valid = this.messages().filter((m) => !m.isLoading);
      const data = JSON.stringify(valid);
      localStorage.setItem(STORAGE_KEY, data);
      sessionStorage.setItem(STORAGE_KEY, data);
    } catch {
      // Ignore storage write quota exceptions
    }
  }

  private loadStoredMessages(): ChatMessage[] {
    try {
      const stored = localStorage.getItem(STORAGE_KEY) || sessionStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        return parsed.map((m: any) => ({
          ...m,
          timestamp: new Date(m.timestamp),
        }));
      }
    } catch {
      // Return empty array on parse failure
    }
    return [];
  }
}
