import React from 'react';
import ReactMarkdown from 'react-markdown';
import { SuggestionChips } from './SuggestionChips';

export const MessageBubble = ({ 
  text, 
  sender, 
  suggestions, 
  isActiveSuggestions,
  onSelectSuggestion
}: { 
  text: string, 
  sender: 'user' | 'bot',
  suggestions?: string[],
  isActiveSuggestions?: boolean,
  onSelectSuggestion?: (text: string) => void
}) => {
  const isBot = sender === 'bot';
  return (
    <div className={`gaply-message-wrapper ${isBot ? 'gaply-message-bot' : 'gaply-message-user'}`}>
      <div className="gaply-message-container">
        <div className="gaply-message-bubble">
          {isBot ? (
            <div className="gaply-markdown-body">
              <ReactMarkdown>
                {text}
              </ReactMarkdown>
            </div>
          ) : (
            text
          )}
        </div>
        {isBot && suggestions && suggestions.length > 0 && (
          <div className={`gaply-inline-suggestions ${!isActiveSuggestions ? 'gaply-suggestions-disabled' : ''}`}>
            {isActiveSuggestions && <div className="gaply-mcq-header">Select an option:</div>}
            <SuggestionChips 
              chips={suggestions} 
              onSelect={isActiveSuggestions && onSelectSuggestion ? onSelectSuggestion : () => {}} 
              disabled={!isActiveSuggestions}
            />
          </div>
        )}
      </div>
    </div>
  );
};
