import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <div className="app-root min-h-dvh min-h-[100dvh]">
        <App />
      </div>
    </BrowserRouter>
  </React.StrictMode>,
);
