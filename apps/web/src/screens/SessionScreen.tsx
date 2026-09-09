import { Avatar, Shell, Tabs } from "./Shell";
import { type Go } from "./nav";

import "../styles/session.css";

const COLD_OPENS = [
  {
    tc: "00:41:24",
    rank: "Chosen",
    chosen: true,
    tone: "thumb-red",
    drop: true,
    quote: "“You lot look sozzled already.”",
    note: "The origin of the name, told in full for the first time.",
    dur: "0:22",
  },
  {
    tc: "01:04:12",
    rank: "#2",
    chosen: false,
    tone: "thumb-cool",
    drop: false,
    quote: "“I will not defend a vicar, actually — no. I will.”",
    note: "Sharp turn, self-contained.",
    dur: "0:15",
  },
  {
    tc: "00:12:41",
    rank: "#3",
    chosen: false,
    tone: "thumb-amber",
    drop: false,
    quote: "“A live show. In October. In a room. With people.”",
    note: "Announces the live show.",
    dur: "0:18",
  },
  {
    tc: "00:27:03",
    rank: "#4",
    chosen: false,
    tone: "thumb",
    drop: true,
    quote: "“It was fifteen because I had the Corsa.”",
    note: "Albert correcting Chris; works without context.",
    dur: "0:11",
  },
  {
    tc: "01:19:53",
    rank: "#5",
    chosen: false,
    tone: "thumb-slate",
    drop: false,
    quote: "“If this is the last thing we say, I am fine with that.”",
    note: "Ends the episode; strong as an opener too.",
    dur: "0:20",
  },
];

const PLAN: { label: string; owner: string; state: "done" | "now" | "next"; to?: "cut" | "approval" }[] = [
  { label: "Register + posting slot", owner: "Albert", state: "done" },
  { label: "Transcribe", owner: "Edlo", state: "done" },
  { label: "Final mix uploaded", owner: "Albert", state: "done" },
  { label: "Cuts + cold opens proposed", owner: "Edlo", state: "done" },
  { label: "Choose the cold open", owner: "Chris", state: "now" },
  { label: "Triage cuts, then cut", owner: "Chris", state: "next", to: "cut" },
  { label: "Sync graphics to new length", owner: "Chris", state: "next" },
  { label: "Pack drafted + policy-checked", owner: "Edlo", state: "next" },
  { label: "Approve + publish", owner: "Paul", state: "next", to: "approval" },
];

export function SessionScreen({ go }: { go: Go }) {
  return (
    <Shell
      go={go}
      center={<Tabs active="session" go={go} />}
      right={
        <span className="who">
          Chris <Avatar initials="CH" />
        </span>
      }
    >
      <main className="page">
        <section className="hero">
          <div>
            <p className="eyebrow">EP 214 · Recorded Sun 1 Sep · 1:28:40</p>
            <h1 className="display-xl hero-title">The Venue, the Vicar and the Leeds Pub Story</h1>
          </div>
          <div className="countdown">
            <span className="countdown-n">3</span>
            <span className="countdown-label">Days to publish</span>
            <span className="countdown-date">Thursday 12 September · 07:00</span>
          </div>
        </section>

        <section className="mix">
          <span className="signal" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
          </span>
          <div className="mix-text">
            <strong>Final mix v2 landed from Albert at 14:02</strong>
            <span className="mix-meta">
              ep214_final_mix_v2.wav · 412 MB · 48 kHz · you can now make length edits to the
              ATEM video
            </span>
          </div>
          <div className="mix-actions">
            <button type="button" className="btn">
              Download
            </button>
            <button type="button" className="btn btn-accent" onClick={() => go("cut")}>
              Open cut session
            </button>
          </div>
        </section>

        <header className="sec-head">
          <h2 className="display-md">Cold open</h2>
          <span className="sec-sub">Five moments, quotes verbatim. Pick one or none.</span>
          <span className="sec-hint">← swipe →</span>
        </header>
        <div className="stories">
          {COLD_OPENS.map((c) => (
            <article className={`story ${c.tone}${c.chosen ? " story-chosen" : ""}`} key={c.tc}>
              <div className="story-top">
                <span className="tc">{c.tc}</span>
                <span className={`story-rank${c.chosen ? " story-rank-chosen" : ""}`}>{c.rank}</span>
              </div>
              <div className="story-mid">
                {c.drop && (
                  <span className="story-drop">
                    <span className="drop-icon" />
                    Drop a frame
                  </span>
                )}
              </div>
              <div className="story-glass">
                <p className="story-quote display-sm">{c.quote}</p>
                <p className="story-note">{c.note}</p>
                <div className="story-foot">
                  <span className="play" aria-hidden="true">
                    ▶
                  </span>
                  <span>{c.dur}</span>
                </div>
              </div>
            </article>
          ))}
        </div>

        <header className="sec-head">
          <h2 className="display-md">The plan</h2>
          <span className="sec-sub">Nine steps, your order, every episode. You are on step 5.</span>
        </header>
        <ol className="plan">
          {PLAN.map((step) => {
            const inner = (
              <>
                <span className="plan-bar" />
                <span className="plan-label">{step.label}</span>
                <span className="plan-owner">{step.owner}</span>
              </>
            );
            return (
              <li className={`plan-${step.state}`} key={step.label}>
                {step.to ? (
                  <button type="button" className="plan-link" onClick={() => go(step.to!)}>
                    {inner}
                  </button>
                ) : (
                  inner
                )}
              </li>
            );
          })}
        </ol>
      </main>
    </Shell>
  );
}
