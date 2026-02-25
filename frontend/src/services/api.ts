import axios from 'axios';
import type { AnalyzeResponse, ChatRequest, ChatResponse } from '@/types/api';

const API_BASE = '/api/v1';

export const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const healthCheck = async (): Promise<{ status: string }> => {
  const { data } = await api.get('/health');
  return data;
};

export const analyzeFile = async (
  file: File,
  skipPolicy: boolean = false
): Promise<AnalyzeResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('skip_policy', String(skipPolicy));

  const { data } = await api.post<AnalyzeResponse>('/analyze', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return data;
};

export const chatWithAI = async (request: ChatRequest): Promise<ChatResponse> => {
  const { data } = await api.post<ChatResponse>('/chat', request);
  return data;
};
