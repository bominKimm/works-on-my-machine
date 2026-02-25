import { motion, AnimatePresence } from 'framer-motion';
import { X, Send, Loader2 } from 'lucide-react';
import { useAppStore } from '@/store/app';
import { Button } from './ui/button';
import { useState, useRef, useEffect } from 'react';
import { chatWithAI } from '@/services/api';
import type { ChatMessage } from '@/types/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ChatPanelProps {
  open: boolean;
  onClose: () => void;
}

export function ChatPanel({ open, onClose }: ChatPanelProps) {
  const { analysisResult, chatHistory, addChatMessage } = useAppStore();
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatHistory]);

  const handleSend = async () => {
    if (!input.trim() || isLoading || !analysisResult) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: input.trim(),
    };

    addChatMessage(userMessage);
    setInput('');
    setIsLoading(true);

    try {
      const response = await chatWithAI({
        question: userMessage.content,
        context: {
          security: analysisResult.security,
          policy: analysisResult.policy,
        },
        history: chatHistory,
      });

      if (response.status === 'success' && response.answer) {
        addChatMessage({
          role: 'assistant',
          content: response.answer,
        });
      } else {
        addChatMessage({
          role: 'assistant',
          content: 'Sorry, I couldn\'t process your request. Please try again.',
        });
      }
    } catch (error) {
      console.error('Chat error:', error);
      addChatMessage({
        role: 'assistant',
        content: 'An error occurred while processing your request.',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!open) return null;

  return (
    <motion.div
      initial={{ x: '100%' }}
      animate={{ x: 0 }}
      exit={{ x: '100%' }}
      transition={{ type: 'spring', damping: 25, stiffness: 200 }}
      className="w-full md:w-[400px] lg:w-[500px] bg-white border-2 border-gray-200 rounded-2xl flex flex-col h-[calc(100vh-120px)] shadow-lg"
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b">
        <div>
          <h2 className="text-lg font-bold">💬 AI Security Advisor</h2>
          <p className="text-xs text-muted-foreground">Ask questions about the analysis</p>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="w-5 h-5" />
        </Button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {chatHistory.length === 0 ? (
          <div className="text-center py-12 text-gray-600">
            <p className="text-sm mb-2">Ask me about the security analysis</p>
            <p className="text-xs">Example: "What are the critical vulnerabilities?"</p>
          </div>
        ) : (
          chatHistory.map((message, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-2 ${
                  message.role === 'user'
                    ? 'bg-gray-900 text-white'
                    : 'glass-card border'
                }`}
              >
                {message.role === 'user' ? (
                  <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                ) : (
                  <div className="text-sm prose prose-sm prose-slate max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-headings:my-1 prose-strong:text-gray-900 prose-code:text-gray-900 prose-code:bg-gray-200 prose-code:px-1 prose-code:py-0.5 prose-code:rounded">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                  </div>
                )}
              </div>
            </motion.div>
          ))
        )}

        {isLoading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex justify-start"
          >
            <div className="bg-gray-50 border-2 border-gray-200 rounded-2xl px-4 py-2 flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              <p className="text-sm text-gray-600">Thinking...</p>
            </div>
          </motion.div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your question..."
            disabled={isLoading}
            className="flex-1 px-4 py-2 rounded-full bg-gray-50 border-2 border-gray-200 focus:outline-none focus:border-gray-900 text-sm transition-colors"
          />
          <Button
            variant="gradient"
            size="icon"
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="rounded-full"
          >
            <Send className="w-5 h-5" />
          </Button>
        </div>
      </div>
    </motion.div>
  );
}
