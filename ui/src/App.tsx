import { BrowserRouter } from "react-router-dom";
import JChatMindLayout from "./components/JChatMindLayout.tsx";
import { ChatSessionsProvider } from "./contexts/ChatSessionsContext.tsx";
import { KnowledgeBaseProvider } from "./hooks/useKnowledgeBases.tsx";
import { AgentProvider } from "./hooks/useAgents.tsx";

function App() {
  return (
    <BrowserRouter>
      <KnowledgeBaseProvider>
        <AgentProvider>
          <ChatSessionsProvider>
            <JChatMindLayout />
          </ChatSessionsProvider>
        </AgentProvider>
      </KnowledgeBaseProvider>
    </BrowserRouter>
  );
}

export default App;
