package com.marrine.jchatmind.model.vo;

public enum SelfRagDecision {
    ACCEPT,
    RETRY_WITH_RERANK,
    RETRY_WITH_LARGER_POOL,
    INSUFFICIENT_EVIDENCE
}
