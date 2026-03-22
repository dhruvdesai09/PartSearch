import { useEffect, useRef, type RefObject } from "react";

/**
 * Invokes `onOutside` when a pointer event occurs outside `ref`.
 */
export function useClickOutside<T extends HTMLElement>(
  ref: RefObject<T | null>,
  onOutside: () => void,
  enabled = true,
): void {
  const cbRef = useRef(onOutside);
  cbRef.current = onOutside;

  useEffect(() => {
    if (!enabled) return;

    const handle = (e: MouseEvent | TouchEvent) => {
      const el = ref.current;
      if (!el) return;
      if (e.target instanceof Node && el.contains(e.target)) return;
      cbRef.current();
    };

    document.addEventListener("mousedown", handle);
    document.addEventListener("touchstart", handle);
    return () => {
      document.removeEventListener("mousedown", handle);
      document.removeEventListener("touchstart", handle);
    };
  }, [ref, enabled]);
}
