export interface SearchResultItem {
  chunk_id: string;
  document_id: string;
  file_name: string;
  chunk_text: string;
  chunk_index: number;
  similarity_score: number;
  metadata: Record<string, unknown>;
}

export interface SearchResponse {
  query: string;
  total_results: number;
  results: SearchResultItem[];
}

export interface RAGSourceItem {
  document_id: string;
  file_name: string;
  chunk_text: string;
  similarity_score: number;
}


export interface RAGAskResponse {
  answer: string;
  sources: RAGSourceItem[];
}

export interface ChatMessageItem {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sources?: RAGSourceItem[];
  isLoading?: boolean;
  error?: string;
}
