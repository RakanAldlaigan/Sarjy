
let current: HTMLAudioElement | null = null;

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
