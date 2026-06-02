import React, { useMemo } from "react";
import { Button, Divider, Dropdown, Modal } from "antd";
import type { MenuProps } from "antd";
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  MoreOutlined,
} from "@ant-design/icons";
import type { AgentVO } from "../../api/api.ts";
import { formatDateTime, getAgentEmoji } from "../../utils";

interface AgentTabContentProps {
  agents: AgentVO[];
  onCreateAgentClick: () => void;
  onSelectAgent: (agentId: string) => void;
  onEditAgent?: (agent: AgentVO) => void;
  onDeleteAgent?: (agentId: string) => void;
}

const AgentTabContent: React.FC<AgentTabContentProps> = ({
  agents,
  onCreateAgentClick,
  onSelectAgent,
  onEditAgent,
  onDeleteAgent,
}) => {
  // 为每个 agent 生成 emoji
  const agentsWithEmoji = useMemo(() => {
    return agents.map((agent) => ({
      ...agent,
      emoji: getAgentEmoji(agent.id),
    }));
  }, [agents]);

  // 创建右键菜单
  const getContextMenuItems = (agent: AgentVO): MenuProps["items"] => {
    const items: MenuProps["items"] = [];

    if (onEditAgent) {
      items.push({
        key: "edit",
        label: "编辑",
        icon: <EditOutlined />,
        onClick: (e) => {
          e.domEvent.stopPropagation();
          onEditAgent(agent);
        },
      });
    }

    if (onDeleteAgent) {
      items.push({
        key: "delete",
        label: "删除",
        icon: <DeleteOutlined />,
        danger: true,
        onClick: (e) => {
          e.domEvent.stopPropagation();
          Modal.confirm({
            title: "确定要删除这个智能体吗？",
            content: "删除后将无法恢复",
            okText: "确定",
            cancelText: "取消",
            okType: "danger",
            onOk: () => {
              onDeleteAgent(agent.id);
            },
          });
        },
      });
    }

    return items;
  };

  return (
    <div className="flex flex-col h-full">
      <Button
        color="purple"
        variant="filled"
        icon={<PlusOutlined />}
        onClick={onCreateAgentClick}
        className="w-full"
        style={{
          background: "linear-gradient(135deg, rgba(192, 132, 252, 0.25), rgba(240, 171, 252, 0.2))",
          border: "1px solid rgba(192, 132, 252, 0.3)",
          fontWeight: 600,
        }}
      >
        智能体助手
      </Button>
      <Divider />
      <div className="flex-1 overflow-y-auto rounded-xl p-1.5">
        {agents.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-purple-400">
            <p className="text-sm">暂无智能体</p>
            <p className="text-xs mt-1">点击上方按钮添加</p>
          </div>
        ) : (
          <div className="space-y-1.5">
            {agentsWithEmoji.map((agent) => {
              const menuItems = getContextMenuItems(agent);
              const hasMenu = menuItems && menuItems.length > 0;
              return (
                <div
                  key={agent.id}
                  onClick={() => onSelectAgent(agent.id)}
                  className="w-full px-3 py-3 rounded-xl cursor-pointer transition-all duration-200 ease-out group relative glass-solid glass-hover"
                  style={{
                    transition: "all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1)",
                  }}
                >
                  <div className="flex items-start gap-3">
                    <div
                      className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 text-lg mt-0.5"
                      style={{
                        background: "linear-gradient(135deg, #f0abfc 0%, #c084fc 50%, #a78bfa 100%)",
                        boxShadow: "0 2px 8px rgba(168, 85, 247, 0.2)",
                      }}
                    >
                      {agent.emoji}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-purple-100 truncate text-sm">
                        {agent.name}
                      </div>
                      {agent.description && (
                        <div className="text-xs text-purple-300 mt-1 line-clamp-1">
                          {agent.description}
                        </div>
                      )}
                      {agent.updatedAt && (
                        <div className="text-xs text-purple-400 mt-1">
                          {formatDateTime(agent.updatedAt)}
                        </div>
                      )}
                    </div>
                    {hasMenu && (
                      <div
                        onClick={(e) => e.stopPropagation()}
                        onContextMenu={(e) => e.stopPropagation()}
                        className="opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                      >
                        <Dropdown
                          menu={{ items: menuItems }}
                          trigger={["contextMenu", "click"]}
                          placement="bottomRight"
                        >
                          <Button
                            type="text"
                            size="small"
                            icon={<MoreOutlined />}
                            onClick={(e) => e.stopPropagation()}
                            className="text-purple-400 hover:text-purple-500"
                          />
                        </Dropdown>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default AgentTabContent;
