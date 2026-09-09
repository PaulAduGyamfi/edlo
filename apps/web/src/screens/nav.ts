export type Screen = "session" | "cut" | "archive" | "schedule" | "approval";

// The only behaviour in the UI: switching which screen is mounted.
export type Go = (screen: Screen) => void;
