import React, { useState } from 'react';
import { ChatPanel } from './ChatPanel';
import { MessageCircle, X } from 'lucide-react';

export const Widget = ({ tokenUrl, botName, theme }: { tokenUrl: string, botName: string, theme: string }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className={`gaply-widget gaply-theme-${theme}`}>
      {isOpen && (
        <div className="gaply-panel-container">
          <ChatPanel tokenUrl={tokenUrl} botName={botName} onClose={() => setIsOpen(false)} />
        </div>
      )}
      
      <button 
        className="gaply-fab" 
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Toggle Chat"
      >
        {isOpen ? <X size={24} /> : <MessageCircle size={24} />}
      </button>
    </div>
  );
};
