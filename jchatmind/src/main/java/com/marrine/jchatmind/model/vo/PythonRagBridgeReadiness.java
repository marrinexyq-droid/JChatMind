package com.marrine.jchatmind.model.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PythonRagBridgeReadiness {
    private boolean ready;
    private String serverName;
    private String serverVersion;
    private List<String> tools;
    private List<String> collections;
    private Map<String, Integer> collectionChunkCounts;
    private int totalChunks;
    private String message;
}
