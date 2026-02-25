import { motion } from 'framer-motion';
import { useAppStore } from '@/store/app';

export function ResultSummary() {
  const { analysisResult } = useAppStore();

  if (!analysisResult?.security) {
    return null;
  }

  const { security } = analysisResult;
  const summary = security.vulnerability_summary || {};

  const metrics = [
    {
      label: 'Total',
      value: security.vulnerabilities.length,
      icon: '📊',
      bgColor: 'bg-slate-100',
      borderColor: 'border-slate-200',
      textColor: 'text-slate-700',
    },
    {
      label: 'Critical',
      value: summary.Critical || 0,
      icon: '🔴',
      bgColor: 'bg-white',
      borderColor: 'border-gray-200',
      textColor: 'text-red-600',
    },
    {
      label: 'High',
      value: summary.High || 0,
      icon: '🔶',
      bgColor: 'bg-white',
      borderColor: 'border-gray-200',
      textColor: 'text-orange-600',
    },
    {
      label: 'Medium',
      value: summary.Medium || 0,
      icon: '🔷',
      bgColor: 'bg-white',
      borderColor: 'border-gray-200',
      textColor: 'text-blue-600',
    },
    {
      label: 'Low',
      value: summary.Low || 0,
      icon: '🟢',
      bgColor: 'bg-white',
      borderColor: 'border-gray-200',
      textColor: 'text-green-600',
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full max-w-4xl"
    >
      <h2 className="text-2xl font-bold mb-4">Analysis Summary</h2>
      <div className="grid grid-cols-5 gap-4">
        {metrics.map((metric, index) => (
          <motion.div
            key={metric.label}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.05 * index }}
            whileHover={{ scale: 1.02, y: -2 }}
            className={`${metric.bgColor} border-2 ${metric.borderColor} rounded-xl p-3 text-center hover:shadow-md transition-all`}
          >
            <div className="text-xl mb-1">{metric.icon}</div>
            <div className={`text-2xl font-bold ${metric.textColor}`}>
              {metric.value}
            </div>
            <div className="text-xs text-gray-600 mt-1 font-medium">
              {metric.label}
            </div>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
