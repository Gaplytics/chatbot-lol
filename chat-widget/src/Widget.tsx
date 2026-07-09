import React, { useState } from 'react';
import { ChatPanel } from './ChatPanel';
import { MessageCircle, X } from 'lucide-react';

export const Widget = ({ tokenUrl, botName, theme, tenantId }: { tokenUrl: string, botName: string, theme: string, tenantId: string }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [hasOpened, setHasOpened] = useState(false);

  const handleToggle = () => {
    setIsOpen(!isOpen);
    if (!hasOpened) {
      setHasOpened(true);
    }
  };

  return (
    <div className={`gaply-widget gaply-theme-${theme}`}>
      {hasOpened && (
        <div className="gaply-panel-container" style={{ display: isOpen ? 'flex' : 'none' }}>
          <ChatPanel tokenUrl={tokenUrl} botName={botName} tenantId={tenantId} onClose={() => setIsOpen(false)} />
        </div>
      )}
      
      <button 
        className="gaply-fab" 
        onClick={handleToggle}
        aria-label="Toggle Chat"
      >
        {isOpen ? <X size={24} /> : <MessageCircle size={24} />}
      </button>
    </div>
  );
};
