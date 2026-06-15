package com.marrine.jchatmind.service;

import com.marrine.jchatmind.model.vo.ScoredChunk;

import java.util.List;

public interface GraphRagService {
    void ensureSchema();

    void indexChunk(String kbId, String docId, String chunkId, String title, String content);

    void deleteDocumentGraph(String docId);

    List<ScoredChunk> expandRelatedChunks(String kbId, List<ScoredChunk> seedChunks, int maxHops, int limit);
}
