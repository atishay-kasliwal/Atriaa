import { gsap } from "gsap";

export function setupMotion() {
  const diagram = document.querySelector(".flow-figure");
  if (!diagram) return () => {};
  const preference = gsap.matchMedia();
  preference.add("(prefers-reduced-motion: no-preference)", () => {
    const paths = [...diagram.querySelectorAll("[data-flow-path]")];
    const dots = [...diagram.querySelectorAll("[data-flow-dot]")];
    const halo = diagram.querySelector("[data-pulse-halo]");
    let visible = false;
    const visibility = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
    });
    visibility.observe(diagram);
    // The single GSAP clock carries the pulse and the patient-to-review flow.
    const update = (time) => {
      if (!visible || document.hidden) return;
      const phase = (time % 5) / 5;
      paths.forEach((path, index) => {
        const position = (phase + index / paths.length) % 1;
        const point = path.getPointAtLength(position * path.getTotalLength());
        if (dots[index])
          gsap.set(dots[index], { attr: { cx: point.x, cy: point.y } });
      });
      if (halo)
        gsap.set(halo, { opacity: 0.12 + (1 + Math.sin(time * 2.2)) * 0.1 });
    };
    gsap.ticker.add(update);
    return () => {
      visibility.disconnect();
      gsap.ticker.remove(update);
    };
  });
  return () => preference.revert();
}
