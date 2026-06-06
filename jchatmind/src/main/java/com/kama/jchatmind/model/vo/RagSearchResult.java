package com.kama.jchatmind.model.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class RagSearchResult {
    private List<ScoredChunk> chunks;
    private RagTrace trace;
}
