package com.kama.jchatmind.service;

import com.kama.jchatmind.model.vo.ScoredChunk;

import java.util.List;

/**
 * Cross-Encoder Reranking 服务接口
 */
public interface RerankService {

    /**
     * 对候选结果进行重排序
     *
     * @param query      用户查询
     * @param candidates 候选 chunks
     * @param topK       返回 topK 个结果
     * @return 重排后的结果
     */
    List<ScoredChunk> rerank(String query, List<ScoredChunk> candidates, int topK);
}
