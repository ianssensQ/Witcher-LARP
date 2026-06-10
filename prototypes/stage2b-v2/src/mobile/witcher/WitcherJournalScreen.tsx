import { WitcherJournalScreenV1 } from "./WitcherJournalScreenV1";
import { WitcherJournalScreenV2 } from "./WitcherJournalScreenV2";

function shouldUseWitcherJournalV2() {
  const params = new URLSearchParams(window.location.search);
  const version = params.get("version") ?? params.get("v");
  return version === "2" || version === "v2" || window.location.pathname.endsWith("/v2");
}

export function WitcherJournalScreen() {
  return shouldUseWitcherJournalV2() ? <WitcherJournalScreenV2 /> : <WitcherJournalScreenV1 />;
}
