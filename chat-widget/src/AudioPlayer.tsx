import React, { useEffect, useRef } from 'react';
import { Room, RoomEvent, Track } from 'livekit-client';

export const AudioPlayer = ({ room, isMuted = false }: { room: Room, isMuted?: boolean }) => {
  const audioEl = useRef<HTMLAudioElement>(null);
  // Use a ref so the track-subscribe handler always sees the current muted value
  // (avoids stale closure where isMuted is captured at effect-setup time)
  const isMutedRef = useRef(isMuted);

  // Sync ref and DOM element whenever the prop changes
  useEffect(() => {
    isMutedRef.current = isMuted;
    if (audioEl.current) {
      audioEl.current.muted = isMuted;
    }
  }, [isMuted]);

  useEffect(() => {
    const applyMuted = () => {
      if (audioEl.current) {
        audioEl.current.muted = isMutedRef.current;
      }
    };

    const handleTrackSubscribed = (track: any) => {
      if (track.kind === Track.Kind.Audio && audioEl.current) {
        track.attach(audioEl.current);
        // Re-apply after attach — attaching resets the muted property
        applyMuted();
      }
    };

    room.on(RoomEvent.TrackSubscribed, handleTrackSubscribed);

    // Also attach already-subscribed tracks (joining late)
    room.remoteParticipants.forEach(participant => {
      participant.audioTrackPublications.forEach(pub => {
        if (pub.isSubscribed && pub.track && audioEl.current) {
          pub.track.attach(audioEl.current);
          applyMuted();
        }
      });
    });

    return () => {
      room.off(RoomEvent.TrackSubscribed, handleTrackSubscribed);
    };
  }, [room]);

  // Note: React's `muted` prop on <audio> is broken — always set via ref/useEffect above
  return <audio ref={audioEl} autoPlay style={{ display: 'none' }} />;
};
