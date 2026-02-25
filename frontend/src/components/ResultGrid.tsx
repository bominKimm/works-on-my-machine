import { motion } from 'framer-motion';
import { AlertTriangle, Shield, FileText, Zap } from 'lucide-react';
import { useAppStore } from '@/store/app';
import { useState } from 'react';
import { DetailModal } from './DetailModal';

type CardType = 'vulnerabilities' | 'attacks' | 'policy' | 'report';

const CARDS = [
  {
    id: 'vulnerabilities' as CardType,
    icon: AlertTriangle,
    title: 'Vulnerabilities',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
    iconColor: 'text-red-600',
    accentColor: 'text-red-600',
    emoji: '🔴',
  },
  {
    id: 'attacks' as CardType,
    icon: Zap,
    title: 'Attack Scenarios',
    bgColor: 'bg-orange-50',
    borderColor: 'border-orange-200',
    iconColor: 'text-orange-600',
    accentColor: 'text-orange-600',
    emoji: '⚡',
  },
  {
    id: 'policy' as CardType,
    icon: Shield,
    title: 'Policy Check',
    bgColor: 'bg-purple-50',
    borderColor: 'border-purple-200',
    iconColor: 'text-purple-600',
    accentColor: 'text-purple-600',
    emoji: '🛡️',
  },
  {
    id: 'report' as CardType,
    icon: FileText,
    title: 'Report',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    iconColor: 'text-blue-600',
    accentColor: 'text-blue-600',
    emoji: '📊',
  },
];

export function ResultGrid() {
  const { analysisResult } = useAppStore();
  const [selectedCard, setSelectedCard] = useState<CardType | null>(null);

  if (!analysisResult?.security) {
    return null;
  }

  const getCardData = (id: CardType) => {
    const { security, policy } = analysisResult;
    
    switch (id) {
      case 'vulnerabilities':
        return {
          count: security?.vulnerabilities.length || 0,
          subtitle: 'vulnerabilities found',
        };
      case 'attacks':
        return {
          count: security?.attack_scenarios.length || 0,
          subtitle: 'attack scenarios',
        };
      case 'policy':
        return {
          count: policy?.violations.length || 0,
          subtitle: policy?.status === 'passed' ? 'PASSED ✅' : 'violations found',
        };
      case 'report':
        return {
          count: '📄',
          subtitle: 'Download report',
        };
    }
  };

  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full max-w-4xl"
      >
        {CARDS.map((card, index) => {
          const data = getCardData(card.id);
          const Icon = card.icon;

          return (
            <motion.button
              key={card.id}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.1 * index }}
              whileHover={{ scale: 1.02, y: -4 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => setSelectedCard(card.id)}
              className={`${card.bgColor} border-2 ${card.borderColor} rounded-2xl p-6 text-left group cursor-pointer transition-all hover:shadow-lg`}
            >
              <div className="flex items-start justify-between mb-4">
                <div className={`p-2 rounded-lg ${card.bgColor} border ${card.borderColor}`}>
                  <Icon className={`w-6 h-6 ${card.iconColor}`} />
                </div>
                <span className="text-2xl">{card.emoji}</span>
              </div>

              <h3 className="text-lg font-bold mb-1 text-gray-900">{card.title}</h3>
              
              <div className="flex items-baseline gap-2 mb-3">
                <span className={`text-3xl font-bold ${card.accentColor}`}>
                  {data.count}
                </span>
                <span className="text-sm text-gray-600">{data.subtitle}</span>
              </div>

              <div className={`text-sm font-medium ${card.accentColor} flex items-center gap-1`}>
                View Details
                <span className="transition-transform group-hover:translate-x-1">→</span>
              </div>
            </motion.button>
          );
        })}
      </motion.div>

      <DetailModal
        type={selectedCard}
        open={selectedCard !== null}
        onClose={() => setSelectedCard(null)}
      />
    </>
  );
}
