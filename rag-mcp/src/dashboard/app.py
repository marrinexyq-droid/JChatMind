from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.dashboard.service import DashboardService


def run_app(settings_path: Path) -> None:
    try:
        import streamlit as st
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Streamlit is not installed. Install the dashboard extra before "
            "starting the UI: pip install -e .[dashboard]"
        ) from exc

    service = DashboardService(settings_path)
    st.set_page_config(page_title="rag-mcp dashboard", layout="wide")
    st.title("rag-mcp dashboard")

    page = st.sidebar.radio(
        "Page",
        [
            "Overview",
            "Data Browser",
            "Ingestion Manager",
            "Ingestion Traces",
            "Query Traces",
            "Evaluation Panel",
        ],
    )

    if page == "Overview":
        _render_overview(st, service)
    elif page == "Data Browser":
        _render_data_browser(st, service)
    elif page == "Ingestion Manager":
        _render_ingestion_manager(st, service)
    elif page == "Ingestion Traces":
        _render_traces(st, service, "ingestion")
    elif page == "Query Traces":
        _render_traces(st, service, "query")
    elif page == "Evaluation Panel":
        _render_evaluation(st, service)


def _render_overview(st: Any, service: DashboardService) -> None:
    overview = service.overview()
    columns = st.columns(4)
    columns[0].metric("Collections", overview.collection_count)
    columns[1].metric("Documents", overview.document_count)
    columns[2].metric("Chunks", overview.chunk_count)
    columns[3].metric("Traces", overview.trace_count)

    st.subheader("Operational Snapshot")
    st.json(asdict(overview))


def _render_data_browser(st: Any, service: DashboardService) -> None:
    collections = service.list_collections()
    st.subheader("Collections")
    st.dataframe([asdict(item) for item in collections], use_container_width=True)

    names = ["all", *[item.name for item in collections]]
    selected = st.selectbox("Collection", names)
    collection = None if selected == "all" else selected
    st.subheader("Chunks")
    st.dataframe(
        [asdict(item) for item in service.list_chunks(collection=collection, limit=200)],
        use_container_width=True,
    )


def _render_ingestion_manager(st: Any, service: DashboardService) -> None:
    st.subheader("Indexed Documents")
    collections = service.list_collections()
    names = ["all", *[item.name for item in collections]]
    selected = st.selectbox("Collection", names)
    collection = None if selected == "all" else selected
    st.dataframe(
        [asdict(item) for item in service.list_documents(collection=collection)],
        use_container_width=True,
    )


def _render_traces(st: Any, service: DashboardService, trace_type: str) -> None:
    st.subheader(f"{trace_type.title()} Traces")
    traces = service.list_traces(trace_type=trace_type, limit=200)
    st.dataframe([asdict(item) for item in traces], use_container_width=True)


def _render_evaluation(st: Any, service: DashboardService) -> None:
    st.subheader("Latest Evaluation Report")
    report = service.latest_evaluation_report()
    if report is None:
        st.info("No JSON evaluation report found.")
        return
    st.write(str(report.path))
    st.json(
        {
            "total_cases": report.total_cases,
            "split_counts": report.split_counts,
            "retrieval_metric_count": report.retrieval_metric_count,
        }
    )
    st.dataframe(report.raw.get("retrieval_metrics", []), use_container_width=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the rag-mcp Streamlit dashboard.")
    parser.add_argument(
        "--settings",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "config" / "settings.yaml",
    )
    args = parser.parse_args()
    run_app(args.settings)


if __name__ == "__main__":
    main()
