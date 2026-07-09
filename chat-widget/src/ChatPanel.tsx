import React, { useState, useEffect, useRef } from 'react';
import { useLiveKit } from './hooks/useLiveKit';
import { MessageBubble } from './MessageBubble';
import { VoiceButton } from './VoiceButton';
import { AudioPlayer } from './AudioPlayer';
import { Send, Minimize2, Volume2, VolumeX, MessageCircle } from 'lucide-react';

export const ChatPanel = ({ tokenUrl, botName, tenantId, onClose }: any) => {
  const { room, messages, isConnected, isProcessing, sendMessage, sendSettings, selectSuggestion } = useLiveKit(tokenUrl, tenantId);
  const [inputText, setInputText] = useState("");
  
  // Voice output toggle: Determines if bot answers with audio (also sent to backend to avoid unnecessary TTS)
  const [botVoiceOutput, setBotVoiceOutput] = useState(false);
  
  const handleVoiceOutputToggle = (enabled: boolean) => {
    setBotVoiceOutput(enabled);
    sendSettings(enabled); // notify backend — skips Deepgram TTS when off
  };
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isProcessing]);

  const handleSend = () => {
    if (inputText.trim() && !isProcessing) {
      sendMessage(inputText.trim(), botVoiceOutput);
      setInputText("");
    }
  };

  return (
    <div className="gaply-chat-panel">
      {/* 1. Header Area */}
      <div className="gaply-panel-header">
        <div className="gaply-header-info">
          <div className="gaply-bot-avatar">
            <MessageCircle size={18} />
          </div>
          <div>
            <h3>{botName}</h3>
            <span className="gaply-status-text">
              <span className={`gaply-status-dot ${isConnected ? 'connected' : ''}`}></span>
              {isConnected ? 'Online' : 'Connecting...'}
            </span>
            <span style={{ marginLeft: "8px", fontSize: "10px", background: "#ff4757", color: "white", padding: "2px 6px", borderRadius: "10px" }}>
              TENANT: {tenantId}
            </span>
          </div>
        </div>
        <div className="gaply-header-actions">
          <button onClick={onClose} className="gaply-close-btn" title="Minimize Chat">
            <Minimize2 size={16} />
          </button>
        </div>
      </div>

      {/* 2. Interactive Settings Sub-Bar */}
      <div className="gaply-control-bar">
        <div className="gaply-control-label-wrapper">
          {botVoiceOutput ? <Volume2 size={16} /> : <VolumeX size={16} />}
          <span className="gaply-control-label">Bot Voice Output</span>
        </div>
        <div className="gaply-voice-toggle-container">
          <label className="gaply-switch" title={botVoiceOutput ? "Click to mute bot speaking" : "Click to let bot speak answers"}>
            <input 
              type="checkbox" 
              checked={botVoiceOutput} 
              onChange={(e) => handleVoiceOutputToggle(e.target.checked)} 
              disabled={!isConnected || isProcessing}
            />
            <span className="gaply-slider"></span>
          </label>
          <span className="gaply-control-status">{botVoiceOutput ? "ON" : "OFF"}</span>
        </div>
      </div>

      {/* 3. Messages List Area */}
      <div className="gaply-messages">
        {messages.map((m, i) => {
          // A bot message's suggestions are active if it's the very last message in the array
          const isActive = m.sender === 'bot' && i === messages.length - 1;
          
          return (
            <MessageBubble 
              key={m.id || i} 
              text={m.text} 
              sender={m.sender} 
              suggestions={m.suggestions}
              selectedSuggestion={m.selectedSuggestion}
              isActiveSuggestions={isActive}
              onSelectSuggestion={(text) => selectSuggestion(m.id || `msg-${i}`, text, botVoiceOutput)}
            />
          );
        })}
        {isProcessing && (
          <div className="gaply-message-wrapper gaply-message-bot">
             <div className="gaply-typing-indicator">
               <span></span><span></span><span></span>
             </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 4. Bottom Input and Voice Trigger Panel */}
      <div className="gaply-input-container">
        <div className="gaply-input-area">
          <input 
            value={inputText} 
            onChange={e => setInputText(e.target.value)} 
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            placeholder={isProcessing ? "Thinking..." : "Type your message..."}
            disabled={!isConnected || isProcessing}
          />
          <button 
            onClick={handleSend} 
            disabled={!isConnected || isProcessing || !inputText.trim()} 
            className="gaply-send-btn"
            title="Send Message"
          >
            <Send size={16} />
          </button>
          
          <div className="gaply-divider-line"></div>
          
          {/* Voice Input Trigger */}
          <VoiceButton room={room} isConnected={isConnected} disabled={isProcessing} />
        </div>
      </div>
      
      {room && <AudioPlayer room={room} isMuted={!botVoiceOutput} />}
    </div>
  );
};
