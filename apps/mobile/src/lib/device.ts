// SPDX-License-Identifier: Apache-2.0
/** Native capability wrappers: foreground-only location, in-app camera, keystore-backed storage. */
import { Camera, CameraResultType, CameraSource } from "@capacitor/camera";
import { Geolocation } from "@capacitor/geolocation";
import { Capacitor } from "@capacitor/core";
import { SecureStorage } from "@aparajita/capacitor-secure-storage";
import type { KeyValueStore } from "./queue";

export interface LocationFix {
  lat: number;
  lon: number;
  accuracyM: number;
  capturedAt: string;
  source: "device";
}

/** Event-triggered, foreground, fresh reading (maximumAge 0). Never background. Returns null on denial/timeout. */
export async function captureLocation(timeoutMs = 15000): Promise<LocationFix | null> {
  try {
    const perm = await Geolocation.checkPermissions();
    if (perm.location !== "granted") {
      const asked = await Geolocation.requestPermissions({ permissions: ["location"] });
      if (asked.location !== "granted") return null;
    }
    const p = await Geolocation.getCurrentPosition({ enableHighAccuracy: true, maximumAge: 0, timeout: timeoutMs });
    return { lat: p.coords.latitude, lon: p.coords.longitude, accuracyM: p.coords.accuracy, capturedAt: new Date(p.timestamp).toISOString(), source: "device" };
  } catch {
    return null; // caller falls back to manual pin / zone; reporting is never blocked by GPS
  }
}

export async function takePhoto(): Promise<{ dataUrl: string; base64: string; sha256: string } | null> {
  try {
    const photo = await Camera.getPhoto({ quality: 70, width: 1600, correctOrientation: true, resultType: CameraResultType.DataUrl, source: CameraSource.Camera, allowEditing: false });
    if (!photo.dataUrl) return null;
    const b64 = photo.dataUrl.split(",", 2)[1] ?? "";
    const bin = atob(b64);
    const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
    const digest = await crypto.subtle.digest("SHA-256", bytes); // hash of the raw image bytes; the server recomputes it
    return { dataUrl: photo.dataUrl, base64: b64, sha256: [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("") };
  } catch {
    return null;
  }
}

/** Keystore/Keychain on native; on the PWA fallback we deliberately refuse to persist secrets or drafts. */
export function secureStore(): KeyValueStore | null {
  if (!Capacitor.isNativePlatform()) return null;
  return {
    async get(key) {
      return ((await SecureStorage.get(key)) as string | null) ?? null;
    },
    async set(key, value) {
      await SecureStorage.set(key, value);
    },
    async remove(key) {
      await SecureStorage.remove(key);
    },
  };
}
