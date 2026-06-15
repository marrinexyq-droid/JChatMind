package com.marrine.jchatmind.service;

import com.marrine.jchatmind.model.vo.QueryPlan;
import com.marrine.jchatmind.model.vo.RagSearchResult;
import com.marrine.jchatmind.model.vo.SelfRagEvaluation;

public interface SelfRagEvaluator {
    SelfRagEvaluation evaluate(QueryPlan queryPlan, RagSearchResult searchResult, int retryCount);

    QueryPlan remediate(QueryPlan queryPlan, SelfRagEvaluation evaluation);
}
