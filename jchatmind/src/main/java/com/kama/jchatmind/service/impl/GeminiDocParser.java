package com.kama.jchatmind.service.impl;

import com.kama.jchatmind.service.MarkdownParserService.MarkdownSection;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * Gemini 格式文档解析器。
 * 处理带有 ====== 父切片 / ------ 子切片 标记的文档，
 * 每篇文档产出 3 个 MarkdownSection（Intro / Child / Conclusion）。
 */
@Service
@Slf4j
public class GeminiDocParser {

    public List<MarkdownSection> parseGeminiFormat(InputStream inputStream) {
        List<String> lines;
        try {
            lines = new BufferedReader(new InputStreamReader(inputStream, StandardCharsets.UTF_8))
                    .lines()
                    .toList();
        } catch (Exception e) {
            log.error("读取 Gemini 格式文档失败", e);
            throw new RuntimeException("读取文档失败: " + e.getMessage(), e);
        }

        String title = "Untitled";
        StringBuilder introBuf = new StringBuilder();
        StringBuilder childBuf = new StringBuilder();
        StringBuilder conclusionBuf = new StringBuilder();

        String childTitle = "Child Chunk";

        enum State { BEFORE_PARENT, INTRO, CHILD, CONCLUSION, DONE }
        State state = State.BEFORE_PARENT;

        for (String rawLine : lines) {
            String line = rawLine.trim();
            if (line.isEmpty()) continue;

            if (line.startsWith("# ====== 父切片开始")) {
                state = State.INTRO;
                continue;
            }
            if (line.startsWith("# ====== 父切片结束")) {
                state = State.DONE;
                continue;
            }
            if (line.startsWith("# ------ 子切片嵌套")) {
                state = State.CHILD;
                continue;
            }
            if (line.startsWith("# ------ 子切片嵌套结束")) {
                state = State.CONCLUSION;
                continue;
            }

            // 提取 Title 元数据
            if (line.startsWith("# Title:") && title.equals("Untitled")) {
                title = line.substring("# Title:".length()).trim();
                continue;
            }
            // 跳过 ID/Level（所有状态）
            if (line.startsWith("# ID:") || line.startsWith("# Level:")) {
                continue;
            }

            // Tags/Hypothetical_Questions 仅在 Child 状态保留到正文
            if ((line.startsWith("# Tags:") || line.startsWith("# Hypothetical_Questions:"))) {
                if (state == State.CHILD) {
                    childBuf.append(line).append("\n");  // 保留到子切片正文
                }
                continue;
            }

            // 正文收集
            switch (state) {
                case INTRO -> introBuf.append(line).append("\n");
                case CHILD -> {
                    childBuf.append(line).append("\n");
                    if (childTitle.equals("Child Chunk") && !line.startsWith("#") && line.length() > 10) {
                        childTitle = line.substring(0, Math.min(line.length(), 60)).trim();
                    }
                }
                case CONCLUSION -> conclusionBuf.append(line).append("\n");
            }
        }

        List<MarkdownSection> sections = new ArrayList<>();

        String introText = introBuf.toString().trim();
        if (!introText.isEmpty()) {
            sections.add(new MarkdownSection(title + "（简介）", introText));
        }

        String childText = childBuf.toString().trim();
        if (!childText.isEmpty()) {
            sections.add(new MarkdownSection(childTitle, childText));
        }

        String conclusionText = conclusionBuf.toString().trim();
        if (!conclusionText.isEmpty()) {
            sections.add(new MarkdownSection(title + "（总结）", conclusionText));
        }

        log.info("Gemini 格式解析完成: 共 {} 个 chunk (title={})", sections.size(), title);
        return sections;
    }
}
