"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";
import type { LiveQueue } from "../types";

type NurseState = {
    queue: LiveQueue | null;
    error: string;
    refresh: () => Promise<void>;
};

const NurseContext = createContext<NurseState | null>(null);

// One poll of the live waiting room shared by every nurse page.
export function NurseProvider({ children }: { children: React.ReactNode }) {
    const [queue, setQueue] = useState<LiveQueue | null>(null);
    const [error, setError] = useState("");

    const refresh = useCallback(async () => {
        try {
            setQueue(await api.queue());
            setError("");
        } catch (e) {
            setError((e as Error).message);
        }
    }, []);

    useEffect(() => {
        const first = setTimeout(refresh, 0);
        const timer = setInterval(refresh, 3000);
        return () => {
            clearTimeout(first);
            clearInterval(timer);
        };
    }, [refresh]);

    return <NurseContext.Provider value={{ queue, error, refresh }}>{children}</NurseContext.Provider>;
}

export function useNurse(): NurseState {
    const ctx = useContext(NurseContext);
    if (!ctx) throw new Error("useNurse must be used inside NurseProvider");
    return ctx;
}
