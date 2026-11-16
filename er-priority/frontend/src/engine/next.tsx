"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { onPage, type PageFn } from "./index";

export function Engine({ setup }: { setup: PageFn }) {
  const pathname = usePathname();
  useEffect(() => onPage(setup), [pathname, setup]);
  return null;
}
