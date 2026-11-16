import { gsap } from "gsap";

export type PageFn = (root: HTMLElement) => void | (() => void);

// The app owns navigation and scrolling. Motion only enhances committed content.
export function onPage(setup: PageFn) {
  const root = document.getElementById("main");
  if (!root) return;
  const media = gsap.matchMedia();
  media.add("(prefers-reduced-motion: no-preference)", () => {
    const context = gsap.context(() => setup(root), root);
    return () => context.revert();
  });
  return () => media.revert();
}
