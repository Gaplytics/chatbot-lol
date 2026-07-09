import React from 'react';

export const SuggestionChips = ({ chips, onSelect }: { chips: string[], onSelect: (text: string) => void }) => {
  return (
    <div className="gaply-suggestion-chips">
      {chips.map((chip, i) => (
        <button key={i} className="gaply-chip" onClick={() => onSelect(chip)}>
          {chip}
        </button>
      ))}
    </div>
  );
};
