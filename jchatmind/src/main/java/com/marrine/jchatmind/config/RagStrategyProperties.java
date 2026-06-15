package com.marrine.jchatmind.config;

import com.marrine.jchatmind.model.vo.QueryType;
import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.util.EnumMap;
import java.util.Map;

@Data
@Component
@ConfigurationProperties(prefix = "rag.strategy")
public class RagStrategyProperties {

    private Map<QueryType, Strategy> types = defaultStrategies();

    public Strategy strategyFor(QueryType queryType) {
        QueryType safeType = queryType == null ? QueryType.FACT : queryType;
        Strategy configured = types == null ? null : types.get(safeType);
        return configured == null ? defaultStrategies().get(safeType) : configured.withDefaults(defaultStrategies().get(safeType));
    }

    private static Map<QueryType, Strategy> defaultStrategies() {
        Map<QueryType, Strategy> defaults = new EnumMap<>(QueryType.class);
        defaults.put(QueryType.FACT, new Strategy("hybrid", 5, 20, 1.0, 1.0, false, 1));
        defaults.put(QueryType.SUMMARY, new Strategy("hybrid", 10, 40, 1.0, 1.0, false, 1));
        defaults.put(QueryType.COMPARISON, new Strategy("hybrid-rerank", 8, 30, 1.0, 1.2, false, 1));
        defaults.put(QueryType.MULTI_HOP, new Strategy("hybrid-rerank", 8, 40, 1.0, 1.2, true, 2));
        return defaults;
    }

    @Data
    public static class Strategy {
        private String mode;
        private Integer topK;
        private Integer candidatePoolSize;
        private Double vectorWeight;
        private Double bm25Weight;
        private Boolean graphExpansionEnabled;
        private Integer graphMaxHops;

        public Strategy() {
        }

        Strategy(String mode,
                 Integer topK,
                 Integer candidatePoolSize,
                 Double vectorWeight,
                 Double bm25Weight,
                 Boolean graphExpansionEnabled,
                 Integer graphMaxHops) {
            this.mode = mode;
            this.topK = topK;
            this.candidatePoolSize = candidatePoolSize;
            this.vectorWeight = vectorWeight;
            this.bm25Weight = bm25Weight;
            this.graphExpansionEnabled = graphExpansionEnabled;
            this.graphMaxHops = graphMaxHops;
        }

        Strategy withDefaults(Strategy defaults) {
            Strategy merged = new Strategy();
            merged.mode = hasText(mode) ? mode : defaults.mode;
            merged.topK = positive(topK) ? topK : defaults.topK;
            merged.candidatePoolSize = positive(candidatePoolSize) ? candidatePoolSize : defaults.candidatePoolSize;
            merged.vectorWeight = positive(vectorWeight) ? vectorWeight : defaults.vectorWeight;
            merged.bm25Weight = positive(bm25Weight) ? bm25Weight : defaults.bm25Weight;
            merged.graphExpansionEnabled = graphExpansionEnabled == null ? defaults.graphExpansionEnabled : graphExpansionEnabled;
            merged.graphMaxHops = positive(graphMaxHops) ? graphMaxHops : defaults.graphMaxHops;
            return merged;
        }

        private boolean hasText(String value) {
            return value != null && !value.trim().isEmpty();
        }

        private boolean positive(Number value) {
            return value != null && value.doubleValue() > 0;
        }
    }
}
