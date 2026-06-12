import { HttpAgent } from "@ag-ui/client";
import { CopilotKit } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";

import "@copilotkit/react-ui/styles.css";
import "./App.css";

// Direct AG-UI connection to the FastAPI `/agent` endpoint (proxied by Vite in
// dev). This runtime-less mode keeps the stack Python-only; a hosted
// CopilotRuntime can be layered on later for production hardening.
const agent = new HttpAgent({ url: "/agent" });

export default function App() {
  return (
    <CopilotKit agents__unsafe_dev_only={{ default: agent }} agent="default">
      <div className="app">
        <header className="app__header">
          <h1>🔍 Repo Research</h1>
          <p>Analyze GitHub repositories with AI — powered by LangGraph.</p>
        </header>
        <main className="app__chat">
          <CopilotChat
            labels={{
              title: "Repo Research",
              initial:
                "Ask me to analyze your starred repos, search topics, or find maintenance hotspots.",
            }}
          />
        </main>
      </div>
    </CopilotKit>
  );
}
