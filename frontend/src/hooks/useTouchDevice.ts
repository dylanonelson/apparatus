"use client";

import { useState, useEffect } from "react";

/**
 * Detects whether the device has a touch-primary interface (phones, tablets).
 *
 * Uses the CSS media query `(hover: none) and (pointer: coarse)` which matches
 * devices where the primary input mechanism is a touchscreen (no hover
 * capability and imprecise pointer). Desktop machines with touchscreens will
 * not match because their primary pointer is typically `fine` (mouse/trackpad).
 */
export const useTouchDevice = (): boolean => {
  const [isTouch, setIsTouch] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia("(hover: none) and (pointer: coarse)");
    setIsTouch(mql.matches);

    const handler = (e: MediaQueryListEvent) => setIsTouch(e.matches);
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);

  return isTouch;
};
