// The fishing record: a list everyone can read. Signing in adds the buttons to add, edit and delete.
// Whether a visitor may write is decided by the database, not by this file; hiding buttons is only tidiness.
import { useCallback, useEffect, useState } from "react";
import { copy } from "../copy";
import type { Spot } from "../data/derive";
import { currentEmail, deleteRecord, listRecords, onSignInChange, recordsConfigured, signOut } from "../records/api";
import type { FishingRecord } from "../records/types";
import { RecordCard } from "./RecordCard";
import { RecordForm } from "./RecordForm";
import { SignIn } from "./SignIn";

type Editing = { kind: "none" } | { kind: "new" } | { kind: "edit"; record: FishingRecord };

export function Records({ spots, now }: { spots: Spot[]; now: Date }) {
  const c = copy.records;
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [records, setRecords] = useState<FishingRecord[]>([]);
  const [email, setEmail] = useState<string | null>(null);
  const [askingSignIn, setAskingSignIn] = useState(false);
  const [editing, setEditing] = useState<Editing>({ kind: "none" });
  const [problem, setProblem] = useState("");

  const load = useCallback(() => {
    setStatus("loading");
    listRecords().then((rows) => { setRecords(rows); setStatus("ready"); }, () => setStatus("error"));
  }, []);

  useEffect(() => {
    if (!recordsConfigured) return;
    load();
    let stop: (() => void) | undefined, gone = false;
    currentEmail().then((e) => { if (!gone) setEmail(e); }, () => undefined);
    onSignInChange((e) => { if (!gone) setEmail(e); }).then((s) => { if (gone) s(); else stop = s; }, () => undefined);
    return () => { gone = true; stop?.(); };
  }, [load]);

  // signing out closes anything half-edited
  useEffect(() => { if (!email) setEditing({ kind: "none" }); else setAskingSignIn(false); }, [email]);

  async function remove(record: FishingRecord) {
    setProblem("");
    try {
      await deleteRecord(record);
      setRecords((rows) => rows.filter((r) => r.id !== record.id));
    } catch (error) {
      setProblem(copy.form.removeFailed(error instanceof Error ? error.message : String(error)));
    }
  }

  if (!recordsConfigured) {
    return (
      <section className="section records" aria-labelledby="records-heading">
        <h2 id="records-heading">{c.heading}</h2>
        <p className="empty">{c.notConfigured}</p>
      </section>
    );
  }

  return (
    <section className="section records" aria-labelledby="records-heading">
      <h2 id="records-heading">{c.heading}</h2>

      {email && editing.kind === "none" && (
        <button type="button" className="button button--solid records__add" onClick={() => setEditing({ kind: "new" })}>{c.add}</button>
      )}
      {email && editing.kind === "new" && (
        <RecordForm spots={spots} now={now} record={null} onCancel={() => setEditing({ kind: "none" })}
                    onSaved={() => { setEditing({ kind: "none" }); load(); }} />
      )}

      {problem && <p className="problem problem--inline records__problem" role="alert">{problem}</p>}

      {status === "loading" && !records.length && <p className="status" role="status">{c.loading}</p>}
      {status === "error" && (
        <div className="records__failed" role="alert">
          <p>{c.failed}</p>
          <button type="button" className="button" onClick={load}>{c.retry}</button>
        </div>
      )}
      {status === "ready" && !records.length && <p className="empty">{c.empty}</p>}

      <ol className="records__list">
        {records.map((record) => (
          <li key={record.id}>
            {editing.kind === "edit" && editing.record.id === record.id ? (
              <RecordForm spots={spots} now={now} record={record} onCancel={() => setEditing({ kind: "none" })}
                          onSaved={() => { setEditing({ kind: "none" }); load(); }} />
            ) : (
              <RecordCard record={record} spots={spots} canEdit={Boolean(email) && editing.kind === "none"}
                          onEdit={() => setEditing({ kind: "edit", record })} onDelete={() => remove(record)} />
            )}
          </li>
        ))}
      </ol>

      <div className="records__account">
        {email ? (
          <p>{copy.account.signedIn(email)} <button type="button" className="link" onClick={() => { signOut().catch(() => undefined); }}>{copy.account.signOut}</button></p>
        ) : askingSignIn ? (
          <SignIn onCancel={() => setAskingSignIn(false)} />
        ) : (
          <button type="button" className="link" onClick={() => setAskingSignIn(true)}>{copy.account.open}</button>
        )}
      </div>
    </section>
  );
}
