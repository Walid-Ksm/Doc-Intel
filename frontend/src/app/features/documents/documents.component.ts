import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { DocumentStoreService } from '../../core/services/document-store.service';
import { DocumentSummary } from '../../core/models/document.model';
import { StatusBadgeComponent } from './components/status-badge/status-badge.component';
import { UploadModalComponent } from './components/upload-modal/upload-modal.component';

type SortField = 'file_name' | 'status' | 'version' | 'created_at';
type SortDir = 'asc' | 'desc';

@Component({
  selector: 'app-documents',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, DatePipe, StatusBadgeComponent, UploadModalComponent],
  templateUrl: './documents.component.html',
  styleUrl: './documents.component.css',
})
export class DocumentsComponent implements OnInit {
  readonly store = inject(DocumentStoreService);
  private readonly destroyRef = inject(DestroyRef);

  readonly isUploadModalOpen = signal<boolean>(false);
  readonly documentToDelete = signal<DocumentSummary | null>(null);

  // Search & sort
  readonly searchQuery = signal<string>('');
  readonly sortField = signal<SortField>('created_at');
  readonly sortDir = signal<SortDir>('desc');

  readonly filteredAndSorted = computed<DocumentSummary[]>(() => {
    const q = this.searchQuery().toLowerCase().trim();
    const docs = this.store.documents();

    const filtered = q
      ? docs.filter(
          (d) =>
            d.file_name.toLowerCase().includes(q) ||
            d.status.toLowerCase().includes(q)
        )
      : docs;

    const field = this.sortField();
    const dir = this.sortDir();

    return [...filtered].sort((a, b) => {
      let cmp = 0;
      if (field === 'file_name') {
        cmp = a.file_name.localeCompare(b.file_name);
      } else if (field === 'status') {
        cmp = a.status.localeCompare(b.status);
      } else if (field === 'version') {
        cmp = a.version - b.version;
      } else if (field === 'created_at') {
        cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      }
      return dir === 'asc' ? cmp : -cmp;
    });
  });

  constructor() {
    this.destroyRef.onDestroy(() => {
      this.store.stopPolling();
    });
  }

  ngOnInit(): void {
    this.store.loadDocuments();
  }

  sortBy(field: SortField): void {
    if (this.sortField() === field) {
      this.sortDir.update((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      this.sortField.set(field);
      this.sortDir.set('asc');
    }
  }

  sortIcon(field: SortField): string {
    if (this.sortField() !== field) return 'none';
    return this.sortDir() === 'asc' ? 'asc' : 'desc';
  }

  openUploadModal(): void {
    this.isUploadModalOpen.set(true);
  }

  closeUploadModal(): void {
    this.isUploadModalOpen.set(false);
  }

  confirmDelete(doc: DocumentSummary, event: Event): void {
    event.stopPropagation();
    this.documentToDelete.set(doc);
  }

  cancelDelete(): void {
    this.documentToDelete.set(null);
  }

  executeDelete(): void {
    const doc = this.documentToDelete();
    if (!doc) return;
    this.store.delete(doc.document_id, () => {
      this.documentToDelete.set(null);
    });
  }
}
