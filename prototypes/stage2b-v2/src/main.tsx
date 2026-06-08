import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import { WitcherJournalScreen } from "./mobile/witcher/WitcherJournalScreen";

const isWitcherMobileRoute = window.location.pathname.startsWith("/mobile/witcher");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {isWitcherMobileRoute ? <WitcherJournalScreen /> : <App />}
  </React.StrictMode>,
);
