"use client";

import { useEffect, useRef } from "react";

const REVEAL_SELECTORS = [
  ".section-heading",
  ".research-row",
  ".research-marquee",
  ".compare-card",
  ".conversion-intro",
  ".brand-marquee",
  ".conversion-notes p",
  ".hellobeauty-footer p",
];

const INTERACTIVE_SELECTOR =
  "a, button, .compare-card, .research-row, .hero-proof-list span, .research-marquee, .brand-marquee";

export function MotionEffects() {
  const progressRef = useRef<HTMLSpanElement>(null);
  const cursorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = document.documentElement;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

    if (reducedMotion.matches) {
      root.classList.add("motion-reduced");
      return () => root.classList.remove("motion-reduced");
    }

    root.classList.add("motion-ready");

    const revealElements = Array.from(
      document.querySelectorAll<HTMLElement>(REVEAL_SELECTORS.join(",")),
    );

    revealElements.forEach((element, index) => {
      element.style.setProperty("--motion-index", String(index % 12));
    });

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) {
            return;
          }

          entry.target.classList.add("is-inview");
          observer.unobserve(entry.target);
        });
      },
      {
        rootMargin: "0px 0px -12% 0px",
        threshold: 0.16,
      },
    );

    revealElements.forEach((element) => observer.observe(element));

    const cursor = cursorRef.current;
    const progress = progressRef.current;
    let currentX = window.innerWidth / 2;
    let currentY = window.innerHeight / 2;
    let targetX = currentX;
    let targetY = currentY;
    let animationFrame = 0;

    const updateCursorState = (target: EventTarget | null) => {
      if (!(target instanceof Element) || !cursor) {
        return;
      }

      cursor.classList.toggle("is-active", Boolean(target.closest(INTERACTIVE_SELECTOR)));
    };

    const handlePointerMove = (event: PointerEvent) => {
      if (event.pointerType === "touch") {
        return;
      }

      targetX = event.clientX;
      targetY = event.clientY;
      cursor?.classList.add("is-visible");
      updateCursorState(event.target);
    };

    const handlePointerLeave = () => {
      cursor?.classList.remove("is-visible", "is-active");
    };

    const tick = () => {
      currentX += (targetX - currentX) * 0.18;
      currentY += (targetY - currentY) * 0.18;

      if (cursor) {
        cursor.style.transform = `translate3d(${currentX}px, ${currentY}px, 0)`;
      }

      if (progress) {
        const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
        const scrollProgress = maxScroll > 0 ? window.scrollY / maxScroll : 0;
        progress.style.setProperty("--progress-scale", scrollProgress.toFixed(4));
      }

      animationFrame = window.requestAnimationFrame(tick);
    };

    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    window.addEventListener("pointerleave", handlePointerLeave);
    animationFrame = window.requestAnimationFrame(tick);

    return () => {
      root.classList.remove("motion-ready");
      observer.disconnect();
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerleave", handlePointerLeave);
      window.cancelAnimationFrame(animationFrame);
    };
  }, []);

  return (
    <>
      <div className="motion-progress" aria-hidden="true">
        <span ref={progressRef} />
      </div>
      <div className="kinetic-cursor" ref={cursorRef} aria-hidden="true">
        <span className="cursor-ring" />
        <span className="cursor-dot" />
      </div>
    </>
  );
}
