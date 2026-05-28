# 04 — RAG 知识库（检索增强生成）

> 相关文件：`RagServiceImpl.java`, `MarkdownParserServiceImpl.java`, `DocumentFacadeServiceImpl.java`, `ChunkBgeM3Mapper.xml`, `KnowledgeTools.java`

---

## 一、RAG 全链路总览

```
文档上传
  │
  ▼
1. Markdown 解析（MarkdownParserServiceImpl）
   ├─ Flexmark 解析 → 按标题分块
   └─ 输出 List<MarkdownSection>{title, content}
      │
      ▼
2. Embedding 生成（RagServiceImpl）
   ├─ POST localhost:11434/api/embeddings
   ├─ 模型: bge-m3 (1024维)
   └─ 输出 float[1024]
      │
      ▼
3. 向量存储（ChunkBgeM3Mapper）
   ├─ INSERT INTO chunk_bge_m3 (content, embedding VECTOR(1024), ...)
   └─ ivfflat 索引加速检索
      │
      ▼
   ─── 用户提问时 ───
      │
      ▼
4. 查询向量化
   ├─ doEmbed(userQuery) → float[1024]
   └─ toPgVector() → "[0.1,0.2,...]"
      │
      ▼
5. 相似度检索（pgvector）
   ├─ SELECT ... ORDER BY embedding <-> query_vector LIMIT 3
   ├─ 运算符 <-> = L2 距离
   └─ 返回 Top-3 最相似 chunk
      │
      ▼
6. Agent 使用（KnowledgeTools）
   ├─ Agent 调 KnowledgeTool(kbId, query)
   └─ 检索结果拼入上下文 → LLM 参考回答
```

---

## 二、Markdown 文档解析与分块

### MarkdownParserServiceImpl.java

```java
@Service
public class MarkdownParserServiceImpl implements MarkdownParserService {

    private final Parser parser;  // Flexmark 解析器

    public MarkdownParserServiceImpl() {
        MutableDataSet options = new MutableDataSet();
        this.parser = Parser.builder(options).build();
    }

    public List<MarkdownSection> parseMarkdown(InputStream inputStream) {
        // 1. 读取文件全部内容
        originalMarkdownContent = new String(inputStream.readAllBytes(), StandardCharsets.UTF_8);

        // 2. Flexmark 解析为 AST
        Document document = parser.parse(originalMarkdownContent);

        // 3. 提取章节（按标题分块）
        List<MarkdownSection> sections = new ArrayList<>();
        extractSections(document, sections);
        return sections;
    }
}
```

### Chunk 策略：按 Markdown 标题分块

```java
private void extractSections(Document document, List<MarkdownSection> sections) {
    // 1. 收集所有顶层节点
    List<Node> topLevelNodes = document.getFirstChild() → ... 全部子节点

    // 2. 遍历，找到 Heading 节点
    for (int i = 0; i < topLevelNodes.size(); i++) {
        Node node = topLevelNodes.get(i);

        if (node instanceof Heading) {
            String title = extractHeadingText(heading);  // 标题文本

            // 3. 收集当前标题到下一个标题之间的所有内容
            StringBuilder content = new StringBuilder();
            for (int j = i + 1; j < topLevelNodes.size(); j++) {
                if (nextNode instanceof Heading) break;  // 遇到下一个标题就停
                content.append(extractNodeContent(nextNode));
            }

            sections.add(new MarkdownSection(title, content.toString()));
        }
    }
}
```

**Chunk 策略的优缺点**：
- ✅ 简单、可理解、按语义自然分块
- ✅ 保留标题作为检索粒度
- ❌ 没有重叠窗口（上下文边界生硬）
- ❌ 只处理顶层标题，不支持嵌套结构
- ❌ 大标题下的内容可能过长（超过 LLM 上下文）

---

## 三、Embedding 生成

### RagServiceImpl.java

```java
@Service
public class RagServiceImpl implements RagService {

    private final WebClient webClient;  // 调 Ollama 的 HTTP 客户端

    public RagServiceImpl(WebClient.Builder builder, ChunkBgeM3Mapper chunkBgeM3Mapper) {
        this.webClient = builder.baseUrl("http://localhost:11434").build();
        //                                          ↑ 本地 Ollama 服务
    }

    // ⭐ 核心：调 Ollama 生成 embedding
    private float[] doEmbed(String text) {
        EmbeddingResponse resp = webClient.post()
                .uri("/api/embeddings")
                .bodyValue(Map.of(
                        "model", "bge-m3",     // BGE-M3 模型
                        "prompt", text           // 要 embedding 的文本
                ))
                .retrieve()
                .bodyToMono(EmbeddingResponse.class)
                .block();                        // 同步阻塞等待
        return resp.getEmbedding();              // float[1024]
    }

    // 公开方法
    public float[] embed(String text) {
        return doEmbed(text);
    }

    // 相似度检索
    public List<String> similaritySearch(String kbId, String title) {
        // 1. 把用户查询也做 embedding
        String queryEmbedding = toPgVector(doEmbed(title));
        // 2. SQL 查询
        List<ChunkBgeM3> chunks = chunkBgeM3Mapper.similaritySearch(
                kbId, queryEmbedding, 3);   // 返回 Top3
        // 3. 只返回文本内容
        return chunks.stream().map(ChunkBgeM3::getContent).toList();
    }

    // float[] → "[0.1,0.2,...]" → pgvector 语法
    private String toPgVector(float[] v) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < v.length; i++) {
            sb.append(v[i]);
            if (i < v.length - 1) sb.append(",");
        }
        sb.append("]");
        return sb.toString();
    }
}
```

**为什么选 bge-m3？**
- 1024 维，中英文跨语言语义都好
- 可以通过 Ollama 本地部署（免费、低延迟、无数据泄露）
- BGE-M3 支持多种检索方式（Dense + Sparse + Multi-Vector）

---

## 四、向量存储与检索

### 数据库设计（`chunk_bge_m3` 表）

```sql
CREATE TABLE chunk_bge_m3 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kb_id UUID NOT NULL REFERENCES knowledge_base(id) ON DELETE CASCADE,
    doc_id UUID NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    content TEXT NOT NULL,                     -- 切片后的文本
    metadata JSONB,                            -- 扩展信息
    embedding VECTOR(1024) NOT NULL,           -- bge-m3 模型输出 1024 维向量
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ivfflat 索引（近似最近邻搜索）
CREATE INDEX idx_chunk_embedding
ON chunk_bge_m3
USING ivfflat (embedding vector_l2_ops)
WITH (lists = 100);
```

### 向量检索 SQL（ChunkBgeM3Mapper.xml）

```xml
<select id="similaritySearch" resultMap="BaseResultMap">
    SELECT id, kb_id, doc_id, content, ...
    FROM chunk_bge_m3
    WHERE kb_id = CAST(#{kbId} AS uuid)              <!-- 按知识库过滤 -->
    ORDER BY embedding <-> #{vectorLiteral}::vector   <!-- L2距离排序 -->
    LIMIT #{limit}                                    <!-- 返回 Top3 -->
</select>
```

**`<->` 运算符说明：**
- `<->` = L2 距离（欧几里得距离），值越小越相似
- `<#>` = 余弦距离
- `<=>` = L1 距离（曼哈顿距离）

**ivfflat 索引说明：**
- **ivfflat** = Inverted File with Flat Compression（倒排文件 + 扁平压缩）
- 工作方式：用 K-Means 聚类把向量空间分成 100 个列表（lists=100）
- 检索时：只搜索最近的几个列表（probes 参数控制），而不是全量搜索
- **优缺点**：
  - ✅ 比暴力搜索快很多
  - ✅ 适合 10 万 ~ 100 万级别
  - ❌ 精度不如 HNSW
  - ❌ 需要调参（lists, probes）

---

## 五、文档上传触发 RAG 的完整流程

### DocumentFacadeServiceImpl.uploadDocument()

```java
public CreateDocumentResponse uploadDocument(String kbId, MultipartFile file) {
    // 1. 提取文件信息
    String originalFilename = file.getOriginalFilename();
    String filetype = getFileType(originalFilename);  // "md"
    long fileSize = file.getSize();

    // 2. 创建文档数据库记录（获取 documentId）
    Document document = documentConverter.toEntity(documentDTO);
    documentMapper.insert(document);

    // 3. 保存文件到磁盘
    String filePath = documentStorageService.saveFile(kbId, documentId, file);

    // 4. 更新 metadata（记录文件路径）
    // ...

    // 5. ⭐ 如果是 Markdown 文件，触发 RAG 处理
    if ("md".equalsIgnoreCase(filetype)) {
        processMarkdownDocument(kbId, documentId, filePath);
    } else {
        log.warn("待新增处理的文件类型: {}", filetype);
        // 目前只支持 md，不支持 PDF/TXT 等
    }
}
```

### processMarkdownDocument() — RAG 处理核心

```java
private void processMarkdownDocument(String kbId, String documentId, String filePath) {
    // 1. 读取文件 → 解析 Markdown → 按标题分块
    List<MarkdownSection> sections = markdownParserService.parseMarkdown(inputStream);

    // 2. 遍历每个章节
    for (MarkdownSection section : sections) {
        String title = section.getTitle();
        String content = section.getContent();

        // 3. 对标题做 embedding（不是对内容！）
        float[] embedding = ragService.embed(title);

        // 4. 存储 chunk
        ChunkBgeM3 chunk = ChunkBgeM3.builder()
                .kbId(kbId)
                .docId(documentId)
                .content(content)
                .embedding(embedding)
                .build();
        chunkBgeM3Mapper.insert(chunk);
    }
}
```

**注意**：这里是对**标题**做 embedding 而不是对内容。这意味着：
- 检索时用户查"天气" → embedding → 找标题相似的 chunk
- 如果标题不包含查询词，即使内容相关也可能检不到
- 改进方向：标题 + 内容拼接做 embedding，或分别 embedding 后加权平均

---

## 六、Agent 如何使用知识库

### KnowledgeTools.java

```java
@Tool(name = "KnowledgeTool",
      description = "从指定知识库中执行相似性检索（RAG）...")
public String knowledgeQuery(String kbsId, String query) {
    List<String> strings = ragService.similaritySearch(kbsId, query);
    return String.join("\n", strings);
}
```

Agent 在 Think 阶段判断是否需要查知识库：
1. LLM 认为缺少上下文 → 调 `KnowledgeTool(kbId, query)`
2. 工具执行 → `ragService.similaritySearch(kbId, query)`
3. 返回相似文本片段
4. 下一轮 Think → LLM 参考检索结果回答用户

### thinkPrompt 中的知识库信息

```java
// JChatMind.think() 第232行
String thinkPrompt = """
    ...
    【额外信息】
    - 你目前拥有的知识库列表以及描述：%s
    """.formatted(this.availableKbs);
    //                 ↑ 把知识库信息告诉 LLM
    //                   如: [{id:'kb1', name:'产品文档', description:'产品使用说明'}]
```

---

## 七、数据库全部 6 张表关系

```
agent ───→ chat_session ───→ chat_message
  │                            (session_id FK, cascade)
  │
  └── allowed_kbs (JSONB) ──→ knowledge_base
                                │
                                └── document
                                     │ (kb_id FK, cascade)
                                     │
                                     └── chunk_bge_m3
                                          (kb_id FK, doc_id FK, cascade)
```

---

## 八、面试核心问题

### Q1: RAG 全链路是怎样的？

文档上传 → Markdown解析分块 → Ollama bge-m3 embedding → 存储到 pgvector → 用户查询时同样 embedding → SQL 向量检索（L2距离）→ Top-3 结果返回给 LLM。

### Q2: 为什么选 pgvector 而不是 Milvus/Pinecone？

- 部署简单：一套 PostgreSQL 搞定所有数据（结构化 + 向量），不需要额外维护一个向量数据库
- 事务一致性：向量数据和业务数据在同一个事务中
- 成本低：开源、免费
- 有成熟的索引（ivfflat, HNSW）
- 缺点：大规模（百万级以上）性能不如专用向量库

### Q3: Chunk 策略是什么？有什么改进空间？

当前：按 Markdown 标题分块（单层，不嵌套）。
改进：
1. 重叠窗口（overlap）：相邻 chunk 共享部分内容，避免边界截断
2. 标题+内容联合 embedding：而不是只对标题 embedding
3. 多粒度检索：先用标题检索，再在结果内细粒度匹配
4. 语义分块：用 LLM 或 NLP 技术按语义边界分块

### Q4: ivfflat 和 HNSW 的区别？

ivfflat：K-Means 聚类 + 倒排索引。速度快，精度略低，适合 10 万级。
HNSW：分层可导航小世界图。精度高，但构建慢、内存占用大，适合百万级。

### Q5: 如果知识库里有 100 万条 chunk，性能怎么样？

ivfflat 在适当调参（lists 和 probes）下，100 万级仍然可用。如果需要更高性能，可以切换为 HNSW 索引。

### Q6: 这个 RAG 链路有什么不足？

1. 只支持 Markdown 文件
2. Chunk 策略过于简单（无重叠、无嵌套）
3. 只对标题 embedding（内容遗漏）
4. 检索结果没有重排序（rerank）
5. 没有评估检索质量的指标（recall/precision）
