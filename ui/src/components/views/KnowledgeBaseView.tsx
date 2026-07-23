import { useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Card, Typography, Button, Upload, Table, Popconfirm, Space, message, Empty,
} from "antd";
import {
  BookOutlined, UploadOutlined, DeleteOutlined, FileOutlined, PlusOutlined,
} from "@ant-design/icons";
import type { UploadProps } from "antd";
import { useKnowledgeBases } from "../../hooks/useKnowledgeBases.ts";
import { useDocuments } from "../../hooks/useDocuments.ts";
import { uploadDocument, type DocumentVO } from "../../api/api.ts";
import { getKnowledgeBaseEmoji } from "../../utils";

const { Title, Text, Paragraph } = Typography;

const cardStyle = {
  background: "var(--bg-elevated)",
  border: "1px solid var(--glass-border)",
  borderRadius: "16px",
};

export default function KnowledgeBaseView({ onCreateClick }: { onCreateClick?: () => void }) {
  const { knowledgeBaseId } = useParams<{ knowledgeBaseId?: string }>();
  const navigate = useNavigate();
  const { knowledgeBases } = useKnowledgeBases();
  const { documents, loading, refreshDocuments, deleteDocument } = useDocuments(knowledgeBaseId);
  const [uploading, setUploading] = useState(false);

  const currentKnowledgeBase = useMemo(() => {
    if (!knowledgeBaseId) return null;
    return knowledgeBases.find((kb) => kb.knowledgeBaseId === knowledgeBaseId) || null;
  }, [knowledgeBaseId, knowledgeBases]);

  const handleUpload: UploadProps["customRequest"] = async (options) => {
    const { file, onSuccess, onError } = options;
    if (!knowledgeBaseId) { message.error("请先选择知识库"); return; }
    setUploading(true);
    try {
      await uploadDocument(knowledgeBaseId, file as File);
      message.success("文档上传成功");
      await refreshDocuments();
      onSuccess?.(file);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "上传失败");
      onError?.(error as Error);
    } finally { setUploading(false); }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
  };

  const columns = [
    {
      title: "文件名", dataIndex: "filename", key: "filename",
      render: (text: string) => (
        <Space><FileOutlined style={{ color: "var(--accent-blue)" }} /><span>{text}</span></Space>
      ),
    },
    { title: "类型", dataIndex: "filetype", key: "filetype", width: 120 },
    { title: "大小", dataIndex: "size", key: "size", width: 120, render: (size: number) => formatFileSize(size) },
    {
      title: "操作", key: "action", width: 100,
      render: (_: unknown, record: DocumentVO) => (
        <Popconfirm title="确定要删除这个文档吗？" onConfirm={() => deleteDocument(record.id)}
          okText="确定" cancelText="取消">
          <Button type="text" danger icon={<DeleteOutlined />} size="small">删除</Button>
        </Popconfirm>
      ),
    },
  ];

  // ======== List view ========
  if (!knowledgeBaseId) {
    const kbsWithEmoji = knowledgeBases.map((kb) => ({
      ...kb,
      emoji: getKnowledgeBaseEmoji(kb.knowledgeBaseId),
    }));

    return (
      <div className="flex flex-col h-full p-6 overflow-y-auto">
        <div className="max-w-4xl w-full mx-auto">
          <div className="flex items-center justify-between mb-4">
            <Title level={3} className="m-0" style={{ color: "var(--text-primary)" }}>知识库</Title>
            {onCreateClick && (
              <Button type="primary" icon={<PlusOutlined />} onClick={onCreateClick}
                style={{ borderRadius: "12px", fontWeight: 600 }}>
                新建知识库
              </Button>
            )}
          </div>

          {kbsWithEmoji.length === 0 ? (
            <Empty
              image={<BookOutlined style={{ fontSize: 48, color: "var(--text-muted)" }} />}
              description={<span style={{ color: "var(--text-secondary)" }}>暂无知识库</span>}
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {kbsWithEmoji.map((kb) => (
                <div
                  key={kb.knowledgeBaseId}
                  onClick={() => navigate(`/knowledge-base/${kb.knowledgeBaseId}`)}
                  className="p-4 rounded-2xl cursor-pointer transition-all duration-200"
                  style={cardStyle}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = "rgba(139, 156, 247, 0.3)";
                    e.currentTarget.style.background = "var(--bg-surface)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = "var(--glass-border)";
                    e.currentTarget.style.background = "var(--bg-elevated)";
                  }}
                >
                  <div className="flex items-start gap-3">
                    <div
                      className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 text-lg"
                      style={{
                        background: "linear-gradient(135deg, #8b9cf7 0%, #67e8f9 100%)",
                      }}
                    >
                      {kb.emoji}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>
                        {kb.name}
                      </div>
                      {kb.description && (
                        <div className="text-xs mt-1 line-clamp-2" style={{ color: "var(--text-secondary)" }}>
                          {kb.description}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ======== Detail view ========
  if (!currentKnowledgeBase) {
    return (
      <div className="flex flex-col h-full items-center justify-center p-6">
        <Empty
          description={
            <div className="mt-4">
              <Title level={4} style={{ color: "var(--text-primary)" }}>知识库不存在</Title>
              <Text style={{ color: "var(--text-secondary)" }}>请检查知识库 ID 是否正确</Text>
            </div>
          }
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full p-6 overflow-y-auto">
      <div className="max-w-4xl w-full mx-auto">
        <Card style={cardStyle} className="mb-4">
          <div className="flex items-start gap-4">
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl shrink-0"
              style={{
                background: "linear-gradient(135deg, #8b9cf7 0%, #67e8f9 100%)",
              }}
            >
              <BookOutlined className="text-white" />
            </div>
            <div className="flex-1">
              <Title level={3} className="mb-1" style={{ color: "var(--text-primary)" }}>
                {currentKnowledgeBase.name}
              </Title>
              {currentKnowledgeBase.description && (
                <Paragraph className="mb-0" style={{ color: "var(--text-secondary)" }}>
                  {currentKnowledgeBase.description}
                </Paragraph>
              )}
            </div>
          </div>
        </Card>

        <Card
          title={<span className="font-semibold" style={{ color: "var(--text-primary)" }}>上传文档</span>}
          style={cardStyle} className="mb-4"
        >
          <Upload customRequest={handleUpload} showUploadList={false} accept=".md" disabled={uploading}>
            <Button type="primary" icon={<UploadOutlined />} loading={uploading} size="large"
              style={{ borderRadius: "12px", fontWeight: 600 }}>
              选择文件上传
            </Button>
          </Upload>
          <Text className="block mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
            支持格式: Markdown
          </Text>
        </Card>

        <Card
          title={<span className="font-semibold" style={{ color: "var(--text-primary)" }}>文档列表 ({documents.length})</span>}
          style={cardStyle} className="mb-4"
        >
          {loading ? (
            <div className="text-center py-8"><Text style={{ color: "var(--text-secondary)" }}>加载中...</Text></div>
          ) : documents.length === 0 ? (
            <Empty description={<Text style={{ color: "var(--text-secondary)" }}>暂无文档，请上传文档</Text>} />
          ) : (
            <Table columns={columns} dataSource={documents} rowKey="id"
              pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 条` }} />
          )}
        </Card>
      </div>
    </div>
  );
}
