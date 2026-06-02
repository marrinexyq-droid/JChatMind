import React, { useState } from "react";
import { Button, Input } from "antd";
import TextArea from "antd/es/input/TextArea";
import { SaveOutlined } from "@ant-design/icons";
import { motion } from "framer-motion";
import GlassModal from "./GlassModal.tsx";
import { type CreateKnowledgeBaseRequest } from "../../api/api.ts";

interface AddKnowledgeBaseModalProps {
  open: boolean;
  onClose: () => void;
  createKnowledgeBaseHandle: (
    request: CreateKnowledgeBaseRequest,
  ) => Promise<void>;
}

const AddKnowledgeBaseModal: React.FC<AddKnowledgeBaseModalProps> = ({
  open,
  onClose,
  createKnowledgeBaseHandle,
}) => {
  const [formData, setFormData] = useState<CreateKnowledgeBaseRequest>({
    name: "",
    description: "",
  });

  const [createLoading, setCreateLoading] = useState(false);

  const handleSubmit = async () => {
    if (!formData.name.trim()) {
      return;
    }
    setCreateLoading(true);

    try {
      await createKnowledgeBaseHandle(formData);
      // 重置表单
      setFormData({
        name: "",
        description: "",
      });
      onClose();
    } finally {
      setCreateLoading(false);
    }
  };

  const handleCancel = () => {
    // 重置表单
    setFormData({
      name: "",
      description: "",
    });
    onClose();
  };

  const labelStyle = "block font-semibold mb-2";
  const labelColor = { color: "#c4b5fd" };

  return (
    <GlassModal
      open={open}
      onClose={handleCancel}
      title="新建知识库"
      width={600}
    >
      <motion.div
        className="py-4 px-6"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1, duration: 0.25 }}
      >
        <div className="mb-4">
          <label className={labelStyle} style={labelColor}>
            名称 <span className="text-red-400">*</span>
          </label>
          <Input
            placeholder="请输入知识库名称"
            value={formData.name}
            onChange={(e) =>
              setFormData({ ...formData, name: e.target.value })
            }
            onPressEnter={handleSubmit}
          />
        </div>
        <div className="mb-6">
          <label className={labelStyle} style={labelColor}>描述</label>
          <TextArea
            placeholder="请输入知识库描述（可选）"
            rows={4}
            value={formData.description}
            onChange={(e) =>
              setFormData({ ...formData, description: e.target.value })
            }
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button
            onClick={handleCancel}
            style={{
              borderRadius: "12px",
              border: "1px solid rgba(168, 85, 247, 0.2)",
            }}
          >
            取消
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            loading={createLoading}
            onClick={handleSubmit}
            disabled={!formData.name.trim()}
            style={{
              background: "linear-gradient(135deg, #c084fc, #a78bfa)",
              border: "none",
              borderRadius: "12px",
              fontWeight: 600,
              boxShadow: "0 4px 12px rgba(168, 85, 247, 0.25)",
            }}
          >
            创建
          </Button>
        </div>
      </motion.div>
    </GlassModal>
  );
};

export default AddKnowledgeBaseModal;
