import { create } from 'zustand';
import type { AnalyzeResponse, ChatMessage } from '@/types/api';

type AnalysisState = 'idle' | 'uploading' | 'analyzing' | 'completed' | 'error';

interface AppState {
  // Analysis state
  analysisState: AnalysisState;
  uploadedFile: File | null;
  skipPolicy: boolean;
  analysisResult: AnalyzeResponse | null;
  error: string | null;

  // Chat state
  chatHistory: ChatMessage[];
  isChatOpen: boolean;

  // Actions
  setAnalysisState: (state: AnalysisState) => void;
  setUploadedFile: (file: File | null) => void;
  setSkipPolicy: (skip: boolean) => void;
  setAnalysisResult: (result: AnalyzeResponse | null) => void;
  setError: (error: string | null) => void;
  addChatMessage: (message: ChatMessage) => void;
  toggleChat: () => void;
  reset: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Initial state
  analysisState: 'idle',
  uploadedFile: null,
  skipPolicy: false,
  analysisResult: null,
  error: null,
  chatHistory: [],
  isChatOpen: false,

  // Actions
  setAnalysisState: (state) => set({ analysisState: state }),
  setUploadedFile: (file) => set({ uploadedFile: file }),
  setSkipPolicy: (skip) => set({ skipPolicy: skip }),
  setAnalysisResult: (result) => set({ analysisResult: result }),
  setError: (error) => set({ error }),
  addChatMessage: (message) =>
    set((state) => ({ chatHistory: [...state.chatHistory, message] })),
  toggleChat: () => set((state) => ({ isChatOpen: !state.isChatOpen })),
  reset: () =>
    set({
      analysisState: 'idle',
      uploadedFile: null,
      analysisResult: null,
      error: null,
      chatHistory: [],
    }),
}));
