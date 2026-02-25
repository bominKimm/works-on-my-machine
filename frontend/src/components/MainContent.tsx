import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '@/store/app';
import { UploadCard } from './UploadCard';
import { PipelineBar } from './PipelineBar';
import { ResultSummary } from './ResultSummary';
import { ResultTabs } from './ResultTabs';
import { ChatPanel } from './ChatPanel';
import { MessageCircle } from 'lucide-react';
import { analyzeFile } from '@/services/api';

export function MainContent() {
  const {
    analysisState,
    uploadedFile,
    skipPolicy,
    isChatOpen,
    toggleChat,
    setAnalysisState,
    setAnalysisResult,
    setError,
  } = useAppStore();

  const handleAnalyze = async () => {
    if (!uploadedFile) return;

    setAnalysisState('analyzing');
    setError(null);

    try {
      const result = await analyzeFile(uploadedFile, skipPolicy);

      if (result.status === 'success') {
        setAnalysisResult(result);
        setAnalysisState('completed');
      } else {
        setError(result.error || 'Analysis failed');
        setAnalysisState('error');
      }
    } catch (error) {
      console.error('Analysis error:', error);
      setError(error instanceof Error ? error.message : 'Network error');
      setAnalysisState('error');
    }
  };

  const showResults = analysisState === 'completed';

  return (
    <div className="container mx-auto px-4 pt-24 pb-8 relative">
      {/* Pipeline Bar - always visible after upload */}
      <AnimatePresence>
        {(analysisState === 'analyzing' || showResults) && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="mb-8"
          >
            <div className="bg-white border-2 border-gray-200 rounded-2xl py-4 shadow-sm">
              <PipelineBar />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Content Area */}
      <div className="flex gap-8 min-h-[calc(100vh-250px)]">
        {/* Left side - Results */}
        <AnimatePresence>
          {showResults && (
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="flex-1 flex flex-col items-center gap-8"
            >
              <ResultSummary />
              <ResultTabs />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Right side - Chat Panel */}
        <AnimatePresence>
          {showResults && isChatOpen && (
            <ChatPanel open={isChatOpen} onClose={toggleChat} />
          )}
        </AnimatePresence>

        {/* Center - Upload/Progress when not completed */}
        {!showResults && (
          <div className="flex-1 flex flex-col items-center gap-8">
            {/* Project Description */}
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-center max-w-2xl"
            >
              <h2 className="text-3xl font-bold text-gray-900 mb-3">
                설계 단계 보안 위험 분석
              </h2>
              <p className="text-gray-500 leading-relaxed">
                목업 컨테이너 환경을 구성하고, 설계 단계에서<br />
                공격 가능성을 식별해 검증 우선순위를 제시합니다.
              </p>
              <p className="text-xs text-gray-400 mt-2">
                실제 침투 테스트를 대체하는 도구가 아닙니다. 배포 전 설계 리스크를 조기에 발견하고, 보안 검토 우선순위를 정하는 데 활용하세요.
              </p>
              <div className="flex justify-center gap-6 mt-4 text-sm text-gray-400">
                <span>🔍 설계 취약점 탐지</span>
                <span>⚡ 공격 시나리오 식별</span>
                <span>📋 검증 우선순위 리포트</span>
              </div>
            </motion.div>

            <UploadCard onStartAnalysis={handleAnalyze} />

            {/* Analysis Progress */}
            <AnimatePresence>
              {analysisState === 'analyzing' && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  className="bg-white border-2 border-gray-200 rounded-2xl p-8 w-full max-w-md text-center shadow-sm"
                >
                  <div className="animate-spin w-16 h-16 border-4 border-gray-900 border-t-transparent rounded-full mx-auto mb-4" />
                  <p className="text-lg font-semibold text-gray-900">Analyzing architecture diagram...</p>
                  <p className="text-sm text-gray-600 mt-2">This may take a few moments</p>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Error State */}
            <AnimatePresence>
              {analysisState === 'error' && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 20 }}
                  className="bg-red-50 border-2 border-red-200 rounded-2xl p-6 w-full max-w-md text-center"
                >
                  <p className="text-lg font-semibold text-red-600">❌ Analysis Failed</p>
                  <p className="text-sm text-gray-600 mt-2">
                    {useAppStore.getState().error || 'An unexpected error occurred'}
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>

      {/* FAB - AI Advisor */}
      <AnimatePresence>
        {showResults && !isChatOpen && (
          <motion.button
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={toggleChat}
            className="fixed bottom-8 right-8 w-16 h-16 rounded-full bg-gray-900 text-white shadow-lg hover:shadow-xl flex items-center justify-center z-40"
            title="AI Security Advisor"
          >
            <MessageCircle className="w-8 h-8" />
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
}
