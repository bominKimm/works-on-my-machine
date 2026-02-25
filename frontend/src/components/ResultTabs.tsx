import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, Shield, FileText, Zap, Download } from 'lucide-react';
import { useAppStore } from '@/store/app';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from './ui/accordion';
import { Button } from './ui/button';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useState } from 'react';

type CardType = 'vulnerabilities' | 'attacks' | 'policy' | 'report';

const TABS = [
  {
    id: 'vulnerabilities' as CardType,
    icon: AlertTriangle,
    title: 'Vulnerabilities',
    emoji: '🔴',
  },
  {
    id: 'attacks' as CardType,
    icon: Zap,
    title: 'Attack Scenarios',
    emoji: '⚡',
  },
  {
    id: 'policy' as CardType,
    icon: Shield,
    title: 'Policy Check',
    emoji: '🛡️',
  },
  {
    id: 'report' as CardType,
    icon: FileText,
    title: 'Report',
    emoji: '📊',
  },
];

const SeverityBadge = ({ severity }: { severity: string }) => {
  const colors: Record<string, string> = {
    Critical: 'bg-red-500',
    High: 'bg-orange-500',
    Medium: 'bg-blue-500',
    Low: 'bg-green-500',
  };

  return (
    <span className={`inline-block px-2 py-1 rounded text-xs font-semibold text-white ${colors[severity] || 'bg-gray-500'}`}>
      {severity}
    </span>
  );
};

export function ResultTabs() {
  const { analysisResult } = useAppStore();
  const [selectedTab, setSelectedTab] = useState<CardType>('vulnerabilities');

  if (!analysisResult?.security) {
    return null;
  }

  const getTabCount = (id: CardType) => {
    const { security, policy } = analysisResult;
    
    switch (id) {
      case 'vulnerabilities':
        return security?.vulnerabilities.length || 0;
      case 'attacks':
        return security?.attack_scenarios.length || 0;
      case 'policy':
        return policy?.violations.length || 0;
      case 'report':
        return '📄';
    }
  };

  const renderContent = () => {
    switch (selectedTab) {
      case 'vulnerabilities':
        const vulns = analysisResult.security?.vulnerabilities || [];
        return (
          <div className="space-y-2">
            <Accordion type="single" collapsible className="w-full">
              {vulns.map((vuln) => (
                <AccordionItem key={vuln.id} value={vuln.id}>
                  <AccordionTrigger className="text-left">
                    <div className="flex items-center gap-2">
                      <SeverityBadge severity={vuln.severity} />
                      <span className="font-semibold">{vuln.id}</span>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-3 pl-4">
                      <div>
                        <p className="text-sm font-semibold">Resource:</p>
                        <p className="text-sm text-gray-600">{vuln.resource_name}</p>
                      </div>
                      <div>
                        <p className="text-sm font-semibold">Description:</p>
                        <p className="text-sm text-gray-600">{vuln.description}</p>
                      </div>
                      <div>
                        <p className="text-sm font-semibold">Impact:</p>
                        <p className="text-sm text-gray-600">{vuln.impact}</p>
                      </div>
                      <div>
                        <p className="text-sm font-semibold">Recommendation:</p>
                        <p className="text-sm text-gray-600">{vuln.recommendation}</p>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </div>
        );

      case 'attacks':
        const attacks = analysisResult.security?.attack_scenarios || [];
        return (
          <div className="space-y-2">
            <Accordion type="single" collapsible className="w-full">
              {attacks.map((attack, index) => (
                <AccordionItem key={index} value={`attack-${index}`}>
                  <AccordionTrigger className="text-left">
                    <div className="flex items-center gap-2">
                      <SeverityBadge severity={attack.severity} />
                      <span className="font-semibold">{attack.name}</span>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-3 pl-4">
                      <div>
                        <p className="text-sm font-semibold">MITRE ATT&CK:</p>
                        <p className="text-sm text-gray-600">{attack.mitre_technique}</p>
                      </div>
                      <div className="flex gap-4">
                        <div>
                          <p className="text-sm font-semibold">Detection:</p>
                          <p className="text-sm text-gray-600">{attack.detection_difficulty}</p>
                        </div>
                        <div>
                          <p className="text-sm font-semibold">Likelihood:</p>
                          <p className="text-sm text-gray-600">{attack.likelihood}</p>
                        </div>
                      </div>
                      <div>
                        <p className="text-sm font-semibold">Prerequisites:</p>
                        <p className="text-sm text-gray-600">{attack.prerequisites}</p>
                      </div>
                      <div>
                        <p className="text-sm font-semibold">Attack Chain:</p>
                        <ol className="list-decimal list-inside text-sm text-gray-600 space-y-1">
                          {attack.attack_chain.map((step, idx) => (
                            <li key={idx}>{step}</li>
                          ))}
                        </ol>
                      </div>
                      <div>
                        <p className="text-sm font-semibold">Expected Impact:</p>
                        <p className="text-sm text-gray-600">{attack.expected_impact}</p>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </div>
        );

      case 'policy':
        const policy = analysisResult.policy;
        if (!policy) {
          return <p className="text-gray-600">Policy validation was skipped.</p>;
        }
        return (
          <div className="space-y-4">
            <div className="text-center p-4 glass-card">
              <p className="text-2xl font-bold">
                {policy.status === 'passed' ? '✅ PASSED' : '❌ FAILED'}
              </p>
              <p className="text-sm text-gray-600 mt-2">{policy.summary}</p>
            </div>

            {policy.violations.length > 0 && (
              <div>
                <h3 className="font-semibold mb-2 text-red-600">Violations</h3>
                <div className="space-y-2">
                  {policy.violations.map((v, idx) => (
                    <div key={idx} className="border-2 border-red-200 bg-red-50 p-3 rounded-xl">
                      <p className="font-semibold text-sm">[{v.rule}] {v.severity.toUpperCase()}</p>
                      <p className="text-sm text-gray-600 mt-1">{v.message}</p>
                      <p className="text-sm mt-1"><strong>Fix:</strong> {v.recommendation}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {policy.recommendations.length > 0 && (
              <div>
                <h3 className="font-semibold mb-2 text-yellow-600">Recommendations</h3>
                <div className="space-y-2">
                  {policy.recommendations.map((r, idx) => (
                    <div key={idx} className="border-2 border-yellow-200 bg-yellow-50 p-3 rounded-xl">
                      <p className="font-semibold text-sm">[{r.rule}] {r.severity.toUpperCase()}</p>
                      <p className="text-sm text-gray-600 mt-1">{r.message}</p>
                      <p className="text-sm mt-1"><strong>Recommendation:</strong> {r.recommendation}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        );

      case 'report':
        const report = analysisResult.security?.report || '';
        return (
          <div className="space-y-4">
            <Button
              variant="gradient"
              className="w-full"
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
            <div className="prose prose-sm prose-slate max-w-none prose-headings:font-bold prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg prose-p:text-gray-700 prose-strong:text-gray-900 prose-ul:list-disc prose-ol:list-decimal prose-table:border-collapse prose-th:border prose-th:border-gray-300 prose-th:bg-gray-100 prose-th:p-2 prose-td:border prose-td:border-gray-300 prose-td:p-2">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full max-w-4xl"
    >
      <h2 className="text-2xl font-bold mb-4">Analysis Details</h2>
      
      {/* Tabs */}
      <div className="grid grid-cols-4 gap-2 mb-6">
        {TABS.map((tab, index) => {
          const Icon = tab.icon;
          const isSelected = selectedTab === tab.id;

          return (
            <motion.button
              key={tab.id}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.05 * index }}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => setSelectedTab(tab.id)}
              className={`bg-white border-2 rounded-lg px-3 py-2 transition-all flex items-center gap-2 ${
                isSelected
                  ? 'border-gray-900 shadow-md'
                  : 'border-gray-200 hover:shadow-md hover:border-gray-400'
              }`}
            >
              <Icon className={`w-4 h-4 flex-shrink-0 ${isSelected ? 'text-gray-900' : 'text-gray-600'}`} />
              <span className="text-xs font-bold text-gray-900 truncate">{tab.title}</span>
            </motion.button>
          );
        })}
      </div>

      {/* Content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={selectedTab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.2 }}
          className="bg-white border-2 border-gray-200 rounded-2xl p-6 h-[calc(100vh-420px)] overflow-y-auto"
        >
          {renderContent()}
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
}
