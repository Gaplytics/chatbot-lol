import React, { useState, useEffect, useRef } from 'react';
import { useLiveKit } from './hooks/useLiveKit';
import { MessageBubble } from './MessageBubble';
import { SuggestionChips } from './SuggestionChips';
import { VoiceButton } from './VoiceButton';
import { AudioPlayer } from './AudioPlayer';

export const ChatPanel = ({ tokenUrl, botName, onClose }: any) => {
  const { room, messages, suggestions, isConnected, isProcessing, sendMessage } = useLiveKit(tokenUrl);
  const [inputText, setInputText] = useState("");
  // Voice response toggle: when ON, typed messages also trigger TTS
  const [voiceResponse, setVoiceResponse] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isProcessing]);

  const handleSend = () => {
    if (inputText.trim() && !isProcessing) {
      sendMessage(inputText.trim(), voiceResponse);
      setInputText("");
    }
  };

  return (
    <div className="gaply-chat-panel">
      <div className="gaply-header">
        <div className="gaply-header-info">
          <div className="gaply-avatar">
            <span className="gaply-avatar-initial">{botName.charAt(0)}</span>
          </div>
          <div className="gaply-header-text">
            <h3>{botName}</h3>
            <span className="gaply-status">
              <span className={`gaply-status-dot ${isConnected ? 'connected' : ''}`}></span>
              {isConnected ? 'Online' : 'Connecting...'}
            </span>
          </div>
        </div>
        <button onClick={onClose} className="gaply-close-btn">&times;</button>
      </div>
      <div className="gaply-messages">
        {messages.map((m, i) => (
          <MessageBubble key={m.id || i} text={m.text} sender={m.sender} />
        ))}
        {isProcessing && (
          <div className="gaply-message-wrapper gaply-message-bot">
             <div className="gaply-message-bubble gaply-typing-indicator">
               <span></span><span></span><span></span>
             </div>
          </div>
        )}
        {!isProcessing && suggestions.length > 0 && (
          <SuggestionChips chips={suggestions} onSelect={(text) => sendMessage(text, voiceResponse)} />
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className="gaply-input-area">
        <input 
          value={inputText} 
          onChange={e => setInputText(e.target.value)} 
          onKeyDown={e => e.key === 'Enter' && handleSend()}
          placeholder={isProcessing ? "AI is processing..." : "Type your message..."}
          disabled={!isConnected || isProcessing}
        />
        <button 
          onClick={handleSend} 
          disabled={!isConnected || isProcessing || !inputText.trim()} 
          className="gaply-send-btn"
        >
          Send
        </button>
        {/* Voice-response toggle: controls whether text replies also use TTS */}
        <button
          className={`gaply-tts-toggle-btn ${voiceResponse ? 'active' : ''}`}
          onClick={() => setVoiceResponse(v => !v)}
          disabled={!isConnected || isProcessing}
          title={voiceResponse ? "Voice response ON – click to disable" : "Voice response OFF – click to enable"}
        >
          {voiceResponse ? '🔊' : '🔇'}
        </button>
        {/* Mic button: toggles the user's microphone for voice input */}
        <VoiceButton room={room} isConnected={isConnected} disabled={isProcessing} />
      </div>
      {room && <AudioPlayer room={room} />}
    </div>
  );
};
