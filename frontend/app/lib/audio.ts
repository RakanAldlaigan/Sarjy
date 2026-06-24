// Single shared player so audio from any source (voice response, confirmation
// card) never overlaps — starting new audio stops whatever is currently playing.

let current: HTMLAudioElement | null = null;

/** Plays base64-encoded mp3, stopping any audio already playing first. Playback
 *  rejections (e.g. the browser's autoplay policy) are logged, not thrown.
 *  `onPlaying` (optional) fires on the element's `playing` event — the true
 *  moment audio actually starts (used for latency timing; unset => no listener). */
export async function playAudio(base64: string, onPlaying?: () => void): Promise<void> {
  stopAudio();
  const audio = new Audio(`data:audio/mpeg;base64,${base64}`);
  current = audio;
  if (onPlaying) audio.addEventListener("playing", onPlaying, { once: true });
  try {
    await audio.play();
  } catch (err) {
    console.warn("Audio playback failed", err);
  }
}

export function stopAudio(): void {
  if (current) {
    current.pause();
    current.currentTime = 0;
    current = null;
  }
}
