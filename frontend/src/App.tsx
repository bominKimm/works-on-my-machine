import { MainContent } from './components/MainContent';
import { Button } from './components/ui/button';
import { useAppStore } from './store/app';
import { RotateCcw } from 'lucide-react';

function App() {
  const { analysisState, reset } = useAppStore();
  const showNewAnalysisButton = analysisState === 'completed';

  return (
    <div className="min-h-screen gradient-bg">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 fixed top-0 left-0 right-0 z-50 p-4">
        <div className="container mx-auto flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">🛡️ Azure Security Analyzer</h1>
          <div className="flex gap-4 items-center">
            {showNewAnalysisButton && (
              <Button
                variant="outline"
                onClick={reset}
                className="flex items-center gap-2"
              >
                <RotateCcw className="w-4 h-4" />
                New Analysis
              </Button>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <MainContent />
    </div>
  );
}

export default App;
