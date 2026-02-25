import { useCallback, useState } from 'react';
import { Upload, Check } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '@/store/app';
import { Button } from './ui/button';
import { Checkbox } from './ui/checkbox';

const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20MB
const ALLOWED_TYPES = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg'];

interface UploadCardProps {
  onStartAnalysis?: () => void;
}

export function UploadCard({ onStartAnalysis }: UploadCardProps) {
  const [dragActive, setDragActive] = useState(false);
  const { uploadedFile, skipPolicy, setUploadedFile, setSkipPolicy, analysisState } = useAppStore();

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const validateFile = (file: File): string | null => {
    if (!ALLOWED_TYPES.includes(file.type)) {
      return 'Only PDF, PNG, and JPG files are supported';
    }
    if (file.size > MAX_FILE_SIZE) {
      return 'File size must be less than 20MB';
    }
    return null;
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const file = e.dataTransfer.files?.[0];
    if (file) {
      const error = validateFile(file);
      if (error) {
        alert(error);
        return;
      }
      setUploadedFile(file);
    }
  }, [setUploadedFile]);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const error = validateFile(file);
      if (error) {
        alert(error);
        return;
      }
      setUploadedFile(file);
    }
  }, [setUploadedFile]);

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  // Compact mode when analyzing or completed - completely hide when completed
  const isCompact = analysisState === 'analyzing' || analysisState === 'completed';
  const shouldHide = analysisState === 'completed';

  if (shouldHide) {
    return null;
  }

  return (
    <AnimatePresence mode="wait">
      <motion.div
        layout
        initial={{ opacity: 0, y: 20 }}
        animate={{ 
          opacity: 1, 
          y: 0,
          scale: isCompact ? 0.9 : 1,
          height: isCompact ? 'auto' : undefined,
        }}
        exit={{ opacity: 0, y: -20 }}
        transition={{ duration: 0.5, type: 'spring' }}
        className={`bg-white border-2 border-gray-200 rounded-2xl p-8 w-full transition-all shadow-sm ${
          isCompact ? 'max-w-4xl' : 'max-w-2xl'
        }`}
      >
        {!isCompact ? (
          <div className="space-y-6">
            <div
              className={`relative border-2 border-dashed rounded-2xl p-12 text-center transition-all ${
                dragActive
                  ? 'border-gray-900 bg-gray-50 scale-[1.02]'
                  : 'border-gray-300 hover:border-gray-500'
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <input
                type="file"
                id="file-upload"
                className="hidden"
                accept=".pdf,.png,.jpg,.jpeg"
                onChange={handleFileChange}
              />
              
              <label htmlFor="file-upload" className="cursor-pointer block">
                <div className="space-y-4">
                  <div className="text-6xl">
                    {uploadedFile ? <Check className="w-16 h-16 mx-auto text-green-500" /> : <Upload className="w-16 h-16 mx-auto text-gray-400" />}
                  </div>
                  
                  {uploadedFile ? (
                    <div className="space-y-2">
                      <p className="text-lg font-semibold">{uploadedFile.name}</p>
                      <p className="text-sm text-muted-foreground">{formatFileSize(uploadedFile.size)}</p>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={(e) => {
                          e.preventDefault();
                          setUploadedFile(null);
                        }}
                      >
                        Change File
                      </Button>
                    </div>
                  ) : (
                    <div>
                      <p className="text-lg font-medium">Drag & Drop or Click to Upload</p>
                      <p className="text-sm text-muted-foreground mt-2">PDF, PNG, JPG · Max 20MB</p>
                    </div>
                  )}
                </div>
              </label>
            </div>

            <div className="flex items-center space-x-2">
              <Checkbox
                id="skip-policy"
                checked={skipPolicy}
                onCheckedChange={(checked) => setSkipPolicy(checked as boolean)}
              />
              <label
                htmlFor="skip-policy"
                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
              >
                Skip Policy Validation
              </label>
            </div>

            <Button
              variant="gradient"
              size="lg"
              className="w-full text-lg font-semibold"
              disabled={!uploadedFile || analysisState === 'analyzing'}
              onClick={onStartAnalysis}
            >
              {analysisState === 'analyzing' ? 'Analyzing...' : '▶ Start Analysis'}
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-4">
            <Check className="w-8 h-8 text-green-500" />
            <div>
              <p className="font-semibold">{uploadedFile?.name}</p>
              <p className="text-xs text-muted-foreground">{uploadedFile && formatFileSize(uploadedFile.size)}</p>
            </div>
          </div>
        )}
      </motion.div>
    </AnimatePresence>
  );
}
