import { gsap } from "gsap";
import { ease } from "@/engine/env";

export function setupMotion(root: HTMLElement) {
  const heading = root.querySelector(".home-hero, .page-heading, .dashboard-title-row");
  if (heading) {
    gsap.from(heading, { y: 5, duration: 0.35, ease: ease.soft, clearProps: "transform" });
  }
}
