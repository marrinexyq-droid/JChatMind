import React, { useEffect, useState } from "react";
import { Button, Checkbox, Input, Select, Slider } from "antd";
import TextArea from "antd/es/input/TextArea";
import { SaveOutlined } from "@ant-design/icons";
import { motion, AnimatePresence } from "framer-motion";
import GlassModal from "./GlassModal.tsx";
import {
  type CreateAgentRequest,
  type UpdateAgentRequest,
  type AgentVO,
  type ModelType,
  type RagMode,
  getOptionalTools,
  type ToolVO,
} from "../../api/api.ts";
import { useKnowledgeBases } from "../../hooks/useKnowledgeBases.tsx";

interface AddAgentModalProps {
  open: boolean;
  onClose: () => void;
  createAgentHandle: (request: CreateAgentRequest) => Promise<void>;
  updateAgentHandle?: (
    agentId: string,
    request: UpdateAgentRequest,
  ) => Promise<void>;
  editingAgent?: AgentVO | null;
}

const menuItems = [
  { key: "base", label: "基础设置" },
  { key: "model", label: "模型设置" },
  { key: "knowledge", label: "知识库设置" },
  { key: "tools", label: "工具调用" },
];

const AddAgentModal: React.FC<AddAgentModalProps> = ({
  open,
  onClose,
  createAgentHandle,
  updateAgentHandle,
  editingAgent,
}) => {
  // 菜单项
  const [selectedKey, setSelectedKey] = useState<string>("base");

  // 获取知识库列表
  const { knowledgeBases } = useKnowledgeBases();

  // 工具列表
  const [tools, setTools] = useState<ToolVO[]>([]);

  // 表单数据
  const [formData, setFormData] = useState<CreateAgentRequest>({
    name: "智能体助手",
    description: "",
    systemPrompt: "你是一个很有用的智能体助手",
    model: "deepseek-chat",
    allowedTools: [],
    allowedKbs: [],
    chatOptions: {
      temperature: 0.7,
      topP: 1.0,
      messageLength: 20,
    },
    ragConfig: {
      topK: 10,
      mode: "hybrid" as RagMode,
    },
  });

  const [createAgentLoading, setCreateAgentLoading] = useState(false);

  // 当编辑的 agent 变化时，更新表单数据
  useEffect(() => {
    if (editingAgent) {
      setFormData({
        name: editingAgent.name,
        description: editingAgent.description || "",
        systemPrompt: editingAgent.systemPrompt || "",
        model: editingAgent.model,
        allowedTools: editingAgent.allowedTools || [],
        allowedKbs: editingAgent.allowedKbs || [],
        chatOptions: editingAgent.chatOptions || {
          temperature: 0.7,
          topP: 1.0,
          messageLength: 10,
        },
        ragConfig: editingAgent.ragConfig || {
          topK: 10,
          mode: "hybrid" as RagMode,
        },
      });
    } else {
      // 重置表单
      setFormData({
        name: "agent",
        description: "",
        systemPrompt: "",
        model: "deepseek-chat",
        allowedTools: [],
        allowedKbs: [],
        chatOptions: {
          temperature: 0.7,
          topP: 1.0,
          messageLength: 10,
        },
        ragConfig: {
          topK: 10,
          mode: "hybrid" as RagMode,
        },
      });
    }
  }, [editingAgent, open]);

  // 获取工具列表
  useEffect(() => {
    async function fetchTools() {
      try {
        const resp = await getOptionalTools();
        setTools(resp.tools);
      } catch (error) {
        console.error("获取工具列表失败:", error);
      }
    }

    fetchTools().then();
  }, []);

  const isEditMode = !!editingAgent;

  const menuItemStyle = (isSelected: boolean) => ({
    background: isSelected ? "rgba(168, 85, 247, 0.08)" : "transparent",
    color: isSelected ? "#7c3aed" : "#8b7fae",
    border: isSelected ? "1px solid rgba(168, 85, 247, 0.15)" : "1px solid transparent",
  });

  const labelStyle = "block font-semibold mb-1";
  const labelColor = { color: "#c4b5fd" };

  const panelVariants = {
    initial: { opacity: 0, x: 12 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: -12 },
    transition: { duration: 0.2, ease: "easeOut" as const },
  };

  return (
    <GlassModal
      open={open}
      onClose={onClose}
      title={isEditMode ? "编辑智能体" : "智能体助手"}
      width={800}
    >
      <div className="flex" style={{ height: "500px" }}>
        {/* Left sidebar menu */}
        <div
          className="h-full"
          style={{
            width: "150px",
            borderRight: "1px solid rgba(168, 85, 247, 0.08)",
            padding: "8px 8px",
          }}
        >
          <div className="flex flex-col gap-1 select-none cursor-pointer">
            {menuItems.map((item) => {
              const isSelected = selectedKey === item.key;
              return (
                <div
                  key={item.key}
                  onClick={() => setSelectedKey(item.key)}
                  className="px-3 py-2 rounded-xl text-sm font-medium transition-all duration-200"
                  style={menuItemStyle(isSelected)}
                >
                  {item.label}
                </div>
              );
            })}
          </div>
        </div>
        {/* Right content */}
        <div className="flex-1 h-full flex flex-col min-h-0">
          <div className="flex-1 px-5 py-2 overflow-y-auto min-h-0">
            <AnimatePresence mode="wait">
              {selectedKey === "base" && (
                <motion.div key="base" {...panelVariants}>
                  <div className="mb-3">
                    <label className={labelStyle} style={labelColor}>名称</label>
                    <div className="flex items-center">
                      <Input
                        placeholder="请输入智能体名称"
                        value={formData.name}
                        onChange={(e) =>
                          setFormData({ ...formData, name: e.target.value })
                        }
                      />
                    </div>
                  </div>
                  <div className="mb-3">
                    <label className={labelStyle} style={labelColor}>描述</label>
                    <TextArea
                      placeholder="请输入智能体描述"
                      rows={2}
                      value={formData.description}
                      onChange={(e) =>
                        setFormData({ ...formData, description: e.target.value })
                      }
                    />
                  </div>
                  <div className="mb-3">
                    <label className={labelStyle} style={labelColor}>提示词</label>
                    <TextArea
                      placeholder="默认提示词"
                      rows={11}
                      value={formData.systemPrompt}
                      onChange={(e) =>
                        setFormData({ ...formData, systemPrompt: e.target.value })
                      }
                    />
                  </div>
                </motion.div>
              )}
              {selectedKey === "model" && (
                <motion.div key="model" {...panelVariants}>
                  <div className="mb-4">
                    <label className={labelStyle} style={labelColor}>选择模型</label>
                    <Select
                      options={[
                        { value: "deepseek-chat", label: "deepseek-chat" },
                        { value: "glm-4.6", label: "glm-4.6" },
                      ]}
                      placeholder="请选择模型"
                      style={{ width: "300px" }}
                      value={formData.model}
                      onChange={(value: ModelType) =>
                        setFormData({ ...formData, model: value })
                      }
                    />
                  </div>
                  <div className="mb-4">
                    <label className={labelStyle} style={labelColor}>模型参数</label>
                    <div className="space-y-4">
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <label className="block text-sm text-purple-200">
                            Temperature（温度）
                            <span className="text-purple-400 ml-1 text-xs">(0.0 - 2.0)</span>
                          </label>
                          <span className="text-sm font-semibold min-w-[40px] text-right" style={{ color: "#7c3aed" }}>
                            {formData?.chatOptions?.temperature?.toFixed(1)}
                          </span>
                        </div>
                        <Slider
                          min={0}
                          max={2}
                          step={0.1}
                          value={formData?.chatOptions?.temperature}
                          onChange={(value) =>
                            setFormData({
                              ...formData,
                              chatOptions: { ...formData.chatOptions, temperature: value },
                            })
                          }
                        />
                      </div>
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <label className="block text-sm text-purple-200">
                            Top P（核采样）
                            <span className="text-purple-400 ml-1 text-xs">(0.0 - 1.0)</span>
                          </label>
                          <span className="text-sm font-semibold min-w-[40px] text-right" style={{ color: "#7c3aed" }}>
                            {formData?.chatOptions?.topP?.toFixed(1)}
                          </span>
                        </div>
                        <Slider
                          min={0}
                          max={1}
                          step={0.1}
                          value={formData?.chatOptions?.topP}
                          onChange={(value) =>
                            setFormData({
                              ...formData,
                              chatOptions: { ...formData.chatOptions, topP: value },
                            })
                          }
                        />
                      </div>
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <label className="block text-sm text-purple-200">
                            消息窗口长度
                            <span className="text-purple-400 ml-1 text-xs">(1 - 100)</span>
                          </label>
                          <span className="text-sm font-semibold min-w-[40px] text-right" style={{ color: "#7c3aed" }}>
                            {formData?.chatOptions?.messageLength}
                          </span>
                        </div>
                        <Slider
                          min={1}
                          max={100}
                          step={1}
                          value={formData?.chatOptions?.messageLength}
                          onChange={(value) =>
                            setFormData({
                              ...formData,
                              chatOptions: { ...formData.chatOptions, messageLength: value },
                            })
                          }
                        />
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}

              {selectedKey === "knowledge" && (
                <motion.div key="knowledge" {...panelVariants}>
                  <div className="mb-4">
                    <label className={labelStyle} style={labelColor}>知识库</label>
                    <p className="text-sm text-purple-300 mb-4">
                      选择智能体可以访问的知识库，支持多选（最多10个）
                    </p>
                    {knowledgeBases.length === 0 ? (
                      <div className="text-center py-8 text-purple-400">
                        <p>暂无知识库，请先创建知识库</p>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {knowledgeBases.map((kb) => {
                          const kbId = kb.knowledgeBaseId;
                          const isSelected = formData.allowedKbs?.includes(kbId);
                          return (
                            <div
                              key={kbId}
                              className="border rounded-xl p-4 cursor-pointer transition-all duration-200"
                              style={{
                                background: isSelected ? "rgba(147, 51, 234, 0.2)" : "rgba(30, 20, 50, 0.5)",
                                borderColor: isSelected ? "rgba(147, 51, 234, 0.5)" : "rgba(100, 80, 150, 0.3)",
                                backdropFilter: "blur(12px)",
                              }}
                              onClick={() => {
                                const currentKbs = formData.allowedKbs || [];
                                if (isSelected) {
                                  setFormData({
                                    ...formData,
                                    allowedKbs: currentKbs.filter((k) => k !== kbId),
                                  });
                                } else {
                                  if (currentKbs.length >= 10) return;
                                  setFormData({
                                    ...formData,
                                    allowedKbs: [...currentKbs, kbId],
                                  });
                                }
                              }}
                            >
                              <div className="flex items-start gap-2">
                                <Checkbox
                                  checked={isSelected}
                                  onChange={(e) => {
                                    e.stopPropagation();
                                    const currentKbs = formData.allowedKbs || [];
                                    if (e.target.checked) {
                                      if (currentKbs.length >= 10) return;
                                      setFormData({
                                        ...formData,
                                        allowedKbs: [...currentKbs, kbId],
                                      });
                                    } else {
                                      setFormData({
                                        ...formData,
                                        allowedKbs: currentKbs.filter((k) => k !== kbId),
                                      });
                                    }
                                  }}
                                  className="mr-3"
                                />
                                <div className="flex-1">
                                  <div className="flex items-center mb-1">
                                    <span className="font-semibold text-purple-100">{kb.name}</span>
                                  </div>
                                  {kb.description && (
                                    <p className="text-sm text-purple-300">{kb.description}</p>
                                  )}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                  <div>
                    <label className={labelStyle} style={labelColor}>检索设置</label>
                    <p className="text-sm text-purple-300 mb-4">配置知识库检索的行为参数</p>
                    <div className="space-y-4">
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <label className="block text-sm text-purple-200">
                            检索数量（Top-K）
                            <span className="text-purple-400 ml-1 text-xs">(1 - 20)</span>
                          </label>
                          <span className="text-sm font-semibold min-w-[40px] text-right" style={{ color: "#7c3aed" }}>
                            {formData?.ragConfig?.topK ?? 10}
                          </span>
                        </div>
                        <Slider
                          min={1}
                          max={20}
                          step={1}
                          value={formData?.ragConfig?.topK ?? 10}
                          onChange={(value) =>
                            setFormData({
                              ...formData,
                              ragConfig: { ...formData.ragConfig, topK: value },
                            })
                          }
                        />
                      </div>
                      <div>
                        <label className="block text-sm text-purple-200 mb-2">检索模式</label>
                        <Select<RagMode>
                          options={[
                            { value: "vector", label: "纯向量检索" },
                            { value: "hybrid", label: "混合检索（向量 + BM25）" },
                            { value: "hybrid-rerank", label: "混合检索 + Rerank" },
                          ]}
                          style={{ width: "100%" }}
                          value={formData?.ragConfig?.mode ?? "hybrid"}
                          onChange={(value: RagMode) =>
                            setFormData({
                              ...formData,
                              ragConfig: { ...formData.ragConfig, mode: value },
                            })
                          }
                        />
                        <p className="text-xs text-purple-400 mt-2">
                          {formData?.ragConfig?.mode === "vector" &&
                            "仅使用向量相似度检索，速度快但可能遗漏关键词匹配"}
                          {formData?.ragConfig?.mode === "hybrid" &&
                            "向量检索 + BM25 全文检索通过 RRF 融合，日常问答和演示推荐的快速默认模式"}
                          {formData?.ragConfig?.mode === "hybrid-rerank" &&
                            "混合检索后再通过 Cross-Encoder 重排序，适合高质量模式，命中率更高但速度较慢"}
                        </p>
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}
              {selectedKey === "tools" && (
                <motion.div key="tools" {...panelVariants}>
                  <div className="mb-4">
                    <label className={labelStyle} style={labelColor}>工具调用</label>
                    <p className="text-sm text-purple-300 mb-4">
                      选择智能体可以使用的工具，支持多选
                    </p>
                    {tools.length === 0 ? (
                      <div className="text-center py-8 text-purple-400">
                        <p>暂无可用工具</p>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {tools.map((tool) => {
                          const toolId = tool.name;
                          const isSelected = formData.allowedTools?.includes(toolId);
                          return (
                            <div
                              key={toolId}
                              className="border rounded-xl p-4 cursor-pointer transition-all duration-200"
                              style={{
                                background: isSelected ? "rgba(147, 51, 234, 0.2)" : "rgba(30, 20, 50, 0.5)",
                                borderColor: isSelected ? "rgba(147, 51, 234, 0.5)" : "rgba(100, 80, 150, 0.3)",
                                backdropFilter: "blur(12px)",
                              }}
                              onClick={() => {
                                const currentTools = formData.allowedTools || [];
                                if (isSelected) {
                                  setFormData({
                                    ...formData,
                                    allowedTools: currentTools.filter((t) => t !== toolId),
                                  });
                                } else {
                                  setFormData({
                                    ...formData,
                                    allowedTools: [...currentTools, toolId],
                                  });
                                }
                              }}
                            >
                              <div className="flex items-start gap-2">
                                <Checkbox
                                  checked={isSelected}
                                  onChange={(e) => {
                                    e.stopPropagation();
                                    const currentTools = formData.allowedTools || [];
                                    if (e.target.checked) {
                                      setFormData({
                                        ...formData,
                                        allowedTools: [...currentTools, toolId],
                                      });
                                    } else {
                                      setFormData({
                                        ...formData,
                                        allowedTools: currentTools.filter((t) => t !== toolId),
                                      });
                                    }
                                  }}
                                  className="mr-3"
                                />
                                <div className="flex-1">
                                  <div className="flex items-center mb-1">
                                    <span className="font-semibold text-purple-100">{tool.name}</span>
                                  </div>
                                  <p className="text-sm text-purple-300">{tool.description}</p>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
          <div
            className="flex justify-end px-5 py-3"
            style={{ borderTop: "1px solid rgba(168, 85, 247, 0.08)" }}
          >
            <Button
              type="primary"
              icon={<SaveOutlined />}
              loading={createAgentLoading}
              disabled={!formData.name.trim()}
              style={{
                background: "linear-gradient(135deg, #c084fc, #a78bfa)",
                border: "none",
                borderRadius: "12px",
                fontWeight: 600,
                boxShadow: "0 4px 12px rgba(168, 85, 247, 0.25)",
              }}
              onClick={async () => {
                if (!formData.name.trim()) return;
                setCreateAgentLoading(true);
                try {
                  if (isEditMode && editingAgent && updateAgentHandle) {
                    await updateAgentHandle(editingAgent.id, formData);
                  } else {
                    await createAgentHandle(formData);
                  }
                  onClose();
                } finally {
                  setCreateAgentLoading(false);
                }
              }}
            >
              {isEditMode ? "更新" : "保存"}
            </Button>
          </div>
        </div>
      </div>
    </GlassModal>
  );
};

export default AddAgentModal;
