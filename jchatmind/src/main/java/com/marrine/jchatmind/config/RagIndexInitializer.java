package com.marrine.jchatmind.config;

import com.marrine.jchatmind.service.RagService;
import com.marrine.jchatmind.service.GraphRagService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

/**
 * 应用启动时自动初始化 RAG 数据库索引
 */
@Component
@Slf4j
@RequiredArgsConstructor
public class RagIndexInitializer {

    private final RagService ragService;
    private final GraphRagService graphRagService;

    @EventListener(ApplicationReadyEvent.class)
    public void onApplicationReady() {
        log.info("RAG 索引初始化开始...");
        ragService.ensureIndexes();
        graphRagService.ensureSchema();
        log.info("RAG 索引初始化完成");
    }
}
