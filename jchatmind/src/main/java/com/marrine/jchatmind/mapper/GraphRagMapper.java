package com.marrine.jchatmind.mapper;

import com.marrine.jchatmind.model.entity.ChunkBgeM3;
import com.marrine.jchatmind.model.entity.ChunkEntityMention;
import com.marrine.jchatmind.model.entity.EntityRelation;
import com.marrine.jchatmind.model.entity.KnowledgeEntity;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface GraphRagMapper {
    void ensurePgCryptoExtension();

    void ensureKnowledgeEntityTable();

    void ensureChunkEntityMentionTable();

    void ensureEntityRelationTable();

    void ensureKnowledgeEntityIndexes();

    void ensureChunkEntityMentionIndexes();

    void ensureEntityRelationIndexes();

    KnowledgeEntity selectEntityByName(@Param("kbId") String kbId, @Param("name") String name);

    int insertEntity(KnowledgeEntity entity);

    int insertMention(ChunkEntityMention mention);

    int insertRelation(EntityRelation relation);

    int deleteRelationsByDocumentId(@Param("docId") String docId);

    int deleteMentionsByDocumentId(@Param("docId") String docId);

    List<ChunkBgeM3> expandRelatedChunks(
            @Param("kbId") String kbId,
            @Param("seedChunkIds") List<String> seedChunkIds,
            @Param("maxHops") int maxHops,
            @Param("limit") int limit
    );
}
