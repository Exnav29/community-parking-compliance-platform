// SPDX-License-Identifier: Apache-2.0
import { Network } from "@capacitor/network";
import { useEffect, useState } from "react";

export function useOnline(): boolean {
  const [online, setOnline] = useState<boolean>(navigator.onLine);
  useEffect(() => {
    let remove: (() => void) | undefined;
    Network.getStatus().then((s) => setOnline(s.connected)).catch(() => undefined);
    Network.addListener("networkStatusChange", (s) => setOnline(s.connected)).then((h) => (remove = () => h.remove()));
    const on = () => setOnline(true), off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => { remove?.(); window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);
  return online;
}
