# 05 — SSE 实时通信

> 相关文件：`SseServiceImpl.java`, `SseController.java`, `SseMessage.java`, `AgentChatView.tsx`

---

## 一、SSE 简介

**SSE = Server-Sent Events**（服务器推送事件）

- 标准：HTML5 规范的一部分
- 协议：基于 HTTP，`Content-Type: text/event-stream`
- 方向：**服务器→客户端单工通信**
- 浏览器 API：`EventSource`
- 对比 WebSocket：SSE 更轻量，WebSocket 支持双向

---

## 二、SSE 连接建立

### 后端（SseController.java）

```java
@RestController
@RequestMapping("/sse")
public class SseController {

    private final SseService sseService;

    // 关键是 produces = MediaType.TEXT_EVENT_STREAM_VALUE
    @RequestMapping(value = "/connect/{chatSessionId}",
                    produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter connect(@PathVariable String chatSessionId) {
        return sseService.connect(chatSessionId);
    }
}
```

### 后端（SseServiceImpl.java）

```java
@Service
public class SseServiceImpl implements SseService {

    // ⭐ 连接管理器：key=chatSessionId, value=SSE连接
    private final ConcurrentMap<String, SseEmitter> clients = new ConcurrentHashMap<>();

    public SseEmitter connect(String chatSessionId) {
        // 1. 创建 SseEmitter（30分钟超时）
        SseEmitter emitter = new SseEmitter(30 * 60 * 1000L);

        // 2. 保存到连接池
        clients.put(chatSessionId, emitter);

        // 3. 发送初始化消息
        emitter.send(SseEmitter.event().name("init").data("connected"));

        // 4. 注册回调：断开/超时/错误时自动清理
        emitter.onCompletion(() -> clients.remove(chatSessionId));
        emitter.onTimeout(() -> clients.remove(chatSessionId));
        emitter.onError((error) -> clients.remove(chatSessionId));

        return emitter;
    }

    public void send(String chatSessionId, SseMessage message) {
        SseEmitter emitter = clients.get(chatSessionId);
        if (emitter != null) {
            String json = objectMapper.writeValueAsString(message);
            emitter.send(SseEmitter.event()
                    .name("message")       // ← 事件名 "message"
                    .data(json));          // ← JSON 数据
        } else {
            throw new RuntimeException("No client found for: " + chatSessionId);
        }
    }
}
```

### 前端（AgentChatView.tsx）

```typescript
useEffect(() => {
    if (!chatSessionId) return;

    // EventSource 自动发送 GET 请求到 SSE 端点
    const baseRoot = BASE_URL.replace("/api", "");
    const es = new EventSource(`${baseRoot}/sse/connect/${chatSessionId}`);

    // 监听 "message" 事件（对应后端的 .name("message")）
    es.addEventListener("message", (event) => {
        const message = JSON.parse(event.data) as SseMessage;

        switch (message.type) {
            case "AI_GENERATED_CONTENT":
                addMessage(message.payload.message);         // 追加到消息列表
                break;
            case "AI_PLANNING":
            case "AI_THINKING":
            case "AI_EXECUTING":
                setDisplayAgentStatus(true);                  // 显示 Agent 状态
                setAgentStatusText(message.payload.statusText);
                setAgentStatusType(message.type);
                break;
            case "AI_DONE":
                setDisplayAgentStatus(false);                 // 隐藏状态
                break;
        }
    });

    // 组件卸载时关闭连接
    return () => es.close();
}, [chatSessionId]);
```

---

## 三、SSE 消息数据结构

### SseMessage.java

```java
@Data
@Builder
public class SseMessage {
    private Type type;          // 消息类型
    private Payload payload;    // 数据体
    private Metadata metadata;  // 元数据

    @Data
    @Builder
    public static class Payload {
        private ChatMessageVO message;    // 消息内容（用于 AI_GENERATED_CONTENT）
        private String statusText;        // 状态文本（用于 PLANNING/THINKING/EXECUTING）
        private Boolean done;             // 是否完成（用于 AI_DONE）
    }

    @Data
    @Builder
    public static class Metadata {
        private String chatMessageId;     // 消息ID
    }

    public enum Type {
        AI_GENERATED_CONTENT,  // AI 生成了内容（正常消息）
        AI_PLANNING,           // Agent 规划中
        AI_THINKING,           // Agent 思考中
        AI_EXECUTING,          // Agent 执行工具中
        AI_DONE,               // Agent 执行完毕
    }
}
```

### 前端类型定义（types/index.ts）

```typescript
export type SseMessageType =
  | "AI_GENERATED_CONTENT"
  | "AI_PLANNING"
  | "AI_THINKING"
  | "AI_EXECUTING"
  | "AI_DONE";

export interface SseMessage {
  type: SseMessageType;
  payload: {
    message: ChatMessageVO;
    statusText: string;
    done: boolean;
  };
  metadata: {
    chatMessageId: string;
  };
}
```

---

## 四、SSE 与 WebSocket 对比

| 维度 | SSE | WebSocket |
|------|-----|-----------|
| 通信方向 | 服务器→客户端（单工） | 双向通信 |
| 协议 | HTTP（标准） | 独立协议（ws://） |
| 浏览器 API | EventSource | WebSocket |
| 自动重连 | ✅ 浏览器自动 | ❌ 需要手动实现 |
| 传输数据 | 文本（默认） | 文本 + 二进制 |
| 连接数限制 | 浏览器限制 6 个/域名 | 无限制 |
| 适用场景 | 服务器推送（通知、状态更新） | 实时互动（聊天、游戏） |
| 实现复杂度 | 低（Spring 原生支持） | 较高（需要 WebSocket Handler） |

**为什么选 SSE？**
1. 本项目只需要服务器→前端推送，不需要前端→服务器（消息通过 REST API）
2. 浏览器原生支持 `EventSource`，自动重连
3. Spring Boot 原生支持 `SseEmitter`
4. 实现简单，无需额外依赖

---

## 五、当前实现的问题与改进

### 问题 1：没有心跳

`SseEmitter` 设置 30 分钟超时，但没有任何 keepalive。如果网络静默，连接可能被中间件（Nginx、网关）提前断开。

**改进方案**：
```java
// 后端定时发送心跳
@Scheduled(fixedRate = 30000)  // 每30秒
public void heartbeat() {
    clients.forEach((sessionId, emitter) -> {
        try {
            emitter.send(SseEmitter.event()
                    .name("heartbeat")
                    .data("ping"));
        } catch (IOException e) {
            clients.remove(sessionId);
        }
    });
}
```

### 问题 2：断连不重试

`AgentChatView.tsx` 中 `es.onerror` 只有 `console.error`，没有重试逻辑。

**改进方案**：
```typescript
const connectSSE = () => {
    const es = new EventSource(url);
    es.onerror = () => {
        es.close();
        setTimeout(connectSSE, 3000);  // 3秒后重试
    };
};
```

### 问题 3：连接时 Agent 可能已经产生消息

如果 Agent 运行很快，在 SSE 连接建立之前就产生了消息，前端会丢失。

**现有缓解**：前端通过 `getChatMessagesBySessionId(sessionId)` 在挂载时加载已有消息。
**完整方案**：SSE 连接建立后，服务端做一次"补发"：把 Agent 已经产生但客户端没收到的消息重新推送。

---

## 六、面试核心问题

### Q1: SSE 和 WebSocket 的区别？为什么选 SSE？

见上方对比表。核心：本项目只需要单向推送，SSE 更简单、浏览器原生支持自动重连。

### Q2: ConcurrentHashMap 管理连接线程安全吗？

`ConcurrentHashMap` 本身是线程安全的（分段锁）。
但 `send()` 方法的 `get + send` 不是原子操作，极端情况下可能出现：A 线程获取到 emitter，B 线程断连移除了 emitter，A 线程再 send 时已无效。

### Q3: 连接超时怎么处理？

后端设置 30 分钟超时，`onTimeout` 回调自动移除连接。
前端断开后，下次用户发消息会通过 REST API 正常处理，重新建立 SSE 连接。

### Q4: 如果用户开多个窗口？

同一个 `chatSessionId` 只有一个 SSE 连接。后打开的窗口会覆盖前面的连接。改进方案：用用户ID+会话ID作为 key，支持多设备。
