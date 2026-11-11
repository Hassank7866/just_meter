import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  maxWidth?: string;
  footer?: React.ReactNode;
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  maxWidth = 'max-w-xl',
  footer,
}) => {
  const [mounted, setMounted] = useState(false);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    setMounted(true);
    return () => setMounted(false);
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCloseRef.current();
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  if (!isOpen || !mounted) return null;

  return createPortal(
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className={`modal-content-box ${maxWidth} animate-fade-in`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Pinned Modal Header */}
        <div className="flex items-center justify-between gap-2 px-3 sm:px-6 py-3 sm:py-4 border-b border-slate-800 bg-slate-900/95 shrink-0 select-none">
          <h3 className="min-w-0 flex-1 text-sm sm:text-base font-bold text-slate-100 flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-sky-400 animate-pulse"></span>
            <span className="break-words">{title}</span>
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-slate-800 transition-colors"
            title="Close dialog (Esc)"
          >
            <X size={18} />
          </button>
        </div>

        {/* Scrollable Modal Body with visible scrollbar */}
        <div className="modal-scrollable-body overscroll-contain">
          {children}
        </div>

        {/* Pinned Modal Footer */}
        {footer && (
          <div className="px-3 sm:px-6 py-3.5 border-t border-slate-800 bg-slate-900/95 shrink-0 flex flex-wrap items-center justify-end gap-2 sm:gap-3 select-none">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body
  );
};
