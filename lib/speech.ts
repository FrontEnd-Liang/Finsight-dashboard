"use client";

let activeUtterance: SpeechSynthesisUtterance | null = null;
/** 用户点击「停止朗读」时为 true，用于忽略 cancel 触发的伪 error */
let stoppedByUser = false;

function stripForSpeech(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`[^`]+`/g, " ")
    .replace(/[#*_>\[\]()]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 8000);
}

export function isSpeechSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

function cancelPlayback(markAsUserStop: boolean): void {
  if (!isSpeechSupported()) return;
  if (markAsUserStop) {
    stoppedByUser = true;
  }
  window.speechSynthesis.cancel();
  activeUtterance = null;
}

export function stopSpeaking(): void {
  cancelPlayback(true);
}

export function isSpeaking(): boolean {
  return isSpeechSupported() && window.speechSynthesis.speaking;
}

export function speakText(
  text: string,
  callbacks?: { onStart?: () => void; onEnd?: () => void; onError?: () => void }
): boolean {
  if (!isSpeechSupported()) return false;
  const content = stripForSpeech(text);
  if (!content) return false;

  if (activeUtterance || isSpeaking()) {
    cancelPlayback(false);
  }
  stoppedByUser = false;

  const utterance = new SpeechSynthesisUtterance(content);
  utterance.lang = "zh-CN";
  utterance.rate = 1;
  utterance.pitch = 1;

  const voices = window.speechSynthesis.getVoices();
  const zhVoice =
    voices.find((v) => v.lang.startsWith("zh-CN")) ??
    voices.find((v) => v.lang.startsWith("zh")) ??
    voices.find((v) => v.lang.includes("CN"));
  if (zhVoice) utterance.voice = zhVoice;

  utterance.onstart = () => callbacks?.onStart?.();

  utterance.onend = () => {
    const userStopped = stoppedByUser;
    activeUtterance = null;
    stoppedByUser = false;
    if (userStopped) return;
    callbacks?.onEnd?.();
  };

  utterance.onerror = () => {
    const userStopped = stoppedByUser;
    activeUtterance = null;
    stoppedByUser = false;
    if (userStopped) return;
    callbacks?.onError?.();
  };

  activeUtterance = utterance;
  window.speechSynthesis.speak(utterance);
  return true;
}
