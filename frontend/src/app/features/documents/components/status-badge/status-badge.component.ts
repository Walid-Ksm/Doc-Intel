import { Component, computed, input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DocumentStatus } from '../../../../core/models/document.model';

@Component({
  selector: 'app-status-badge',
  standalone: true,
  imports: [CommonModule],
  template: `
    <span class="status-badge" [ngClass]="statusClass()">
      @if (isProcessing()) {
        <span class="pulse-dot"></span>
      }
      <span class="status-label">{{ label() }}</span>
    </span>
  `,
  styles: [`
    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 3px 10px;
      border-radius: var(--radius-full);
      font-size: 11.5px;
      font-weight: 600;
      letter-spacing: 0.02em;
      border: 1px solid transparent;
      text-transform: uppercase;
      font-family: var(--font-mono);
      white-space: nowrap;
    }

    .pulse-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: currentColor;
      animation: pulse-ring 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
    }

    @keyframes pulse-ring {
      0%, 100% {
        opacity: 1;
        transform: scale(1);
      }
      50% {
        opacity: 0.4;
        transform: scale(1.3);
      }
    }

    .badge-pending {
      background: var(--status-pending-bg);
      color: var(--status-pending-text);
      border-color: var(--status-pending-border);
    }

    .badge-processing {
      background: var(--status-processing-bg);
      color: var(--status-processing-text);
      border-color: var(--status-processing-border);
    }

    .badge-indexed {
      background: var(--status-indexed-bg);
      color: var(--status-indexed-text);
      border-color: var(--status-indexed-border);
    }

    .badge-failed {
      background: var(--status-failed-bg);
      color: var(--status-failed-text);
      border-color: var(--status-failed-border);
    }
  `],
})
export class StatusBadgeComponent {
  readonly status = input.required<DocumentStatus>();

  readonly isProcessing = computed(() => {
    const s = this.status();
    return s === 'PENDING' || s === 'PROCESSING' || s === 'EXTRACTED' || s === 'INDEXING';
  });

  readonly statusClass = computed(() => {
    switch (this.status()) {
      case 'PENDING':
        return 'badge-pending';
      case 'PROCESSING':
      case 'EXTRACTED':
      case 'INDEXING':
        return 'badge-processing';
      case 'INDEXED':
        return 'badge-indexed';
      case 'FAILED':
        return 'badge-failed';
      default:
        return 'badge-pending';
    }
  });

  readonly label = computed(() => {
    switch (this.status()) {
      case 'PENDING':
        return 'Pending';
      case 'PROCESSING':
        return 'Processing';
      case 'EXTRACTED':
        return 'Extracted';
      case 'INDEXING':
        return 'Indexing';
      case 'INDEXED':
        return 'Indexed';
      case 'FAILED':
        return 'Failed';
      default:
        return this.status();
    }
  });
}
