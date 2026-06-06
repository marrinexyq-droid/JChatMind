package com.kama.jchatmind.service;

import com.kama.jchatmind.model.vo.RagTrace;

public final class RagTraceContext {
    private static final ThreadLocal<RagTrace> LATEST_TRACE = new ThreadLocal<>();

    private RagTraceContext() {
    }

    public static void set(RagTrace trace) {
        LATEST_TRACE.set(trace);
    }

    public static RagTrace consume() {
        RagTrace trace = LATEST_TRACE.get();
        LATEST_TRACE.remove();
        return trace;
    }
}
