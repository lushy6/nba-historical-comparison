"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";


type IntentState = {
  hasOpened: boolean;
  instantUntil: number;
};

type IntentContextValue = {
  requestOpen: (key: string, open: boolean) => void;
  isOpen: (key: string) => boolean;
};

const IntentContext = createContext<IntentContextValue | null>(null);

const FIRST_DELAY_MS = 500;
const INSTANT_WINDOW_MS = 2000;

export function TooltipIntentProvider({ children }: { children: React.ReactNode }) {
  const [openKey, setOpenKey] = useState<string | null>(null);
  const stateRef = useRef<IntentState>({ hasOpened: false, instantUntil: 0 });
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => () => clearTimer(), [clearTimer]);

  const requestOpen = useCallback((key: string, open: boolean) => {
    if (!open) {
      clearTimer();
      setOpenKey(null);
      return;
    }

    const now = Date.now();
    const isInstant = stateRef.current.hasOpened && now < stateRef.current.instantUntil;

    if (isInstant) {
      clearTimer();
      stateRef.current.instantUntil = now + INSTANT_WINDOW_MS;
      setOpenKey(key);
    } else {
      clearTimer();
      timerRef.current = setTimeout(() => {
        stateRef.current.hasOpened = true;
        stateRef.current.instantUntil = Date.now() + INSTANT_WINDOW_MS;
        setOpenKey(key);
      }, FIRST_DELAY_MS);
    }
  }, [clearTimer]);

  const isOpen = useCallback((key: string) => openKey === key, [openKey]);

  return (
    <IntentContext.Provider value={{ requestOpen, isOpen }}>
      {children}
    </IntentContext.Provider>
  );
}

export function useTooltipIntent() {
  const ctx = useContext(IntentContext);
  if (!ctx) throw new Error("useTooltipIntent must be used inside TooltipIntentProvider");
  return ctx;
}
