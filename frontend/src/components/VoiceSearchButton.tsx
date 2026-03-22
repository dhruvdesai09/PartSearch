import React, { useEffect, useRef, useState } from "react";

type Props = {
  onTranscript: (text: string) => void;
};

declare global {
  interface Window {
    webkitSpeechRecognition?: any;
    SpeechRecognition?: any;
  }
}

export default function VoiceSearchButton({ onTranscript }: Props) {
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    setSupported(Boolean(SR));
    if (!SR) return;

    const rec = new SR();
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = "en-US";

    rec.onresult = (event: any) => {
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0]?.transcript ?? "";
      }
      transcript = transcript.trim();
      if (transcript) onTranscript(transcript);
    };

    rec.onerror = () => {
      setListening(false);
    };

    rec.onend = () => {
      setListening(false);
    };

    recognitionRef.current = rec;
  }, [onTranscript]);

  const start = () => {
    if (!supported) return;
    if (!recognitionRef.current) return;
    if (listening) return;
    setListening(true);
    try {
      recognitionRef.current.start();
    } catch {
      setListening(false);
    }
  };

  return (
    <button
      type="button"
      onClick={start}
      disabled={!supported || listening}
      className={`flex shrink-0 items-center justify-center gap-2 rounded-xl border px-4 py-3 text-sm font-semibold shadow-md transition-all duration-200 ease-out disabled:cursor-not-allowed disabled:opacity-45 ${
        listening
          ? "animate-pulse-ring border-teal-400 bg-gradient-to-br from-teal-500 to-cyan-500 text-white shadow-teal-600/40"
          : "border-violet-200/80 bg-white text-violet-800 shadow-violet-200/50 hover:border-violet-300 hover:bg-gradient-to-br hover:from-violet-50 hover:to-sky-50 hover:text-violet-900"
      }`}
      aria-label="Voice search"
      aria-pressed={listening}
      title={supported ? "Voice search" : "Voice search not supported in this browser"}
    >
      <svg
        className={`h-5 w-5 ${listening ? "text-white" : "text-violet-600"}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={1.75}
        aria-hidden
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z"
        />
      </svg>
      <span className="hidden sm:inline">
        {listening ? "Listening…" : "Voice"}
      </span>
    </button>
  );
}
