from src.evaluation.metrics import mrr, ndcg_at_k, precision_at_k, recall_at_k


def test_recall_at_k_counts_ground_truth_hits():
    assert recall_at_k(["a", "b"], ["x", "a", "c"], 2) == 0.5


def test_precision_at_k_counts_top_k_hits():
    assert precision_at_k(["a", "b"], ["a", "x", "b"], 2) == 0.5


def test_mrr_returns_first_relevant_rank():
    assert mrr(["b"], ["a", "b", "c"]) == 0.5


def test_ndcg_is_one_for_ideal_order():
    assert ndcg_at_k(["a", "b"], ["a", "b"], 2) == 1.0
