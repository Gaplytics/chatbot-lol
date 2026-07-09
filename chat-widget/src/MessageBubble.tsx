import React from 'react';

export const MessageBubble = ({ text, sender }: { text: string, sender: 'user' | 'bot' }) => {
  const isBot = sender === 'bot';
  return (
    <div className={`gaply-message-wrapper ${isBot ? 'gaply-message-bot' : 'gaply-message-user'}`}>
      <div className="gaply-message-bubble">
        {text}
      </div>
    </div>
  );
};
