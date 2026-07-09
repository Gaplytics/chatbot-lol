import { useState, useEffect, useCallback, useRef } from 'react';
import { Room, RoomEvent } from 'livekit-client';

export function useLiveKit(tokenUrl: string) {
  const [room, setRoom] = useState<Room | null>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  // We use a ref to track messages so we can update them safely within event listeners
  // without dealing with stale closures
  const messagesRef = useRef<any[]>([]);
  
  const updateMessages = (newMsgs: any[]) => {
    messagesRef.current = newMsgs;
    setMessages(newMsgs);
  };

  useEffect(() => {
    let activeRoom: Room | null = null;
    
    async function connect() {
      try {
        const resp = await fetch(tokenUrl, { 
          method: 'POST', 
          body: JSON.stringify({ participant_name: "User" }), 
          headers: { 'Content-Type': 'application/json' }
        });
        const data = await resp.json();
        
        activeRoom = new Room({ adaptiveStream: true, dynacast: true });
        
        // Listen for data channel messages from the agent
        activeRoom.on(RoomEvent.DataReceived, (payload) => {
          const strData = new TextDecoder().decode(payload);
          try {
            const parsed = JSON.parse(strData);
            if (parsed.type === 'suggestions') {
              setSuggestions(parsed.data);
            } else if (parsed.type === 'text_stream') {
              // Handle real-time text streaming
              const { id, text, final } = parsed;
              
              const msgs = [...messagesRef.current];
              const existingIdx = msgs.findIndex(m => m.id === id);
              
              if (existingIdx >= 0) {
                // Append text to existing stream message
                msgs[existingIdx] = { 
                  ...msgs[existingIdx], 
                  text: msgs[existingIdx].text + text,
                  final: final
                };
              } else if (text) {
                // New stream message
                msgs.push({ id, text, sender: 'bot', final });
              }
              
              updateMessages(msgs);
              
              if (final) {
                setIsProcessing(false);
              }
            } else if (parsed.type === 'text_reply') {
              // Legacy non-streaming reply
              updateMessages([...messagesRef.current, { text: parsed.text, sender: 'bot', final: true }]);
              setIsProcessing(false);
            }
          } catch (e) {
            // Raw string fallback
            if (strData.trim()) {
              updateMessages([...messagesRef.current, { text: strData, sender: 'bot', final: true }]);
              setIsProcessing(false);
            }
          }
        });

        // Voice transcriptions (agent TTS or user mic speech)
        activeRoom.on(RoomEvent.TranscriptionReceived, (segments, participant) => {
          const msgs = [...messagesRef.current];
          const sender = participant?.identity?.includes('agent') ? 'bot' : 'user';
          
          let hasFinalAgentMessage = false;

          segments.forEach(t => {
            const existingIdx = msgs.findIndex(m => m.id === t.id);
            if (existingIdx >= 0) {
              msgs[existingIdx] = { ...msgs[existingIdx], text: t.text, final: t.final };
            } else {
              msgs.push({ id: t.id, text: t.text, sender, final: t.final });
            }
            
            if (sender === 'bot' && t.final) {
              hasFinalAgentMessage = true;
            }
          });
          
          updateMessages(msgs);
          
          if (hasFinalAgentMessage) {
             setIsProcessing(false);
          }
        });

        await activeRoom.connect(data.livekit_url, data.token);
        setIsConnected(true);
        setRoom(activeRoom);
      } catch (err) {
        console.error("LiveKit connection error", err);
      }
    }
    
    connect();
    
    return () => {
      activeRoom?.disconnect();
    };
  }, [tokenUrl]);

  /**
   * Send a text message to the agent.
   * @param text       The message text.
   * @param voiceResponse  If true, the agent will also speak the reply via TTS.
   *                       If false (default), the agent replies with text only.
   */
  const sendMessage = useCallback(async (text: string, voiceResponse: boolean = false) => {
    if (room && isConnected) {
      // Create a temporary local message
      const localId = 'local-' + Date.now();
      updateMessages([...messagesRef.current, { id: localId, text, sender: 'user', final: true }]);
      setIsProcessing(true);
      setSuggestions([]);
      
      const payload = new TextEncoder().encode(JSON.stringify({
        type: 'chat',
        text,
        voiceResponse,
      }));
      await room.localParticipant.publishData(payload, { reliable: true });
    }
  }, [room, isConnected]);

  return { room, messages, suggestions, isConnected, isProcessing, sendMessage };
}
