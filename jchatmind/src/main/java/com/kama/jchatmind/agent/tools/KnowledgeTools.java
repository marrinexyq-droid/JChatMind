package com.kama.jchatmind.agent.tools;

import com.kama.jchatmind.model.vo.ScoredChunk;
import com.kama.jchatmind.service.RagService;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import java.util.List;

@Component
public class KnowledgeTools implements Tool {

    private final RagService ragService;

    public KnowledgeTools(RagService ragService) {
        this.ragService = ragService;
    }

    @Override
    public String getName() {
        return "KnowledgeTool";
    }

    @Override
    public String getDescription() {
        return "从知识库执行混合检索（向量 + BM25 + Rerank）。输入知识库 ID 和查询文本，返回最相关的知识片段。";
    }

    @Override
    public ToolType getType() {
        return ToolType.FIXED;
    }

    @org.springframework.ai.tool.annotation.Tool(
            name = "KnowledgeTool",
            description = "从指定知识库中执行混合检索（Hybrid RAG: 向量检索 + BM25全文检索 + Cross-Encoder Rerank）。参数为知识库 ID（kbsId）和查询文本（query），返回与查询最相关的知识片段。"
    )
    public String knowledgeQuery(String kbsId, String query) {
        if (!StringUtils.hasLength(kbsId) || !StringUtils.hasLength(query)) {
            return "参数错误：kbsId 和 query 不能为空";
        }

        List<ScoredChunk> results = ragService.hybridSearch(kbsId, query, 5, "hybrid-rerank");

        if (results == null || results.isEmpty()) {
            return "未找到相关内容";
        }

        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < results.size(); i++) {
            ScoredChunk chunk = results.get(i);
            sb.append(String.format("[%d] (来源: %s, 相关度: %.4f)\n%s\n",
                    i + 1,
                    chunk.getSource(),
                    chunk.getScore(),
                    chunk.getContent()));
            if (i < results.size() - 1) {
                sb.append("\n---\n\n");
            }
        }
        return sb.toString();
    }
}
