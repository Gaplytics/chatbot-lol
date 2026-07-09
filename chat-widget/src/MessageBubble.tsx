import React from 'react';
import ReactMarkdown from 'react-markdown';
import { SuggestionChips } from './SuggestionChips';

export const MessageBubble = ({ 
  text, 
  sender, 
  suggestions, 
  selectedSuggestion,
  isActiveSuggestions,
  onSelectSuggestion
}: { 
  text: string, 
  sender: 'user' | 'bot',
  suggestions?: string[],
  selectedSuggestion?: string,
  isActiveSuggestions?: boolean,
  onSelectSuggestion?: (text: string) => void
}) => {
  const isBot = sender === 'bot';
  
  // If a suggestion was selected, only show that one. Otherwise show all of them.
  const chipsToRender = selectedSuggestion && suggestions 
    ? suggestions.filter(s => s === selectedSuggestion) 
    : suggestions;

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
        {isBot && chipsToRender && chipsToRender.length > 0 && (
          <div className={`gaply-inline-suggestions ${!isActiveSuggestions && !selectedSuggestion ? 'gaply-suggestions-disabled' : ''}`}>
            {isActiveSuggestions && <div className="gaply-mcq-header">Select an option:</div>}
            {!isActiveSuggestions && selectedSuggestion && <div className="gaply-mcq-header">Selected option:</div>}
            <SuggestionChips 
              chips={chipsToRender} 
              onSelect={isActiveSuggestions && onSelectSuggestion ? onSelectSuggestion : () => {}} 
              disabled={!isActiveSuggestions}
            />
          </div>
        )}
      </div>
    </div>
  );
};
