import type { TacticalState } from "./types";

export async function fetchLatestState(matchId: string): Promise<TacticalState> {
  const response = await fetch(`/api/matches/${matchId}/latest-state`);
  if (!response.ok) {
    throw new Error(`Failed to fetch tactical state: ${response.status}`);
  }
  return response.json();
}
