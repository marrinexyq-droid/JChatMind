package com.kama.jchatmind.service;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.ToString;

import java.io.InputStream;
import java.util.List;

/**
 * Markdown 解析服务接口
 */
public interface MarkdownParserService {
    /**
     * 解析标准 Markdown 文件，按标题分块
     */
    List<MarkdownSection> parseMarkdown(InputStream inputStream);

    /**
     * 解析 Gemini 格式文档（====== 父切片 / ------ 子切片 标记），用于 RAG 评估
     * 默认不支持，由 GeminiDocParser 实现
     */
    default List<MarkdownSection> parseGeminiFormat(InputStream inputStream) {
        throw new UnsupportedOperationException(
                "Gemini format parsing requires GeminiDocParser. " +
                "Use parseMarkdown() for standard markdown files.");
    }
    
    /**
     * Markdown 章节数据类
     */
    @Data
    @AllArgsConstructor
    @ToString
    class MarkdownSection {
        private String title;
        private String content;
    }
}
