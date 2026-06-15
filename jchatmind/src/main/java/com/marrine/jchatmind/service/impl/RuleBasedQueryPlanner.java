package com.marrine.jchatmind.service.impl;

import com.marrine.jchatmind.config.RagStrategyProperties;
import com.marrine.jchatmind.model.vo.QueryPlan;
import com.marrine.jchatmind.model.vo.QueryType;
import com.marrine.jchatmind.service.QueryPlanner;
import org.springframework.beans.factory.annotation.Autowired;
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
    private static final List<String> RERANK_TERMS = List.of(
            "\u9ad8\u8d28\u91cf", "\u7cbe\u6392", "\u91cd\u6392", "\u6700\u51c6\u786e", "rerank", "Rerank", "RERANK"
    );
    private static final List<String> HIGH_PRECISION_TERMS = List.of(
            "\u51c6\u786e", "\u539f\u6587", "\u7f16\u53f7", "\u54ea\u4e00\u6761", "\u53c2\u6570",
            "\u5b9a\u4e49", "\u51fa\u5904", "\u6765\u6e90", "\u5f15\u7528"
    );
    private static final Pattern EXACT_TERM_PATTERN = Pattern.compile(
            ".*([A-Za-z]{2,}[-_]?\\d*[A-Za-z0-9]*|\\d+(\\.\\d+)+|\\d{2,}|[\u300a\u201c\\\"'][^\u300b\u201d\\\"']+[\u300b\u201d\\\"']).*"
    );

    private final RagStrategyProperties strategyProperties;

    public RuleBasedQueryPlanner() {
        this(new RagStrategyProperties());
    }

    @Autowired
    public RuleBasedQueryPlanner(RagStrategyProperties strategyProperties) {
        this.strategyProperties = strategyProperties;
    }

    @Override
    public QueryPlan plan(String query, String context) {
        String normalizedQuery = normalize(query);
        String normalizedContext = normalize(context);
        String searchQuery = buildSearchQuery(normalizedQuery, normalizedContext);

        QueryType queryType = classify(normalizedQuery);
        boolean exactTerm = hasExactTerm(normalizedQuery);
        boolean highPrecision = containsAny(normalizedQuery, HIGH_PRECISION_TERMS);
        RagStrategyProperties.Strategy strategy = strategyProperties.strategyFor(queryType);

        String mode = strategy.getMode();
        if (containsAny(normalizedQuery, RERANK_TERMS) || highPrecision) {
            mode = "hybrid-rerank";
        }
        double bm25Weight = exactTerm ? Math.max(strategy.getBm25Weight(), 1.5) : strategy.getBm25Weight();

        return QueryPlan.builder()
                .originalQuery(normalizedQuery)
                .context(normalizedContext)
                .searchQuery(searchQuery)
                .queryType(queryType)
                .mode(mode)
                .topK(strategy.getTopK())
                .candidatePoolSize(strategy.getCandidatePoolSize())
                .vectorWeight(strategy.getVectorWeight())
                .bm25Weight(bm25Weight)
                .graphExpansionEnabled(strategy.getGraphExpansionEnabled())
                .graphMaxHops(strategy.getGraphMaxHops())
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
