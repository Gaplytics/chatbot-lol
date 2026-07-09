import React, { useState } from 'react';
import { Mic, MicOff } from 'lucide-react';
import { Room } from 'livekit-client';

export const VoiceButton = ({ room, isConnected, disabled }: { room: Room | null, isConnected: boolean, disabled?: boolean }) => {
  const [isMicOn, setIsMicOn] = useState(false);

  const toggleMic = async () => {
    if (!room || !isConnected || disabled) return;
    
    try {
      if (isMicOn) {
        await room.localParticipant.setMicrophoneEnabled(false);
        setIsMicOn(false);
      } else {
        await room.localParticipant.setMicrophoneEnabled(true);
        setIsMicOn(true);
      }
    } catch (e) {
      console.error("Failed to toggle mic", e);
    }
  };

  return (
    <button 
      className={`gaply-voice-btn ${isMicOn ? 'active' : ''}`} 
      onClick={toggleMic}
      disabled={!isConnected || disabled}
      title={isMicOn ? "Mute Microphone" : "Voice Input (Speak to Agent)"}
    >
      {isMicOn ? (
        <span className="gaply-mic-active-wrapper">
          <Mic size={18} color="#ffffff" />
          <span className="gaply-mic-pulse-ring"></span>
        </span>
      ) : (
        <Mic size={18} />
      )}
    </button>
  );
};
