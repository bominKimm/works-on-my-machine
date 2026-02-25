import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from './ui/accordion';
import { useAppStore } from '@/store/app';
import { Button } from './ui/button';
import { Download } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

type ModalType = 'vulnerabilities' | 'attacks' | 'policy' | 'report' | null;

interface DetailModalProps {
  type: ModalType;
  open: boolean;
  onClose: () => void;
}

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

export function DetailModal({ type, open, onClose }: DetailModalProps) {
  const { analysisResult } = useAppStore();

  if (!type || !analysisResult) {
    return null;
  }

  const renderContent = () => {
    switch (type) {
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
                      <span>- {vuln.title}</span>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-3 pl-4">
                      <div>
                        <p className="text-sm font-semibold">Category:</p>
                        <p className="text-sm text-muted-foreground">{vuln.category}</p>
                      </div>
                      <div>
                        <p className="text-sm font-semibold">Affected Resource:</p>
                        <code className="text-sm bg-gray-100 px-2 py-1 rounded">{vuln.affected_resource}</code>
                      </div>
                      <div>
                        <p className="text-sm font-semibold">Description:</p>
                        <p className="text-sm text-muted-foreground">{vuln.description}</p>
                      </div>
                      <div>
                        <p className="text-sm font-semibold">Remediation:</p>
                        <p className="text-sm text-muted-foreground">{vuln.remediation}</p>
                      </div>
                      {vuln.benchmark_ref && (
                        <div>
                          <p className="text-sm font-semibold">Benchmark:</p>
                          <p className="text-sm text-muted-foreground">{vuln.benchmark_ref}</p>
                        </div>
                      )}
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
              {attacks.map((attack) => (
                <AccordionItem key={attack.id} value={attack.id}>
                  <AccordionTrigger className="text-left">
                    <div className="flex items-center gap-2">
                      <SeverityBadge severity={attack.severity} />
                      <span className="font-semibold">{attack.id}</span>
                      <span>- {attack.name}</span>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-3 pl-4">
                      <div>
                        <p className="text-sm font-semibold">MITRE ATT&CK:</p>
                        <p className="text-sm text-muted-foreground">{attack.mitre_technique}</p>
                      </div>
                      <div className="flex gap-4">
                        <div>
                          <p className="text-sm font-semibold">Detection:</p>
                          <p className="text-sm text-muted-foreground">{attack.detection_difficulty}</p>
                        </div>
                        <div>
                          <p className="text-sm font-semibold">Likelihood:</p>
                          <p className="text-sm text-muted-foreground">{attack.likelihood}</p>
                        </div>
                      </div>
                      <div>
                        <p className="text-sm font-semibold">Prerequisites:</p>
                        <p className="text-sm text-muted-foreground">{attack.prerequisites}</p>
                      </div>
                      <div>
                        <p className="text-sm font-semibold">Attack Chain:</p>
                        <ol className="list-decimal list-inside text-sm text-muted-foreground space-y-1">
                          {attack.attack_chain.map((step, idx) => (
                            <li key={idx}>{step}</li>
                          ))}
                        </ol>
                      </div>
                      <div>
                        <p className="text-sm font-semibold">Expected Impact:</p>
                        <p className="text-sm text-muted-foreground">{attack.expected_impact}</p>
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
          return <p className="text-muted-foreground">Policy validation was skipped.</p>;
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
                    <div key={idx} className="border border-red-200 bg-red-50 p-3 rounded">
                      <p className="font-semibold text-sm">[{v.rule}] {v.severity.toUpperCase()}</p>
                      <p className="text-sm text-muted-foreground mt-1">{v.message}</p>
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
                    <div key={idx} className="border border-yellow-200 bg-yellow-50 p-3 rounded">
                      <p className="font-semibold text-sm">[{r.rule}] {r.severity.toUpperCase()}</p>
                      <p className="text-sm text-muted-foreground mt-1">{r.message}</p>
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

  const titles: Record<string, string> = {
    vulnerabilities: '🔴 Vulnerabilities',
    attacks: '⚡ Attack Scenarios',
    policy: '🛡️ Policy Validation',
    report: '📊 Security Report',
  };

  return (
    <Dialog open={open} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{titles[type]}</DialogTitle>
        </DialogHeader>
        <div className="mt-4 max-h-[60vh] overflow-y-auto">
          {renderContent()}
        </div>
      </DialogContent>
    </Dialog>
  );
}
