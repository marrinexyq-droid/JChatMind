package com.marrine.jchatmind.service;

import com.marrine.jchatmind.model.vo.QueryPlan;

public interface QueryPlanner {
    QueryPlan plan(String query, String context);
}
