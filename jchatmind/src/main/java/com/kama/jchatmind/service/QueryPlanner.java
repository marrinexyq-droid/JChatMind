package com.kama.jchatmind.service;

import com.kama.jchatmind.model.vo.QueryPlan;

public interface QueryPlanner {
    QueryPlan plan(String query, String context);
}
