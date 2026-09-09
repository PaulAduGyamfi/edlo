import { useState } from "react";

import "./styles/ui.css";
import { ApprovalScreen } from "./screens/ApprovalScreen";
import { ArchiveScreen } from "./screens/ArchiveScreen";
import { CutScreen } from "./screens/CutScreen";
import { ScheduleScreen } from "./screens/ScheduleScreen";
import { SessionScreen } from "./screens/SessionScreen";
import { type Screen } from "./screens/nav";

function App() {
  const [screen, go] = useState<Screen>("session");

  switch (screen) {
    case "cut":
      return <CutScreen go={go} />;
    case "archive":
      return <ArchiveScreen go={go} />;
    case "schedule":
      return <ScheduleScreen go={go} />;
    case "approval":
      return <ApprovalScreen go={go} />;
    default:
      return <SessionScreen go={go} />;
  }
}

export default App;
