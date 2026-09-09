import { Avatar, Shell } from "./Shell";
import { type Go } from "./nav";

import "../styles/approval.css";

// Not in the mock — assembled from the book's approval gate (Ch 22): the pack,
// the deterministic policy check, and the one button only Paul can press.

const CHAPTERS = [
  { tc: "00:00:00", label: "Cold open — “You lot look sozzled already.”" },
  { tc: "00:00:22", label: "The venue" },
  { tc: "00:12:41", label: "A live show. In October." },
  { tc: "00:27:03", label: "The Corsa" },
  { tc: "00:41:03", label: "The Leeds pub story, told properly" },
  { tc: "01:04:12", label: "The vicar" },
  { tc: "01:19:53", label: "Sign-off" },
];

const CHECKS = [
  { label: "Every link on the allowlist", detail: "3 of 3 · sozzledpod.com, youtube.com, spotify.com", ok: true },
  { label: "Every sponsor appears in the transcript", detail: "1 of 1 · “Northern Monk”, 00:52:10", ok: true },
  { label: "Chapters in order", detail: "7 chapters, monotonic", ok: true },
  { label: "Every model quote grounded", detail: "9 of 9 at timecode · 3 dropped before review", ok: true },
  { label: "Human flags preserved", detail: "2 of 2 · Albert", ok: true },
  { label: "Cut cap respected", detail: "11 of 12", ok: true },
];

export function ApprovalScreen({ go }: { go: Go }) {
  return (
    <Shell
      go={go}
      center={
        <>
          <span className="shell-title">EP 214 · The Venue, the Vicar and the Leeds Pub Story</span>
          <span className="status">Policy check passed</span>
        </>
      }
      right={
        <>
          <span className="pill-accent">3 days · Thu 12 Sep</span>
          <span className="who">
            Paul <Avatar initials="PA" />
          </span>
        </>
      }
    >
      <main className="page">
        <header className="appr-head">
          <div>
            <p className="eyebrow">Step 9 of 9 · Paul</p>
            <h1 className="display-xl appr-title">Approve + publish</h1>
            <p className="appr-sub">
              Nothing is marked published until you press the button. Every step before it is
              reversible.
            </p>
          </div>
        </header>

        <div className="appr-layout">
          <section className="pack">
            <h2 className="display-md">Publishing pack</h2>
            <p className="pack-note">Drafted by the model, checked by code, edited by Chris.</p>

            <div className="pack-block">
              <span className="pack-label">Title</span>
              <p className="pack-title">The Venue, the Vicar and the Leeds Pub Story</p>
            </div>

            <div className="pack-block">
              <span className="pack-label">Description</span>
              <p className="pack-body">
                The origin of the name, told in full for the first time. Plus a live show in
                October, in a room, with people. Albert remembers the Corsa. Chris will not defend a
                vicar, actually — no, he will.
              </p>
            </div>

            <div className="pack-block">
              <span className="pack-label">Chapters</span>
              <ol className="chapters">
                {CHAPTERS.map((c) => (
                  <li key={c.tc}>
                    <span className="mono">{c.tc}</span>
                    <span>{c.label}</span>
                  </li>
                ))}
              </ol>
            </div>

            <div className="pack-grid">
              <div className="pack-block">
                <span className="pack-label">Links</span>
                <p className="pack-body mono">
                  sozzledpod.com/live
                  <br />
                  youtube.com/@sozzledpod
                  <br />
                  spotify.com/show/sozzled
                </p>
              </div>
              <div className="pack-block">
                <span className="pack-label">Sponsors</span>
                <p className="pack-body">Northern Monk — verified at 00:52:10</p>
              </div>
            </div>
          </section>

          <aside className="policy">
            <h2 className="display-md">Policy check</h2>
            <p className="policy-sub">Deterministic. Runs between the draft and this screen.</p>
            <ul className="checks">
              {CHECKS.map((c) => (
                <li key={c.label}>
                  <span className="check-ok" aria-hidden="true">
                    ✓
                  </span>
                  <div>
                    <span className="check-label">{c.label}</span>
                    <span className="check-detail">{c.detail}</span>
                  </div>
                </li>
              ))}
            </ul>

            <div className="policy-actions">
              <button type="button" className="btn" onClick={() => go("cut")}>
                Send back to review
              </button>
              <button type="button" className="btn btn-accent btn-wide">
                Approve and mark published
              </button>
            </div>
            <p className="policy-foot">
              Recorded as a stage transition with your actor ID and this request's trace ID.
            </p>
          </aside>
        </div>
      </main>
    </Shell>
  );
}
