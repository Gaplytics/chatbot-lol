import React, { useEffect, useRef } from 'react';
import { Room, RoomEvent, Track } from 'livekit-client';

export const AudioPlayer = ({ room }: { room: Room }) => {
  const audioEl = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    const handleTrackSubscribed = (track: any) => {
      if (track.kind === Track.Kind.Audio && audioEl.current) {
        track.attach(audioEl.current);
      }
    };

    room.on(RoomEvent.TrackSubscribed, handleTrackSubscribed);

    // Also attach any already subscribed audio tracks (if joining late)
    room.remoteParticipants.forEach(participant => {
      participant.audioTrackPublications.forEach(pub => {
        if (pub.isSubscribed && pub.track && audioEl.current) {
          pub.track.attach(audioEl.current);
        }
      });
    });

    return () => {
      room.off(RoomEvent.TrackSubscribed, handleTrackSubscribed);
    };
  }, [room]);

  return <audio ref={audioEl} autoPlay style={{ display: 'none' }} />;
};
