import { Component, inject, output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DocumentStoreService } from '../../../../core/services/document-store.service';

const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp'];
const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10MB

interface QueuedFile {
  id: number;
  file: File;
  status: 'pending' | 'uploading' | 'done' | 'error';
  error?: string | undefined;
}

let _nextQueueId = 0;

@Component({
  selector: 'app-upload-modal',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="modal-backdrop" (click)="onBackdropClick($event)">
      <div class="modal-card">
        <div class="modal-header">
          <div class="header-title">
            <svg class="icon-upload" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            <h3>Upload Documents</h3>
          </div>
          <button type="button" class="btn-close" (click)="close.emit()" [disabled]="isBatchUploading()">
            &times;
          </button>
        </div>

        <div class="modal-body">
          <!-- Dropzone -->
          <div
            class="dropzone"
            [class.drag-over]="isDragging()"
            (dragover)="onDragOver($event)"
            (dragleave)="onDragLeave($event)"
            (drop)="onDrop($event)"
            (click)="fileInput.click()"
          >
            <input
              #fileInput
              type="file"
              [accept]="allowedExtensionsStr"
              multiple
              style="display: none"
              (change)="onFileSelected($event)"
            />

            <div class="dropzone-content">
              <div class="drop-icon-wrapper">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="16 16 12 12 8 16" />
                  <line x1="12" y1="12" x2="12" y2="21" />
                  <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
                </svg>
              </div>
              <p class="dropzone-title">Click to select or drag & drop files</p>
              <p class="dropzone-subtitle">PDF, DOCX, PNG, JPG, TIFF, BMP · max 10MB each · multiple files supported</p>
            </div>
          </div>

          <!-- File Queue -->
          @if (queue().length > 0) {
            <div class="queue-container">
              <div class="queue-header">
                <span class="queue-label">{{ queue().length }} file{{ queue().length !== 1 ? 's' : '' }} selected</span>
                @if (!isBatchUploading()) {
                  <button type="button" class="btn-clear-all" (click)="clearQueue()">Clear all</button>
                }
              </div>

              <div class="queue-list">
                @for (item of queue(); track item.file.name + item.file.size) {
                  <div class="queue-item" [class.queue-done]="item.status === 'done'" [class.queue-error]="item.status === 'error'">
                    <div class="queue-item-icon">
                      @if (item.status === 'uploading') {
                        <span class="file-spinner"></span>
                      } @else if (item.status === 'done') {
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                          <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                      } @else if (item.status === 'error') {
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                          <line x1="18" y1="6" x2="6" y2="18"></line>
                          <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                      } @else {
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                          <polyline points="14 2 14 8 20 8"></polyline>
                        </svg>
                      }
                    </div>
                    <div class="queue-item-info">
                      <span class="queue-item-name">{{ item.file.name }}</span>
                      @if (item.status === 'error' && item.error) {
                        <span class="queue-item-error">{{ item.error }}</span>
                      } @else {
                        <span class="queue-item-size">{{ formatFileSize(item.file.size) }}</span>
                      }
                    </div>
                    <span class="queue-item-badge" [class]="'badge-' + item.status">
                      {{ item.status }}
                    </span>
                  </div>
                }
              </div>
            </div>
          }

          <!-- Validation error for dropped files that failed inspection -->
          @if (validationError()) {
            <div class="alert-error">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
              <span>{{ validationError() }}</span>
            </div>
          }

          <!-- Batch progress summary -->
          @if (isBatchUploading()) {
            <div class="progress-bar-wrapper">
              <div class="progress-bar-track">
                <div class="progress-bar-fill" [style.width.%]="batchProgressPercent()"></div>
              </div>
              <span class="progress-label code-mono">{{ batchDone() }} / {{ queue().length }} uploaded</span>
            </div>
          }
        </div>

        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" (click)="close.emit()" [disabled]="isBatchUploading()">
            Cancel
          </button>
          <button
            type="button"
            class="btn btn-primary"
            (click)="submitBatch()"
            [disabled]="pendingFiles().length === 0 || isBatchUploading()"
          >
            @if (isBatchUploading()) {
              <span class="btn-spinner"></span>
              Uploading...
            } @else {
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
              Upload {{ pendingFiles().length }} file{{ pendingFiles().length !== 1 ? 's' : '' }}
            }
          </button>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1000;
      padding: 16px;
      animation: fadeIn 0.15s ease-out;
    }

    .modal-card {
      background: #09090c;
      border: 1px solid var(--border-default);
      border-radius: var(--radius-2xl);
      width: 100%;
      max-width: 520px;
      max-height: 90vh;
      display: flex;
      flex-direction: column;
      box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.06), 0 24px 60px rgba(0, 0, 0, 0.8), 0 0 60px rgba(94, 106, 210, 0.12);
      overflow: hidden;
      animation: scaleUp 0.2s var(--ease-expo-out);
    }

    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    @keyframes scaleUp { from { transform: scale(0.96); opacity: 0; } to { transform: scale(1); opacity: 1; } }

    .modal-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 18px 22px;
      border-bottom: 1px solid var(--border-default);
      flex-shrink: 0;
      background: rgba(255, 255, 255, 0.02);
    }

    .header-title {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .icon-upload {
      width: 18px;
      height: 18px;
      color: var(--accent-bright);
    }

    .modal-header h3 {
      font-size: 15px;
      font-weight: 600;
      letter-spacing: -0.01em;
      color: var(--foreground);
    }

    .btn-close {
      color: var(--foreground-muted);
      font-size: 20px;
      line-height: 1;
      padding: 4px 8px;
      border-radius: var(--radius-sm);
      transition: all var(--transition-fast);
    }

    .btn-close:hover {
      color: var(--foreground);
      background: rgba(255, 255, 255, 0.05);
    }

    .modal-body {
      padding: 22px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      overflow-y: auto;
      flex: 1;
    }

    .dropzone {
      border: 1px dashed rgba(255, 255, 255, 0.15);
      border-radius: var(--radius-lg);
      padding: 32px 20px;
      text-align: center;
      background: rgba(255, 255, 255, 0.02);
      cursor: pointer;
      transition: all var(--transition-fast);
    }

    .dropzone:hover, .dropzone.drag-over {
      border-color: var(--accent-bright);
      background: rgba(94, 106, 210, 0.06);
      box-shadow: 0 0 20px rgba(94, 106, 210, 0.15);
    }

    .dropzone-content {
      display: flex;
      flex-direction: column;
      align-items: center;
    }

    .drop-icon-wrapper {
      width: 44px;
      height: 44px;
      border-radius: var(--radius-lg);
      background: var(--accent-soft);
      border: 1px solid var(--border-accent);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 12px;
      color: var(--accent-bright);
    }

    .drop-icon-wrapper svg { width: 20px; height: 20px; }

    .dropzone-title {
      font-weight: 500;
      color: var(--foreground);
      font-size: 13.5px;
      margin-bottom: 4px;
    }

    .dropzone-subtitle {
      font-size: 12px;
      color: var(--foreground-muted);
    }

    /* Queue */
    .queue-container {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .queue-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .queue-label {
      font-size: 11.5px;
      font-weight: 600;
      color: var(--foreground-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      font-family: var(--font-mono);
    }

    .btn-clear-all {
      font-size: 11.5px;
      color: var(--accent-bright);
      padding: 2px 6px;
      border-radius: var(--radius-sm);
    }

    .btn-clear-all:hover {
      background: var(--accent-soft);
    }

    .queue-list {
      display: flex;
      flex-direction: column;
      gap: 6px;
      max-height: 240px;
      overflow-y: auto;
      padding-right: 4px;
    }

    .queue-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 12px;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-md);
      transition: all var(--transition-fast);
    }

    .queue-item.queue-done {
      border-color: rgba(16, 185, 129, 0.25);
      background: rgba(16, 185, 129, 0.06);
    }

    .queue-item.queue-error {
      border-color: rgba(239, 68, 68, 0.25);
      background: rgba(239, 68, 68, 0.06);
    }

    .queue-item-icon {
      width: 24px;
      height: 24px;
      flex-shrink: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--foreground-muted);
    }

    .queue-item.queue-done .queue-item-icon { color: #34d399; }
    .queue-item.queue-error .queue-item-icon { color: #f87171; }

    .queue-item-icon svg { width: 15px; height: 15px; }

    .queue-item-info {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .queue-item-name {
      font-size: 13px;
      font-weight: 500;
      color: var(--foreground);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .queue-item-size {
      font-size: 11px;
      color: var(--foreground-muted);
      font-family: var(--font-mono);
    }

    .queue-item-error {
      font-size: 11px;
      color: #f87171;
    }

    .queue-item-badge {
      font-size: 10.5px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      padding: 2px 7px;
      border-radius: var(--radius-full);
      font-family: var(--font-mono);
      flex-shrink: 0;
    }

    .badge-pending { background: rgba(255, 255, 255, 0.05); color: var(--foreground-muted); }
    .badge-uploading { background: var(--status-processing-bg); color: var(--status-processing-text); }
    .badge-done { background: var(--status-indexed-bg); color: var(--status-indexed-text); }
    .badge-error { background: var(--status-failed-bg); color: var(--status-failed-text); }

    /* Progress */
    .progress-bar-wrapper {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .progress-bar-track {
      flex: 1;
      height: 5px;
      background: rgba(255, 255, 255, 0.08);
      border-radius: var(--radius-full);
      overflow: hidden;
    }

    .progress-bar-fill {
      height: 100%;
      background: linear-gradient(90deg, var(--accent), var(--accent-bright));
      border-radius: var(--radius-full);
      transition: width 0.4s var(--ease-expo-out);
    }

    .progress-label {
      font-size: 11.5px;
      color: var(--foreground-muted);
      font-family: var(--font-mono);
      white-space: nowrap;
    }

    .alert-error {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 14px;
      background: var(--status-failed-bg);
      border: 1px solid var(--status-failed-border);
      border-radius: var(--radius-md);
      color: var(--status-failed-text);
      font-size: 12.5px;
    }

    .alert-error svg { width: 15px; height: 15px; flex-shrink: 0; }

    .modal-footer {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
      padding: 16px 22px;
      background: rgba(255, 255, 255, 0.015);
      border-top: 1px solid var(--border-default);
      flex-shrink: 0;
    }

    .file-spinner {
      width: 14px;
      height: 14px;
      border: 2px solid rgba(94, 106, 210, 0.3);
      border-top-color: var(--accent-bright);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      display: inline-block;
    }

    .btn-spinner {
      width: 14px;
      height: 14px;
      border: 2px solid rgba(255, 255, 255, 0.3);
      border-top-color: #ffffff;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }

    @keyframes spin { to { transform: rotate(360deg); } }
  `],
})
export class UploadModalComponent {
  readonly store = inject(DocumentStoreService);
  readonly close = output<void>();

  readonly queue = signal<QueuedFile[]>([]);
  readonly isDragging = signal<boolean>(false);
  readonly isBatchUploading = signal<boolean>(false);
  readonly batchDone = signal<number>(0);
  readonly validationError = signal<string | null>(null);

  readonly pendingFiles = () => this.queue().filter((q) => q.status === 'pending');
  readonly batchProgressPercent = () => {
    const total = this.queue().length;
    return total === 0 ? 0 : Math.round((this.batchDone() / total) * 100);
  };

  readonly allowedExtensionsStr = ALLOWED_EXTENSIONS.join(',');

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(true);
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(false);
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      this.addFilesToQueue(Array.from(files));
    }
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.addFilesToQueue(Array.from(input.files));
      input.value = '';
    }
  }

  onBackdropClick(event: MouseEvent): void {
    if ((event.target as HTMLElement).classList.contains('modal-backdrop')) {
      if (!this.isBatchUploading()) {
        this.close.emit();
      }
    }
  }

  clearQueue(): void {
    this.queue.set([]);
    this.validationError.set(null);
  }

  private addFilesToQueue(files: File[]): void {
    this.validationError.set(null);
    const errors: string[] = [];
    const toAdd: QueuedFile[] = [];

    for (const file of files) {
      const ext = '.' + file.name.split('.').pop()?.toLowerCase();
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        errors.push(`${file.name}: unsupported format (${ext})`);
        continue;
      }
      if (file.size > MAX_FILE_SIZE_BYTES) {
        errors.push(`${file.name}: exceeds 10MB limit`);
        continue;
      }
      // Avoid duplicate filenames in queue
      const existing = this.queue().find((q) => q.file.name === file.name && q.file.size === file.size);
      if (existing) continue;

      toAdd.push({ id: ++_nextQueueId, file, status: 'pending' });
    }

    if (errors.length > 0) {
      this.validationError.set(errors.join(' | '));
    }

    if (toAdd.length > 0) {
      this.queue.update((q) => [...q, ...toAdd]);
    }
  }

  async submitBatch(): Promise<void> {
    const pending = this.pendingFiles();
    if (pending.length === 0 || this.isBatchUploading()) return;

    this.isBatchUploading.set(true);
    this.batchDone.set(0);

    for (const item of pending) {
      // Mark uploading — compare by stable id, not object reference
      this.queue.update((q) =>
        q.map((qi) => (qi.id === item.id ? { ...qi, status: 'uploading' as const } : qi))
      );

      const result = await this.store.uploadFile(item.file);

      this.batchDone.update((n) => n + 1);

      let status: 'done' | 'error';
      let error: string | undefined;

      if ('error' in result) {
        status = 'error';
        error = result.error;
      } else {
        status = 'done';
      }

      // Apply done / error status — still use id so the spread copy is found correctly
      this.queue.update((q) =>
        q.map((qi) =>
          qi.id === item.id
            ? {
                ...qi,
                status,
                error,
              }
            : qi
        )
      );
    }

    this.isBatchUploading.set(false);

    // Auto-close only if every file succeeded; stay open and show errors otherwise
    const anyFailed = this.queue().some((q) => q.status === 'error');
    if (!anyFailed) {
      this.close.emit();
    }
  }

  formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }
}
