import { useState, useEffect } from "react";
import { Routes, Route } from "react-router-dom";
import Layout from "../layout/Layout.tsx";
import Sidebar from "../layout/Sidebar.tsx";
import SideMenu from "./SideMenu.tsx";
import Content from "../layout/Content.tsx";
import TopBar from "./TopBar.tsx";
import AgentChatView from "./views/AgentChatView.tsx";
import AgentManagementView from "./views/AgentManagementView.tsx";
import KnowledgeBaseView from "./views/KnowledgeBaseView.tsx";
import PlanetariumView from "./views/PlanetariumView.tsx";
import { PetProvider } from "./pet/PetContext.tsx";
import PetOverlay from "./pet/PetOverlay.tsx";
import AddAgentModal from "./modals/AddAgentModal.tsx";
import AddKnowledgeBaseModal from "./modals/AddKnowledgeBaseModal.tsx";
import { useAgents } from "../hooks/useAgents.ts";
import { useKnowledgeBases } from "../hooks/useKnowledgeBases.ts";

export default function JChatMindLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const [isAddAgentModalOpen, setIsAddAgentModalOpen] = useState(false);
  const [editingAgent, setEditingAgent] = useState<import("../api/api.ts").AgentVO | null>(null);
  const [isAddKnowledgeBaseModalOpen, setIsAddKnowledgeBaseModalOpen] = useState(false);

  const toggleSidebar = () => setSidebarCollapsed((prev) => !prev);

  const toggleAddAgentModal = () => {
    setIsAddAgentModalOpen(!isAddAgentModalOpen);
    setEditingAgent(null);
  };

  const openEditAgentModal = (agent: import("../api/api.ts").AgentVO) => {
    setEditingAgent(agent);
    setIsAddAgentModalOpen(true);
  };

  const toggleAddKnowledgeBaseModal = () => {
    setIsAddKnowledgeBaseModalOpen(!isAddKnowledgeBaseModalOpen);
  };

  const { createAgentHandle, deleteAgentHandle, updateAgentHandle } = useAgents();
  const { createKnowledgeBaseHandle } = useKnowledgeBases();

  useEffect(() => {
    const handleClick = () => {
      window.petActions?.setCurious?.();
    };
    window.addEventListener("click", handleClick);
    return () => window.removeEventListener("click", handleClick);
  }, []);

  return (
    <PetProvider>
      <Layout>
        <div className="flex-1 flex overflow-hidden">
          <Sidebar collapsed={sidebarCollapsed} onToggle={toggleSidebar}>
            <TopBar collapsed={sidebarCollapsed} onToggle={toggleSidebar} />
            <SideMenu
              onCreateAgentClick={toggleAddAgentModal}
              onCreateKnowledgeBaseClick={toggleAddKnowledgeBaseModal}
            />
          </Sidebar>

          <Content>
            <Routes>
              <Route path="/" element={<AgentChatView />} />
              <Route path="/agent" element={<AgentManagementView onCreateClick={toggleAddAgentModal} onEditClick={openEditAgentModal} onDeleteClick={deleteAgentHandle} />} />
              <Route path="/chat" element={<AgentChatView />} />
              <Route path="/chat/:chatSessionId" element={<AgentChatView />} />
              <Route path="/knowledge-base" element={<KnowledgeBaseView onCreateClick={toggleAddKnowledgeBaseModal} />} />
              <Route path="/knowledge-base/:knowledgeBaseId" element={<KnowledgeBaseView onCreateClick={toggleAddKnowledgeBaseModal} />} />
              <Route path="/planetarium" element={<PlanetariumView />} />
            </Routes>
          </Content>
        </div>

        <PetOverlay />
      </Layout>

      <AddAgentModal
        open={isAddAgentModalOpen}
        onClose={toggleAddAgentModal}
        createAgentHandle={createAgentHandle}
        updateAgentHandle={updateAgentHandle}
        editingAgent={editingAgent}
      />
      <AddKnowledgeBaseModal
        open={isAddKnowledgeBaseModalOpen}
        onClose={toggleAddKnowledgeBaseModal}
        createKnowledgeBaseHandle={createKnowledgeBaseHandle}
      />
    </PetProvider>
  );
}
