import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { DocumentApiService } from '../../core/services/document-api.service';
import { DocumentStoreService } from '../../core/services/document-store.service';
import { DocumentDetail, DocumentExtraction } from '../../core/models/document.model';
import { StatusBadgeComponent } from '../documents/components/status-badge/status-badge.component';

@Component({
  selector: 'app-document-detail',
  standalone: true,
  imports: [CommonModule, RouterLink, DatePipe, StatusBadgeComponent],
  templateUrl: './document-detail.component.html',
  styleUrl: './document-detail.component.css',
})
export class DocumentDetailComponent implements OnInit {
  // Input bound from route parameter :id
  readonly id = input.required<string>();

  private readonly apiService = inject(DocumentApiService);
  private readonly store = inject(DocumentStoreService);
  private readonly router = inject(Router);

  readonly document = signal<DocumentDetail | null>(null);
  readonly extraction = signal<DocumentExtraction | null>(null);
  readonly isLoading = signal<boolean>(true);
  readonly isLoadingExtraction = signal<boolean>(true);
  readonly error = signal<string | null>(null);
  readonly isDeleting = signal<boolean>(false);
  readonly isDeleteModalOpen = signal<boolean>(false);
  readonly copiedId = signal<boolean>(false);
  readonly copiedMarkdown = signal<boolean>(false);
  readonly viewMode = signal<'formatted' | 'raw'>('formatted');

  readonly wordCount = computed(() => {
    const text = this.extraction()?.extracted_text;
    if (!text) return 0;
    return text.trim().split(/\s+/).filter(Boolean).length;
  });

  readonly charCount = computed(() => {
    const text = this.extraction()?.extracted_text;
    return text ? text.length : 0;
  });

  ngOnInit(): void {
    this.fetchDetail();
    this.fetchExtraction();
  }

  fetchDetail(): void {
    this.isLoading.set(true);
    this.error.set(null);

    this.apiService.getDocument(this.id()).subscribe({
      next: (doc) => {
        this.document.set(doc);
        this.isLoading.set(false);
      },
      error: (err) => {
        this.isLoading.set(false);
        this.error.set(err?.error?.detail || 'Document not found or unable to load details.');
      },
    });
  }

  fetchExtraction(): void {
    this.isLoadingExtraction.set(true);
    this.apiService.getDocumentExtraction(this.id()).subscribe({
      next: (ext) => {
        this.extraction.set(ext);
        this.isLoadingExtraction.set(false);
      },
      error: () => {
        this.isLoadingExtraction.set(false);
      },
    });
  }

  copyDocumentId(): void {
    const docId = this.document()?.document_id;
    if (docId && navigator.clipboard) {
      navigator.clipboard.writeText(docId).then(() => {
        this.copiedId.set(true);
        setTimeout(() => this.copiedId.set(false), 2000);
      });
    }
  }

  copyMarkdownText(): void {
    const text = this.extraction()?.extracted_text;
    if (text && navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => {
        this.copiedMarkdown.set(true);
        setTimeout(() => this.copiedMarkdown.set(false), 2000);
      });
    }
  }

  setViewMode(mode: 'formatted' | 'raw'): void {
    this.viewMode.set(mode);
  }

  openDeleteModal(): void {
    this.isDeleteModalOpen.set(true);
  }

  cancelDelete(): void {
    this.isDeleteModalOpen.set(false);
  }

  executeDelete(): void {
    const docId = this.document()?.document_id;
    if (!docId) return;

    this.isDeleting.set(true);
    this.store.delete(
      docId,
      () => {
        this.isDeleting.set(false);
        this.router.navigate(['/documents']);
      },
      (err) => {
        this.isDeleting.set(false);
        this.error.set(err);
      }
    );
  }
}

