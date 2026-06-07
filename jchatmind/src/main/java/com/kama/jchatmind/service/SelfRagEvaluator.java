package com.kama.jchatmind.service;

import com.kama.jchatmind.model.vo.QueryPlan;
import com.kama.jchatmind.model.vo.RagSearchResult;
import com.kama.jchatmind.model.vo.SelfRagEvaluation;

public interface SelfRagEvaluator {
    SelfRagEvaluation evaluate(QueryPlan queryPlan, RagSearchResult searchResult, int retryCount);

    QueryPlan remediate(QueryPlan queryPlan, SelfRagEvaluation evaluation);
}
