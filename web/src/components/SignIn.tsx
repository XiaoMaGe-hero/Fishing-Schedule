import { useState, type FormEvent } from "react";
import { copy } from "../copy";
import { signIn } from "../records/api";

/** Email and password. There is no "create account": new sign-ups are switched off in Supabase. */
export function SignIn({ onCancel }: { onCancel: () => void }) {
  const c = copy.account;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [state, setState] = useState<"idle" | "working" | "failed">("idle");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setState("working");
    try {
      await signIn(email.trim(), password); // on success Records hears about it and removes this form
    } catch {
      setState("failed");
    }
  }

  return (
    <form className="form form--signin" onSubmit={submit}>
      <h3>{c.heading}</h3>
      <label className="field"><span>{c.email}</span>
        <input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
      <label className="field"><span>{c.password}</span>
        <input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></label>
      {state === "failed" && <p className="form__problem" role="alert">{c.failed}</p>}
      <div className="form__actions">
        <button type="submit" className="button button--solid" disabled={state === "working"}>{state === "working" ? c.working : c.submit}</button>
        <button type="button" className="button" onClick={onCancel}>{c.cancel}</button>
      </div>
    </form>
  );
}
