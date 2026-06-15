package com.marrine.jchatmind.service.impl;

import com.marrine.jchatmind.mapper.GraphRagMapper;
import com.marrine.jchatmind.model.entity.ChunkBgeM3;
import com.marrine.jchatmind.model.entity.ChunkEntityMention;
import com.marrine.jchatmind.model.entity.EntityRelation;
import com.marrine.jchatmind.model.entity.KnowledgeEntity;
import com.marrine.jchatmind.model.vo.ScoredChunk;
import com.marrine.jchatmind.service.GraphRagService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
@Slf4j
public class GraphRagServiceImpl implements GraphRagService {

    private static final int MAX_ENTITIES_PER_CHUNK = 12;
    private static final Pattern EXACT_ENTITY_PATTERN = Pattern.compile("[A-Za-z][A-Za-z0-9_-]{1,}|\\d+(?:\\.\\d+)+|[\u300a\u201c\"']([^\u300b\u201d\"']{2,32})[\u300b\u201d\"']");
    private static final Pattern DOMAIN_TERM_PATTERN = Pattern.compile("[\\u4e00-\\u9fa5A-Za-z0-9_-]{2,32}(?:协议|系统|模型|算法|框架|技术|理论|数据库|知识库|智能体|向量|图谱|检索|重排|实体|关系|项目|公司)");

    private final GraphRagMapper graphRagMapper;

    public GraphRagServiceImpl(GraphRagMapper graphRagMapper) {
        this.graphRagMapper = graphRagMapper;
    }

    @Override
    @Transactional(propagation = Propagation.NOT_SUPPORTED)
    public void ensureSchema() {
        try {
            graphRagMapper.ensurePgCryptoExtension();
            graphRagMapper.ensureKnowledgeEntityTable();
            graphRagMapper.ensureChunkEntityMentionTable();
            graphRagMapper.ensureEntityRelationTable();
            graphRagMapper.ensureKnowledgeEntityIndexes();
            graphRagMapper.ensureChunkEntityMentionIndexes();
            graphRagMapper.ensureEntityRelationIndexes();
            log.info("GraphRAG-lite schema is ready");
        } catch (Exception e) {
            log.error("Failed to initialize GraphRAG-lite schema", e);
        }
    }

    @Override
    public void indexChunk(String kbId, String docId, String chunkId, String title, String content) {
        if (!StringUtils.hasText(kbId) || !StringUtils.hasText(docId) || !StringUtils.hasText(chunkId)) {
            return;
        }
        List<String> entityNames = extractEntities(title, content);
        if (entityNames.size() < 2) {
            return;
        }

        LocalDateTime now = LocalDateTime.now();
        List<KnowledgeEntity> entities = new ArrayList<>();
        for (String name : entityNames) {
            KnowledgeEntity entity = findOrCreateEntity(kbId, name, now);
            if (entity == null || !StringUtils.hasText(entity.getId())) {
                continue;
            }
            entities.add(entity);
            graphRagMapper.insertMention(ChunkEntityMention.builder()
                    .kbId(kbId)
                    .docId(docId)
                    .chunkId(chunkId)
                    .entityId(entity.getId())
                    .entityName(entity.getName())
                    .createdAt(now)
                    .build());
        }

        entities.sort(Comparator.comparing(KnowledgeEntity::getName));
        for (int i = 0; i < entities.size(); i++) {
            for (int j = i + 1; j < entities.size(); j++) {
                graphRagMapper.insertRelation(EntityRelation.builder()
                        .kbId(kbId)
                        .sourceEntityId(entities.get(i).getId())
                        .targetEntityId(entities.get(j).getId())
                        .relationType("CO_OCCURS_WITH")
                        .sourceChunkId(chunkId)
                        .docId(docId)
                        .weight(1)
                        .createdAt(now)
                        .updatedAt(now)
                        .build());
            }
        }
        log.debug("Indexed GraphRAG-lite chunk: chunkId={}, entities={}", chunkId, entities.size());
    }

    @Override
    public void deleteDocumentGraph(String docId) {
        if (!StringUtils.hasText(docId)) {
            return;
        }
        graphRagMapper.deleteRelationsByDocumentId(docId);
        graphRagMapper.deleteMentionsByDocumentId(docId);
    }

    @Override
    public List<ScoredChunk> expandRelatedChunks(String kbId, List<ScoredChunk> seedChunks, int maxHops, int limit) {
        if (!StringUtils.hasText(kbId) || seedChunks == null || seedChunks.isEmpty() || limit <= 0) {
            return List.of();
        }
        List<String> seedChunkIds = seedChunks.stream()
                .map(ScoredChunk::getId)
                .filter(StringUtils::hasText)
                .distinct()
                .limit(8)
                .toList();
        if (seedChunkIds.isEmpty()) {
            return List.of();
        }

        int safeHops = Math.max(1, Math.min(maxHops, 2));
        List<ChunkBgeM3> chunks = graphRagMapper.expandRelatedChunks(kbId, seedChunkIds, safeHops, limit);
        Map<String, ScoredChunk> unique = new LinkedHashMap<>();
        for (int i = 0; i < chunks.size(); i++) {
            ChunkBgeM3 chunk = chunks.get(i);
            unique.putIfAbsent(chunk.getId(), ScoredChunk.builder()
                    .id(chunk.getId())
                    .kbId(chunk.getKbId())
                    .docId(chunk.getDocId())
                    .content(chunk.getContent())
                    .metadata(chunk.getMetadata())
                    .source("graph")
                    .score(1.0 / (80 + i + 1))
                    .build());
        }
        return List.copyOf(unique.values());
    }

    List<String> extractEntities(String title, String content) {
        Set<String> entities = new LinkedHashSet<>();
        collectMatches(entities, EXACT_ENTITY_PATTERN, title);
        collectMatches(entities, EXACT_ENTITY_PATTERN, content);
        collectMatches(entities, DOMAIN_TERM_PATTERN, title);
        collectMatches(entities, DOMAIN_TERM_PATTERN, content);
        return entities.stream()
                .map(this::normalizeEntity)
                .filter(StringUtils::hasText)
                .filter(entity -> entity.length() >= 2 && entity.length() <= 40)
                .distinct()
                .limit(MAX_ENTITIES_PER_CHUNK)
                .toList();
    }

    private KnowledgeEntity findOrCreateEntity(String kbId, String name, LocalDateTime now) {
        KnowledgeEntity existing = graphRagMapper.selectEntityByName(kbId, name);
        if (existing != null) {
            return existing;
        }
        KnowledgeEntity entity = KnowledgeEntity.builder()
                .kbId(kbId)
                .name(name)
                .type(typeOf(name))
                .createdAt(now)
                .updatedAt(now)
                .build();
        graphRagMapper.insertEntity(entity);
        return graphRagMapper.selectEntityByName(kbId, name);
    }

    private void collectMatches(Set<String> entities, Pattern pattern, String text) {
        if (!StringUtils.hasText(text) || entities.size() >= MAX_ENTITIES_PER_CHUNK) {
            return;
        }
        Matcher matcher = pattern.matcher(text);
        while (matcher.find() && entities.size() < MAX_ENTITIES_PER_CHUNK) {
            String value = matcher.groupCount() >= 1 && matcher.group(1) != null ? matcher.group(1) : matcher.group();
            entities.add(value);
        }
    }

    private String normalizeEntity(String entity) {
        if (entity == null) {
            return "";
        }
        return entity.replaceAll("[\\s\\u3000]+", " ")
                .replaceAll("^[\\p{Punct}\\u3001\\u3002\\uff0c\\uff1a]+|[\\p{Punct}\\u3001\\u3002\\uff0c\\uff1a]+$", "")
                .trim();
    }

    private String typeOf(String entity) {
        if (entity.matches(".*\\d.*") || entity.matches("[A-Za-z][A-Za-z0-9_-]{1,}")) {
            return "TERM";
        }
        if (entity.endsWith("公司")) {
            return "ORG";
        }
        if (entity.endsWith("项目")) {
            return "PROJECT";
        }
        return "CONCEPT";
    }
}
