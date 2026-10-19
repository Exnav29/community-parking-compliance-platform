// SPDX-License-Identifier: Apache-2.0
import type { ReactNode } from "react";

/** Large touch target (>= 56px) with text AND an icon; never colour alone (PRD 43). */
export function Big({ icon, label, hint, onClick, disabled, tone }: {
  icon?: string; label: string; hint?: string; onClick: () => void; disabled?: boolean; tone?: "primary" | "danger" | "ok";
}) {
  return (
    <button className={`big ${tone ?? ""}`} onClick={onClick} disabled={disabled}>
      {icon && <span className="ico" aria-hidden="true">{icon}</span>}
      <span><strong>{label}</strong>{hint && <small>{hint}</small>}</span>
    </button>
  );
}

export function Chip({ children, onClick, active }: { children: ReactNode; onClick: () => void; active?: boolean }) {
  return <button className={`chip ${active ? "active" : ""}`} onClick={onClick} aria-pressed={active}>{children}</button>;
}

export function Screen({ title, onBack, children }: { title: string; onBack?: () => void; children: ReactNode }) {
  return (
    <section aria-labelledby="screen-title">
      <div className="bar">
        {onBack && <button className="link" onClick={onBack} aria-label="Back">&larr; Back</button>}
        <h2 id="screen-title">{title}</h2>
      </div>
      {children}
    </section>
  );
}

export const fmtTime = (iso?: string | null) => (iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "-");
