// Two screens: the board, and one episode. The route lives in the URL hash
// so a reload or a shared link lands on the same episode.

export type Route = { screen: "schedule" } | { screen: "episode"; id: string };

export type Go = (route: Route) => void;

export function routeFromHash(hash: string): Route {
  const m = /^#\/episodes\/([A-Za-z0-9_-]+)$/.exec(hash);
  return m ? { screen: "episode", id: m[1] } : { screen: "schedule" };
}

export function hashFromRoute(route: Route): string {
  return route.screen === "episode" ? `#/episodes/${route.id}` : "#/";
}
