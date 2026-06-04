"use client";

let activeUtterance: SpeechSynthesisUtterance | null = null;

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

export function stopSpeaking(): void {
  if (!isSpeechSupported()) return;
  window.speechSynthesis.cancel();
  activeUtterance = null;
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

  stopSpeaking();
  const utterance = new SpeechSynthesisUtterance(content);
  utterance.lang = "zh-CN";
  utterance.rate = 1;
  utterance.pitch = 1;

  const pickVoice = () => {
    const voices = window.speechSynthesis.getVoices();
    return (
      voices.find((v) => v.lang.startsWith("zh-CN")) ??
      voices.find((v) => v.lang.startsWith("zh")) ??
      voices.find((v) => v.lang.includes("CN"))
    );
  };
  const zhVoice = pickVoice();
  if (zhVoice) utterance.voice = zhVoice;

  utterance.onstart = () => callbacks?.onStart?.();
  utterance.onend = () => {
    activeUtterance = null;
    callbacks?.onEnd?.();
  };
  utterance.onerror = () => {
    activeUtterance = null;
    callbacks?.onError?.();
  };

  activeUtterance = utterance;
  window.speechSynthesis.speak(utterance);
  return true;
}
