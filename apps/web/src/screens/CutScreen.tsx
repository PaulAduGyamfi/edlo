import { Avatar, Shell } from "./Shell";
import { type Go } from "./nav";

import "../styles/cut.css";

// Filmstrip frames, cut slices and a waveform — static data shaped to the
// 1:28:40 episode so the playhead and cut list line up with the transcript.
const FRAMES = ["thumb", "thumb-cool", "thumb-amber", "thumb", "thumb-slate", "thumb-cool"];
const FRAME_COUNT = 36;

const CUTS = [8, 14.5, 23, 31, 38.5, 46.1, 47.5, 62, 74].map((at) => ({ at, now: at === 46.1 }));
const FLAGS = [23.4, 66.5];
const PLAYHEAD = 46.5;

const WAVE = Array.from({ length: 140 }, (_, i) =>
  Math.min(100, 28 + Math.round(Math.abs(Math.sin(i * 0.9) * 42 + Math.cos(i * 2.3) * 26))),
);

const CUT_LIST = [
  {
    kind: "flag",
    from: "00:20:41",
    to: "00:20:44",
    dur: "0:03",
    tone: "thumb-amber",
    quote: "mic pop on Paul's channel",
    why: "Albert heard it in the mix. Human flags skip grounding and are never dropped.",
    status: "Albert · accepted",
    statusTone: "st-yellow",
    current: false,
  },
  {
    kind: "remove",
    from: "00:34:10",
    to: "00:34:19",
    dur: "0:09",
    tone: "thumb-cool",
    quote: "Sorry, can you say that again, the dog was barking",
    why: "Restart; the next sentence repeats the question cleanly.",
    status: "✓ Accepted",
    statusTone: "st-green",
    current: false,
  },
  {
    kind: "remove",
    from: "00:40:52",
    to: "00:41:03",
    dur: "0:11",
    tone: "thumb",
    quote: "Um, hang on, is this — are we recording? Sorry, I lost the — where was I.",
    why: "False start before the Leeds story. Story restarts cleanly at 41:03.",
    status: "✓ Verified at timecode",
    statusTone: "st-green",
    current: true,
  },
  {
    kind: "remove",
    from: "00:42:05",
    to: "00:42:09",
    dur: "0:04",
    tone: "thumb-slate",
    quote: "I think we should probably cut this bit but",
    why: "Self-instruction to cut; the clause after it stands alone.",
    status: "✓ Verified at timecode",
    statusTone: "st-green",
    current: false,
  },
  {
    kind: "tighten",
    from: "00:55:12",
    to: "00:55:40",
    dur: "0:28",
    tone: "thumb-cool",
    quote: "the same thing I said about the, the, the",
    why: "Three restarts of one clause; keep the last.",
    status: "✓ Verified at timecode",
    statusTone: "st-green",
    current: false,
  },
];

export function CutScreen({ go }: { go: Go }) {
  return (
    <Shell
      go={go}
      center={
        <>
          <span className="shell-title">EP 214 · The Venue, the Vicar and the Leeds Pub Story</span>
          <span className="status">Length edits unlocked</span>
        </>
      }
      right={
        <>
          <span className="pill-accent">3 days · Thu 12 Sep</span>
          <Avatar initials="CH" />
        </>
      }
    >
      <main className="page cut-layout">
        <div className="cut-main">
          <div className="player">
            <div className="player-hud">
              <span className="live">Cam 2 · Chris</span>
              <span>Final mix v2 · Albert · 14:02</span>
            </div>
            <div className="player-drop">
              <div>
                <span className="drop-icon" />
                Drop the ATEM program frame
                <br />
                <span className="browse">or browse files</span>
              </div>
            </div>
            <div className="player-caption">
              <p className="caption-meta">
                <span className="red">Proposed cut</span> · 00:40:52 → 00:41:03 · 11 s
              </p>
              <p className="caption">
                Right, okay. So. <s>Um, hang on, is this — are we recording? Sorry, I lost the — where was I.</s>{" "}
                Right. Leeds.
              </p>
            </div>
          </div>

          <div className="transport">
            <span className="play-btn" aria-hidden="true">
              ▶
            </span>
            <span className="tc-big">
              00:41:12:14 <span className="dim">/ 01:28:40</span>
            </span>
            <div className="scrub">
              <span className="scrub-fill" />
              <span className="scrub-head" />
            </div>
            <span className="chip mono">1.5×</span>
            <span className="chip">Loop cut</span>
          </div>

          <div className="strip">
            <div className="strip-ticks">
              <span>00:00</span>
              <span>15:00</span>
              <span>30:00</span>
              <span>45:00</span>
              <span>1:00:00</span>
              <span>1:15:00</span>
              <span>1:28:40</span>
            </div>
            <div className="strip-frames">
              {Array.from({ length: FRAME_COUNT }, (_, i) => (
                <span className={`frame ${FRAMES[i % FRAMES.length]}`} key={i} />
              ))}
              {CUTS.map((c) => (
                <span className={`slice${c.now ? " slice-now" : ""}`} style={{ left: `${c.at}%` }} key={c.at} />
              ))}
              {FLAGS.map((at) => (
                <span className="slice slice-flag" style={{ left: `${at}%` }} key={at} />
              ))}
              <span className="playhead" style={{ left: `${PLAYHEAD}%` }} />
            </div>
            <div className="wave" aria-hidden="true">
              {WAVE.map((h, i) => (
                <i style={{ height: `${h}%` }} key={i} />
              ))}
            </div>
            <div className="strip-legend">
              <span>
                <i className="sw" /> Proposed cuts · 9
              </span>
              <span>
                <i className="sw sw-yellow" /> Albert's flags · 2 · never dropped
              </span>
              <span className="keys mono">J K L shuttle · ↑↓ next cut · A accept · R reject · F flag</span>
            </div>
          </div>

          <div className="transcript">
            <div className="tr-line">
              <span className="tr-tc">00:41:11</span>
              <span className="speaker speaker-paul">Paul</span>
              <p>
                So this is the bit where you finally tell it properly. The whole Leeds thing. We have
                teased it for about two years now.
              </p>
            </div>
            <div className="tr-line">
              <span className="tr-tc">00:41:12</span>
              <span className="speaker speaker-chris">Chris</span>
              <p>
                Right, okay. So. <s>Um, hang on, is this — are we recording? Sorry, I lost the — where was I.</s> Right.
                Leeds. It was the winter of two thousand and, God, fourteen?
              </p>
            </div>
            <div className="tr-line">
              <span className="tr-tc">00:41:21</span>
              <span className="speaker speaker-albert">Albert</span>
              <p>Fifteen. It was fifteen because I had the Corsa.</p>
            </div>
          </div>
        </div>

        <aside className="cutlist">
          <header className="cutlist-head">
            <h2 className="display-md">Cut list</h2>
            <span className="chip">11 · 9 grounded</span>
            <span className="cap mono">cap 12</span>
          </header>
          <div className="filters">
            <span className="chip chip-on">All</span>
            <span className="chip">To decide · 7</span>
            <span className="chip">Accepted · 4</span>
          </div>

          {CUT_LIST.map((c) => (
            <article className={`cut${c.current ? " cut-current" : ""}`} key={c.from}>
              <div className="cut-head">
                <span className={`kind kind-${c.kind}`}>{c.kind}</span>
                <span>
                  {c.from} → {c.to}
                </span>
              </div>
              <div className="cut-body">
                <div className={`cut-thumb thumb ${c.tone}`}>
                  <span className="tc tc-abs">{c.dur}</span>
                </div>
                <div>
                  <p className="cut-quote">“{c.quote}”</p>
                  <p className="cut-why">{c.why}</p>
                  <p className={`cut-status ${c.statusTone}`}>{c.status}</p>
                </div>
              </div>
              {c.current && (
                <div className="cut-actions">
                  <button type="button" className="btn btn-green btn-sm">
                    Accept
                  </button>
                  <button type="button" className="btn btn-sm">
                    Skip
                  </button>
                </div>
              )}
            </article>
          ))}

          <p className="cut-dropped">
            3 more were dropped by the grounding check before you saw them — wrong timecode ×2,
            over cap ×1.
          </p>
          <button type="button" className="btn btn-accent btn-wide">
            Send 9 markers to Final Cut Pro
          </button>
        </aside>
      </main>
    </Shell>
  );
}
