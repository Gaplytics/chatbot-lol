import { useState, useEffect, useCallback, useRef } from 'react';
import { Room, RoomEvent } from 'livekit-client';

export function useLiveKit(tokenUrl: string) {
  const [room, setRoom] = useState<Room | null>(null);
  const [messages, setMessages] = useState<any[]>([]);
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
              // Find the last bot message and attach suggestions to it
              const msgs = [...messagesRef.current];
              for (let i = msgs.length - 1; i >= 0; i--) {
                if (msgs[i].sender === 'bot') {
                  msgs[i] = { ...msgs[i], suggestions: parsed.data };
                  updateMessages(msgs);
                  break;
                }
              }
            } else if (parsed.type === 'website_control') {
              // Dispatch generic gaply_action event for host website to handle
              window.dispatchEvent(new CustomEvent('gaply_action', { 
                detail: { action: parsed.action, payload: parsed.payload } 
              }));

              // Basic fallback for navigation if host website isn't intercepting it
              if (parsed.action === 'navigate' && parsed.payload?.url) {
                console.log(`Gaply Agent navigating to: ${parsed.payload.url}`);
                // In a production app you might want to remove this fallback if you rely on React Router
                window.location.href = parsed.payload.url;
              } else if (parsed.action === 'highlight' && parsed.payload?.selector) {
                const el = document.querySelector(parsed.payload.selector);
                if (el) {
                  // A simple CSS highlight effect
                  el.setAttribute('style', 'outline: 3px solid red; transition: outline 0.5s;');
                  setTimeout(() => {
                    el.removeAttribute('style');
                  }, 3000);
                }
              }
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
      
      const payload = new TextEncoder().encode(JSON.stringify({
        type: 'chat',
        text,
        voiceResponse,
      }));
      await room.localParticipant.publishData(payload, { reliable: true });
    }
  }, [room, isConnected]);

  /** Sends a settings update to the agent backend. */
  const sendSettings = useCallback(async (voiceOutputEnabled: boolean) => {
    if (room && isConnected) {
      const payload = new TextEncoder().encode(JSON.stringify({
        type: 'settings',
        voiceOutputEnabled,
      }));
      await room.localParticipant.publishData(payload, { reliable: true });
    }
  }, [room, isConnected]);

  return { room, messages, isConnected, isProcessing, sendMessage, sendSettings };
}
