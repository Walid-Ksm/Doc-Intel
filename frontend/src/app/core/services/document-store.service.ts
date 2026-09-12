import { computed, DestroyRef, inject, Injectable, signal } from '@angular/core';
import { finalize, forkJoin, Subscription } from 'rxjs';
import { DocumentApiService } from './document-api.service';
import { DocumentStatus, DocumentSummary } from '../models/document.model';

const NON_TERMINAL_STATUSES = new Set<DocumentStatus>([
  'PENDING',
  'PROCESSING',
  'EXTRACTED',
  'INDEXING',
]);

const POLLING_INTERVAL_MS = 3500;

@Injectable({
  providedIn: 'root',
})
export class DocumentStoreService {
  private readonly apiService = inject(DocumentApiService);
  private readonly destroyRef = inject(DestroyRef);

  // State Signals
  readonly documents = signal<DocumentSummary[]>([]);
  readonly isLoading = signal<boolean>(false);
  readonly isPolling = signal<boolean>(false);
  readonly isUploading = signal<boolean>(false);
  readonly error = signal<string | null>(null);

  // Tracks document IDs that were uploaded in this session (to pin them at top)
  private readonly sessionUploadedIds = new Set<string>();

  // Computed state
  readonly hasActiveProcessing = computed(() =>
    this.documents().some((doc) => NON_TERMINAL_STATUSES.has(doc.status))
  );

  readonly documentCount = computed(() => this.documents().length);

  // Polling management
  private pollingTimer: ReturnType<typeof setTimeout> | null = null;
  private activePollSub: Subscription | null = null;

  constructor() {
    this.destroyRef.onDestroy(() => {
      this.stopPolling();
    });
  }

  /**
   * Initial load of documents from backend.
   * If any document is in non-terminal state, starts dynamic polling.
   */
  loadDocuments(): void {
    this.isLoading.set(true);
    this.error.set(null);

    this.apiService.listDocuments().subscribe({
      next: (docs) => {
        this.documents.set(docs);
        this.isLoading.set(false);
        this.evaluatePolling();
      },
      error: (err) => {
        this.isLoading.set(false);
        this.error.set(err?.error?.detail || 'Failed to load documents. Please try again.');
      },
    });
  }

  /**
   * Upload a single file. Returns a Promise resolving to the document_id on success.
   */
  uploadFile(file: File): Promise<{ success: true; document_id: string } | { success: false; error: string }> {
    return new Promise((resolve) => {
      this.apiService.uploadDocument(file).subscribe({
        next: (newDoc) => {
          // Track as session-uploaded so it stays pinned at top during polls
          this.sessionUploadedIds.add(newDoc.document_id);

          const summary: DocumentSummary = {
            document_id: newDoc.document_id,
            file_name: newDoc.file_name,
            status: newDoc.status,
            version: newDoc.version,
            error_message: newDoc.error_message,
            created_at: newDoc.created_at,
          };

          // Insert at top (before any non-session documents)
          this.documents.update((existing) => [
            summary,
            ...existing.filter((d) => d.document_id !== newDoc.document_id),
          ]);

          resolve({ success: true, document_id: newDoc.document_id });
          this.startPolling();
        },
        error: (err) => {
          const message = err?.error?.detail || err?.message || `Failed to upload ${file.name}.`;
          resolve({ success: false, error: message });
        },
      });
    });
  }

  /**
   * Legacy single-file upload used by upload modal (wraps uploadFile).
   */
  upload(file: File, onSuccess?: () => void, onError?: (errMsg: string) => void): void {
    this.isUploading.set(true);
    this.uploadFile(file)
      .then((result) => {
        this.isUploading.set(false);
        if ('error' in result) {
          this.error.set(result.error);
          onError?.(result.error);
        } else {
          onSuccess?.();
        }
      });
  }

  /**
   * Delete a document and remove it from state.
   */
  delete(documentId: string, onSuccess?: () => void, onError?: (errMsg: string) => void): void {
    this.apiService.deleteDocument(documentId).subscribe({
      next: () => {
        this.sessionUploadedIds.delete(documentId);
        this.documents.update((existing) =>
          existing.filter((d) => d.document_id !== documentId)
        );
        this.evaluatePolling();
        onSuccess?.();
      },
      error: (err) => {
        const message = err?.error?.detail || 'Failed to delete document.';
        this.error.set(message);
        onError?.(message);
      },
    });
  }

  private evaluatePolling(): void {
    if (this.hasActiveProcessing()) {
      this.startPolling();
    } else {
      this.stopPolling();
    }
  }

  startPolling(): void {
    if (this.isPolling()) {
      return;
    }
    this.isPolling.set(true);
    this.scheduleNextPoll(POLLING_INTERVAL_MS);
  }

  stopPolling(): void {
    if (this.pollingTimer) {
      clearTimeout(this.pollingTimer);
      this.pollingTimer = null;
    }
    if (this.activePollSub) {
      this.activePollSub.unsubscribe();
      this.activePollSub = null;
    }
    this.isPolling.set(false);
  }

  private scheduleNextPoll(delayMs: number): void {
    if (this.pollingTimer) {
      clearTimeout(this.pollingTimer);
    }
    this.pollingTimer = setTimeout(() => this.executePollStep(), delayMs);
  }

  private executePollStep(): void {
    this.activePollSub = this.apiService.listDocuments().subscribe({
      next: (freshDocs) => {
        // Build a map for O(1) status lookups
        const freshMap = new Map(freshDocs.map((d) => [d.document_id, d]));

        // Build ordered list:
        // 1. Session-uploaded docs that are still present in the fresh response, in insertion order
        // 2. All other docs from the fresh response, in server order
        const pinnedIds = [...this.sessionUploadedIds].filter((id) => freshMap.has(id));
        const unpinnedDocs = freshDocs.filter((d) => !this.sessionUploadedIds.has(d.document_id));

        const merged: DocumentSummary[] = [
          ...pinnedIds.map((id) => freshMap.get(id)!),
          ...unpinnedDocs,
        ];

        // Remove session tracking for any docs that have now reached a terminal state
        for (const id of [...this.sessionUploadedIds]) {
          const fresh = freshMap.get(id);
          if (!fresh || !NON_TERMINAL_STATUSES.has(fresh.status)) {
            this.sessionUploadedIds.delete(id);
          }
        }

        this.documents.set(merged);

        const stillProcessing = freshDocs.some((d) => NON_TERMINAL_STATUSES.has(d.status));
        if (stillProcessing) {
          this.scheduleNextPoll(POLLING_INTERVAL_MS);
        } else {
          this.stopPolling();
        }
      },
      error: (err) => {
        console.warn('[DocumentStore] Polling step error (will retry):', err);
        if (this.hasActiveProcessing()) {
          this.scheduleNextPoll(POLLING_INTERVAL_MS * 1.5);
        } else {
          this.stopPolling();
        }
      },
    });
  }
}
