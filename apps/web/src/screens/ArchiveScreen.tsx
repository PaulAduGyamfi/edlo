import { Shell, Tabs } from "./Shell";
import { type Go } from "./nav";

import "../styles/archive.css";

const RESULTS = [
  {
    ep: "Ep 171 · Christmas Special",
    when: "Feb 2025",
    mood: "Warm",
    moodTone: "warm",
    tc: "32:08",
    tone: "thumb",
    text: (
      <>
        …the whole thing started in that <mark>pub in Leeds</mark> when the landlord said we looked
        sozzled already.
      </>
    ),
  },
  {
    ep: "Ep 88 · The Menace",
    when: "Nov 2022",
    mood: "Mildly negative",
    moodTone: "neg",
    tc: "1:04:51",
    tone: "thumb-cool",
    text: (
      <>
        The <mark>Leeds landlord</mark> is a menace. I said it then, I will say it now.
      </>
    ),
  },
  {
    ep: "Ep 88 · The Menace",
    when: "Nov 2022",
    mood: "Neutral",
    moodTone: "neutral",
    tc: "1:05:30",
    tone: "thumb-slate",
    text: (
      <>
        Chris, tell the <mark>Leeds story</mark> — no, save it for a proper reason.
      </>
    ),
  },
  {
    ep: "Ep 204 · Mailbag",
    when: "Jun 2025",
    mood: "Neutral",
    moodTone: "neutral",
    tc: "09:14",
    tone: "thumb-amber",
    text: (
      <>
        Someone wrote in asking about the <mark>Leeds thing</mark> again. We will get to it.
      </>
    ),
  },
];

const TRACE = [
  { call: 'search_transcripts("Leeds pub story", k=8)', out: "6 passages across 3 episodes · hybrid, fused by rank" },
  { call: 'get_episode("ep171")', out: "Christmas Special · published 14 Feb 2025" },
  { call: 'get_transcript_span("ep088", 3891000, 3960000)', out: "69 s of context around 1:04:51" },
  { call: 'search_transcripts("Leeds landlord", k=5)', out: "2 new passages · nothing after Ep 171" },
];

export function ArchiveScreen({ go }: { go: Go }) {
  return (
    <Shell
      go={go}
      center={<Tabs active="archive" go={go} />}
      right={<span className="status">Read-only · 213 episodes · 119k passages</span>}
    >
      <main className="page archive-layout">
        <div className="archive-main">
          <div className="ask">
            <span>Have we told the Leeds pub story before, and was it positive?</span>
            <span className="ask-send" aria-hidden="true">
              ➤
            </span>
          </div>

          <section className="answer">
            <span className="label-green">Answer · every claim links to a timecode</span>
            <div className="answer-row">
              <p className="answer-text">
                Yes — twice. Most recently in <span className="cite">Ep 171 · 32:08</span> (Feb 2025),
                told warmly as the origin of the show's name. An earlier mention in{" "}
                <span className="cite">Ep 88 · 1:04:51</span> is mildly negative — Paul calls the
                landlord “a menace”. Nothing since Ep 171, so a callback in 214 is a 19-month gap.
              </p>
              <div className="answer-count">
                <span className="n">6</span>
                <span className="l">
                  passages
                  <br />3 episodes
                </span>
              </div>
            </div>
          </section>

          <div className="results">
            {RESULTS.map((r) => (
              <article className="result" key={r.ep + r.tc}>
                <div className={`thumb ${r.tone}`}>
                  <span className="tc tc-abs">{r.tc}</span>
                </div>
                <div>
                  <h3>{r.ep}</h3>
                  <p className="meta">
                    {r.when} · <span className={r.moodTone}>{r.mood}</span>
                  </p>
                  <p>{r.text}</p>
                </div>
              </article>
            ))}
          </div>
        </div>

        <aside className="trace">
          <h2 className="display-md">How I found this</h2>
          <p className="trace-sub">
            4 of 6 steps · 41 s · read tools only. It cannot approve, publish or delete — those
            tools do not exist for it.
          </p>
          <ol>
            {TRACE.map((t, i) => (
              <li key={t.call}>
                <span className="n">{i + 1}</span>
                <div>
                  <code>{t.call}</code>
                  <span className="out">{t.out}</span>
                </div>
              </li>
            ))}
          </ol>
        </aside>
      </main>
    </Shell>
  );
}
