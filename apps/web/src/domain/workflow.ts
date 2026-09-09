// Mirror of edlo/services/workflow.py. The server is the authority; this
// copy only decides which buttons to show and how to explain a refusal.

import { type Role, type Stage } from "../api/episodes";

export const PIPELINE: Stage[] = [
  "registered",
  "mixing",
  "plan_ready",
  "editing",
  "review",
  "published",
];

export const BOARD_STAGES: Stage[] = [...PIPELINE, "blocked"];

export const STAGE_LABEL: Record<Stage, string> = {
  registered: "Registered",
  mixing: "Mixing",
  plan_ready: "Plan ready",
  editing: "Editing",
  review: "Review",
  published: "Published",
  blocked: "Blocked",
};

export const ROLE_LABEL: Record<Role, string> = {
  audio_editor: "Audio editor",
  video_editor: "Video editor",
  owner: "Owner",
};

const LEGAL: Record<Stage, Stage[]> = {
  registered: ["mixing", "blocked"],
  mixing: ["plan_ready", "blocked"],
  plan_ready: ["editing", "mixing", "blocked"],
  editing: ["review", "plan_ready", "blocked"],
  review: ["published", "editing", "blocked"],
  published: [],
  blocked: ["registered", "mixing", "plan_ready", "editing", "review"],
};

// Who may move an episode INTO each stage. "registered" has no owner on the
// server either, so nothing can be moved back into it (blocked → registered
// is listed as legal but nobody is permitted).
const OWNERS: Record<Stage, Role[]> = {
  registered: [],
  mixing: ["audio_editor", "owner"],
  plan_ready: ["video_editor", "owner"],
  editing: ["video_editor", "owner"],
  review: ["video_editor", "owner"],
  published: ["owner"],
  blocked: ["audio_editor", "video_editor", "owner"],
};

export type MoveKind = "forward" | "back" | "block" | "unblock";

export type Move = {
  to: Stage;
  kind: MoveKind;
  allowed: boolean;
  why: string | null; // filled in when not allowed
};

export function isStage(s: string): s is Stage {
  return s in STAGE_LABEL;
}

function owners(stage: Stage): string {
  const names = OWNERS[stage].map((r) => ROLE_LABEL[r].toLowerCase());
  if (names.length === 0) return "nobody";
  if (names.length === 1) return `the ${names[0]}`;
  return `the ${names.slice(0, -1).join(", ")} or ${names[names.length - 1]}`;
}

export function movesFrom(stage: Stage, role: Role): Move[] {
  const fromIndex = PIPELINE.indexOf(stage);
  return LEGAL[stage].map((to) => {
    const allowed = OWNERS[to].includes(role);
    let kind: MoveKind;
    if (to === "blocked") kind = "block";
    else if (stage === "blocked") kind = "unblock";
    else kind = PIPELINE.indexOf(to) > fromIndex ? "forward" : "back";
    return {
      to,
      kind,
      allowed,
      why: allowed
        ? null
        : `Only ${owners(to)} can move an episode to ${STAGE_LABEL[to].toLowerCase()}.`,
    };
  });
}

export const canRegister = (role: Role) => role === "audio_editor" || role === "owner";

/** Actor ids look like "u_albert"; the history only stores the id. */
export function actorName(actorId: string): string {
  const bare = actorId.replace(/^u_/, "");
  return bare ? bare[0].toUpperCase() + bare.slice(1) : actorId;
}

/** The role whose move is needed next, so the schedule can say who it waits on. */
export function waitingOn(stage: Stage): Role | null {
  switch (stage) {
    case "registered":
      return "audio_editor";
    case "mixing":
    case "plan_ready":
    case "editing":
      return "video_editor";
    case "review":
      return "owner";
    default:
      return null;
  }
}
