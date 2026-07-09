import React from 'react';

export const SuggestionChips = ({ 
  chips, 
  onSelect,
  disabled = false
}: { 
  chips: string[], 
  onSelect: (text: string) => void,
  disabled?: boolean
}) => {
  const prefixes = ['A', 'B', 'C', 'D', 'E', 'F'];
  
  return (
    <div className="gaply-mcq-options">
      {chips.map((chip, i) => {
        const prefix = prefixes[i % prefixes.length];
        return (
          <button 
            key={i} 
            className={`gaply-mcq-option-card ${disabled ? 'gaply-mcq-disabled' : ''}`}
            onClick={() => !disabled && onSelect(chip)}
            disabled={disabled}
          >
            <span className="gaply-mcq-badge">{prefix}</span>
            <span className="gaply-mcq-text">{chip}</span>
          </button>
        );
      })}
    </div>
  );
};
