import { motion } from 'framer-motion';
import { Download } from 'lucide-react';
import { useAppStore } from '@/store/app';
import { Button } from './ui/button';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export function ResultTabs() {
  const { analysisResult } = useAppStore();

  if (!analysisResult?.security) {
    return null;
  }

  const report = analysisResult.security?.report || '';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full max-w-4xl"
    >
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold">Security Report</h2>
        <Button
          variant="gradient"
          onClick={() => {
            const blob = new Blob([report], { type: 'text/markdown' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'security_report.md';
            a.click();
          }}
        >
          <Download className="w-4 h-4 mr-2" />
          Download Report
        </Button>
      </div>

      <div className="bg-white border-2 border-gray-200 rounded-2xl p-6 overflow-y-auto">
        <div className="prose prose-sm prose-slate max-w-none prose-headings:font-bold prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg prose-p:text-gray-700 prose-strong:text-gray-900 prose-ul:list-disc prose-ol:list-decimal prose-table:border-collapse prose-th:border prose-th:border-gray-300 prose-th:bg-gray-100 prose-th:p-2 prose-td:border prose-td:border-gray-300 prose-td:p-2">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
        </div>
      </div>
    </motion.div>
  );
}
