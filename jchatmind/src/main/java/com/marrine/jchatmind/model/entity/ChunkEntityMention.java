package com.marrine.jchatmind.model.entity;

import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@Builder
public class ChunkEntityMention {
    private String id;
    private String kbId;
    private String docId;
    private String chunkId;
    private String entityId;
    private String entityName;
    private LocalDateTime createdAt;
}
