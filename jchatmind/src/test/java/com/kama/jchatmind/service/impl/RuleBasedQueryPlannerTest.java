package com.kama.jchatmind.service.impl;

import com.kama.jchatmind.model.vo.QueryPlan;
import com.kama.jchatmind.model.vo.QueryType;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class RuleBasedQueryPlannerTest {

    private final RuleBasedQueryPlanner planner = new RuleBasedQueryPlanner();

    @Test
    void plansFactQueryAsHybrid() {
        QueryPlan plan = planner.plan("BB84\u534f\u8bae\u662f\u4ec0\u4e48\uff1f", null);

        assertEquals(QueryType.FACT, plan.getQueryType());
        assertEquals("hybrid", plan.getMode());
        assertEquals(5, plan.getTopK());
        assertEquals(20, plan.getCandidatePoolSize());
    }

    @Test
    void plansSummaryQueryWithLargerRecall() {
        QueryPlan plan = planner.plan("\u603b\u7ed3\u4e00\u4e0b\u91cf\u5b50\u7ea0\u7f20\u7684\u6838\u5fc3\u8981\u70b9", null);

        assertEquals(QueryType.SUMMARY, plan.getQueryType());
        assertEquals("hybrid-rerank", plan.getMode());
        assertEquals(10, plan.getTopK());
        assertEquals(40, plan.getCandidatePoolSize());
    }

    @Test
    void plansComparisonQuery() {
        QueryPlan plan = planner.plan("BB84\u548cE91\u534f\u8bae\u6709\u4ec0\u4e48\u533a\u522b\uff1f", null);

        assertEquals(QueryType.COMPARISON, plan.getQueryType());
        assertEquals("hybrid-rerank", plan.getMode());
        assertEquals(8, plan.getTopK());
        assertEquals(30, plan.getCandidatePoolSize());
    }

    @Test
    void exactTermsIncreaseBm25Weight() {
        QueryPlan plan = planner.plan("HQ-9B \u7cfb\u7edf\u7684\u53c2\u6570\u662f\u4ec0\u4e48\uff1f", null);

        assertTrue(plan.getBm25Weight() > plan.getVectorWeight());
        assertEquals("hybrid-rerank", plan.getMode());
    }

    @Test
    void contextIsPrependedForFollowUpQuery() {
        QueryPlan plan = planner.plan("\u5b83\u7684\u5b89\u5168\u6027\u600e\u4e48\u6837\uff1f", "E91\u534f\u8bae");

        assertEquals("E91\u534f\u8bae \u5b83\u7684\u5b89\u5168\u6027\u600e\u4e48\u6837\uff1f", plan.getSearchQuery());
    }
}
