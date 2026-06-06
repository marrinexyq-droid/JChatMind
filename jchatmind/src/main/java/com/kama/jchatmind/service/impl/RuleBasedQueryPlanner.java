package com.kama.jchatmind.service.impl;

import com.kama.jchatmind.model.vo.QueryPlan;
import com.kama.jchatmind.model.vo.QueryType;
import com.kama.jchatmind.service.QueryPlanner;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.List;
import java.util.regex.Pattern;

@Service
public class RuleBasedQueryPlanner implements QueryPlanner {

    private static final List<String> SUMMARY_TERMS = List.of(
            "\u603b\u7ed3", "\u6982\u62ec", "\u68b3\u7406", "\u6709\u54ea\u4e9b", "\u6574\u4f53", "\u8981\u70b9"
    );
    private static final List<String> COMPARISON_TERMS = List.of(
            "\u5bf9\u6bd4", "\u6bd4\u8f83", "\u533a\u522b", "\u5dee\u5f02", "\u76f8\u540c", "\u4e0d\u540c",
            "vs", "VS", "\u4f18\u7f3a\u70b9"
    );
    private static final List<String> MULTI_HOP_TERMS = List.of(
            "\u4e3a\u4ec0\u4e48", "\u5982\u4f55\u5f71\u54cd", "\u5173\u7cfb", "\u539f\u56e0",
            "\u5bfc\u81f4", "\u5f71\u54cd", "\u5173\u8054", "\u8054\u7cfb"
    );
    private static final List<String> HIGH_PRECISION_TERMS = List.of(
            "\u51c6\u786e", "\u539f\u6587", "\u7f16\u53f7", "\u54ea\u4e00\u6761", "\u53c2\u6570",
            "\u5b9a\u4e49", "\u51fa\u5904", "\u6765\u6e90", "\u5f15\u7528"
    );
    private static final Pattern EXACT_TERM_PATTERN = Pattern.compile(
            ".*([A-Za-z]{2,}[-_]?\\d*[A-Za-z0-9]*|\\d+(\\.\\d+)+|\\d{2,}|[\u300a\u201c\\\"'][^\u300b\u201d\\\"']+[\u300b\u201d\\\"']).*"
    );

    @Override
    public QueryPlan plan(String query, String context) {
        String normalizedQuery = normalize(query);
        String normalizedContext = normalize(context);
        String searchQuery = buildSearchQuery(normalizedQuery, normalizedContext);

        QueryType queryType = classify(normalizedQuery);
        boolean highPrecision = containsAny(normalizedQuery, HIGH_PRECISION_TERMS);
        boolean exactTerm = hasExactTerm(normalizedQuery);

        String mode = queryType == QueryType.FACT && !highPrecision ? "hybrid" : "hybrid-rerank";
        int topK = switch (queryType) {
            case SUMMARY -> 10;
            case COMPARISON, MULTI_HOP -> 8;
            case FACT -> 5;
        };
        int candidatePoolSize = switch (queryType) {
            case SUMMARY, MULTI_HOP -> 40;
            case COMPARISON -> 30;
            case FACT -> 20;
        };

        return QueryPlan.builder()
                .originalQuery(normalizedQuery)
                .context(normalizedContext)
                .searchQuery(searchQuery)
                .queryType(queryType)
                .mode(mode)
                .topK(topK)
                .candidatePoolSize(candidatePoolSize)
                .vectorWeight(1.0)
                .bm25Weight(exactTerm ? 1.5 : 1.0)
                .build();
    }

    private QueryType classify(String query) {
        if (containsAny(query, SUMMARY_TERMS)) {
            return QueryType.SUMMARY;
        }
        if (containsAny(query, COMPARISON_TERMS)) {
            return QueryType.COMPARISON;
        }
        if (containsAny(query, MULTI_HOP_TERMS) || looksMultiHop(query)) {
            return QueryType.MULTI_HOP;
        }
        return QueryType.FACT;
    }

    private String buildSearchQuery(String query, String context) {
        if (!StringUtils.hasText(context)) {
            return query;
        }
        if (!StringUtils.hasText(query)) {
            return context;
        }
        if (query.contains(context) || context.contains(query)) {
            return query;
        }
        return context + " " + query;
    }

    private boolean looksMultiHop(String query) {
        int separatorCount = 0;
        for (char c : query.toCharArray()) {
            if (c == '\uff0c' || c == ',' || c == '\u3001' || c == ';' || c == '\uff1b') {
                separatorCount++;
            }
        }
        return separatorCount >= 2;
    }

    private boolean hasExactTerm(String query) {
        return EXACT_TERM_PATTERN.matcher(query).matches();
    }

    private boolean containsAny(String query, List<String> terms) {
        for (String term : terms) {
            if (query.contains(term)) {
                return true;
            }
        }
        return false;
    }

    private String normalize(String text) {
        if (!StringUtils.hasText(text)) {
            return "";
        }
        return text.replaceAll("\\s+", " ").trim();
    }
}
