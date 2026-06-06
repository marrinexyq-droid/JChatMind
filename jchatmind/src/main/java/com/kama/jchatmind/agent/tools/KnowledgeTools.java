package com.kama.jchatmind.agent.tools;

import com.kama.jchatmind.model.vo.QueryPlan;
import com.kama.jchatmind.model.vo.RagSearchResult;
import com.kama.jchatmind.model.vo.ScoredChunk;
import com.kama.jchatmind.service.QueryPlanner;
import com.kama.jchatmind.service.RagService;
import com.kama.jchatmind.service.RagTraceContext;
import org.springframework.stereotype.Component;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.util.StringUtils;

import java.util.List;

@Component
public class KnowledgeTools implements Tool {

    private final RagService ragService;
    private final QueryPlanner queryPlanner;

    public KnowledgeTools(RagService ragService, QueryPlanner queryPlanner) {
        this.ragService = ragService;
        this.queryPlanner = queryPlanner;
    }

    @Override
    public String getName() {
        return "KnowledgeTool";
    }

    @Override
    public String getDescription() {
        return "Search the knowledge base with hybrid retrieval: vector search, BM25, RRF fusion, and rerank.";
    }

    @Override
    public ToolType getType() {
        return ToolType.FIXED;
    }

    @org.springframework.ai.tool.annotation.Tool(
            name = "KnowledgeTool",
            description = "Search a specified knowledge base. Parameters are kbsId, query, and optional context for follow-up questions. Returns retrieved chunks marked as [C1], [C2], etc.; cite those markers in the final answer."
    )
    public String knowledgeQuery(
            @ToolParam(description = "Knowledge base ID to search") String kbsId,
            @ToolParam(description = "User question or search query") String query,
            @ToolParam(required = false, description = "Previous topic for follow-up questions") String context) {
        if (!StringUtils.hasLength(kbsId) || !StringUtils.hasLength(query)) {
            return "Invalid parameters: kbsId and query cannot be empty.";
        }

        QueryPlan queryPlan = queryPlanner.plan(query, context);
        RagSearchResult searchResult = ragService.hybridSearchWithTrace(kbsId, queryPlan);
        RagTraceContext.set(searchResult.getTrace());
        List<ScoredChunk> results = searchResult.getChunks();

        if (results == null || results.isEmpty()) {
            return "No relevant content found.";
        }

        StringBuilder sb = new StringBuilder();
        sb.append("Use the following retrieved chunks as evidence. ")
                .append("When answering with information from a chunk, cite the matching marker like [C1].\n\n");

        for (int i = 0; i < results.size(); i++) {
            ScoredChunk chunk = results.get(i);
            sb.append(String.format("[C%d] (source: %s, score: %.4f, docId: %s)%n%s%n",
                    i + 1,
                    chunk.getSource(),
                    chunk.getScore(),
                    chunk.getDocId(),
                    chunk.getContent()));
            if (i < results.size() - 1) {
                sb.append("\n---\n\n");
            }
        }
        return sb.toString();
    }

    public String knowledgeQuery(String kbsId, String query) {
        return knowledgeQuery(kbsId, query, null);
    }
}
