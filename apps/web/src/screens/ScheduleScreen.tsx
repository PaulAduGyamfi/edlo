import { Banner } from "../components/Banner";
import { Avatar, Shell, Tabs } from "./Shell";
import { type Go } from "./nav";

import "../styles/schedule.css";

type Tone = "none" | "on_track" | "due_soon" | "overdue" | "published" | "blocked";

type Card = { ep: string; title: string; countdown: string; date?: string; tone: Tone; owner: string; current?: boolean };

const COLUMNS: { stage: string; cards: Card[] }[] = [
  {
    stage: "Registered",
    cards: [{ ep: "217", title: "Night Buses", countdown: "No posting date", tone: "none", owner: "AB" }],
  },
  {
    stage: "Mixing",
    cards: [
      { ep: "216", title: "The Landlord Question", countdown: "12 days to publish", date: "21 Sep", tone: "on_track", owner: "AB" },
      { ep: "215", title: "Two Pubs, One Street", countdown: "6 days to publish", date: "15 Sep", tone: "on_track", owner: "AB" },
    ],
  },
  {
    stage: "Plan ready",
    cards: [],
  },
  {
    stage: "Editing",
    cards: [
      { ep: "214", title: "The Venue, the Vicar and the Leeds Pub Story", countdown: "3 days to publish", date: "12 Sep", tone: "due_soon", owner: "CH", current: true },
      { ep: "213", title: "Sunday League", countdown: "Publishes today", date: "9 Sep", tone: "due_soon", owner: "CH" },
    ],
  },
  {
    stage: "Review",
    cards: [{ ep: "212", title: "The Chip Shop Wars", countdown: "4 days overdue", date: "5 Sep", tone: "overdue", owner: "PA" }],
  },
  {
    stage: "Published",
    cards: [{ ep: "211", title: "Same Pod, New Year", countdown: "Published", date: "24 Aug", tone: "published", owner: "PA" }],
  },
  {
    stage: "Blocked",
    cards: [{ ep: "210", title: "The Interview", countdown: "Waiting on final mix", tone: "blocked", owner: "CH" }],
  },
];

export function ScheduleScreen({ go }: { go: Go }) {
  return (
    <Shell
      go={go}
      center={<Tabs active="schedule" go={go} />}
      right={
        <span className="who">
          Chris <Avatar initials="CH" />
        </span>
      }
    >
      <main className="page">
        <header className="sched-head">
          <div>
            <p className="eyebrow">The Sozzled Pod · 9 in flight</p>
            <h1 className="display-lg sched-title">Schedule</h1>
            <p className="sched-sub">
              One episode per date. An episode without a posting date does not exist.
            </p>
          </div>
          <div className="sched-actions">
            <span className="legend">
              <span>
                <i className="key key-on_track" /> on track
              </span>
              <span>
                <i className="key key-due_soon" /> due soon
              </span>
              <span>
                <i className="key key-overdue" /> overdue
              </span>
            </span>
            <button type="button" className="btn btn-accent">
              Register episode
            </button>
          </div>
        </header>

        <Banner kind="warn">Showing data from 09:41:12</Banner>

        <div className="board-scroll">
          <div className="board">
            {COLUMNS.map((col) => (
              <section className="col" key={col.stage}>
                <header className="col-head">
                  <span>{col.stage}</span>
                  <span className="col-count">{col.cards.length}</span>
                </header>
                {col.cards.length === 0 && <span className="col-empty">Nothing here</span>}
                {col.cards.map((card) => {
                  const body = (
                    <>
                      <span className="ep-top">
                        <span className="ep-num">EP {card.ep}</span>
                        <span className="ep-owner">{card.owner}</span>
                      </span>
                      <span className="ep-title">{card.title}</span>
                      <span className="ep-cd">
                        {card.countdown}
                        {card.date && <span className="ep-date"> · {card.date}</span>}
                      </span>
                    </>
                  );
                  return card.current ? (
                    <button type="button" className={`ep ep-${card.tone} ep-link`} onClick={() => go("session")} key={card.ep}>
                      {body}
                    </button>
                  ) : (
                    <article className={`ep ep-${card.tone}`} key={card.ep}>
                      {body}
                    </article>
                  );
                })}
              </section>
            ))}
          </div>
        </div>
      </main>
    </Shell>
  );
}
