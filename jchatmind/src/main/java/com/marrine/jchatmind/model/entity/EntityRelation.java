package com.marrine.jchatmind.model.entity;

import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@Builder
public class EntityRelation {
    private String id;
    private String kbId;
    private String sourceEntityId;
    private String targetEntityId;
    private String relationType;
    private String sourceChunkId;
    private String docId;
    private Integer weight;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
