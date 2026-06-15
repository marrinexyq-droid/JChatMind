"""
RAG v2 评估配置文件
"""
import os

# ====== 数据库 ======
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "jchatmind",
    "user": "postgres",
    "password": os.getenv("DB_PASSWORD", "123456"),
}

# ====== 服务地址 ======
OLLAMA_BASE = "http://localhost:11434"
OLLAMA_MODEL = "bge-m3"
RERANKER_BASE = "http://127.0.0.1:8001"

# ====== LLM (智谱 GLM) ======
ZHIPUAI_API_KEY = os.getenv(
    "ZHIPUAI_API_KEY",
    "3a14463a544f4c80844dd18a563a9d8b.bo4YX6sBjstlHwoD",
)
ZHIPUAI_MODEL = "glm-4.6v"

# ====== 评估参数 ======
CANDIDATE_POOL_SIZE = int(os.getenv("POOL_SIZE", "20"))
RRF_K = int(os.getenv("RRF_K", "60"))
EMBED_MODE = os.getenv("EMBED_MODE", "heading+body")  # "heading+body" | "heading-only"
TOP_K_LIST = [1, 3, 5, 10]
EVAL_MODES = ["vector", "hybrid", "hybrid-rerank", "adaptive-rag"]

# ====== 路径 ======
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
QUERIES_FILE = os.path.join(DATA_DIR, "queries.json")
RAW_DIR = os.path.join(OUTPUT_DIR, "raw_results")
METRICS_DIR = os.path.join(OUTPUT_DIR, "metrics")

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(METRICS_DIR, exist_ok=True)
