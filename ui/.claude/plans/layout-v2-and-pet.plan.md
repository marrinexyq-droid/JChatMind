# Plan: 布局升级 V2 + 二次元网页宠物

**Complexity**: Large

## Summary

两部分改造：
1. **布局重构** — 从死板的 320px 固定侧栏 + 内容区 改为更自由的浮动面板式布局，侧栏可收起，聊天区域更沉浸
2. **2D 网页宠物** — 一个二次元风格的像素/手绘精灵宠物，拥有状态机驱动的反应系统（待机、开心、好奇、兴奋、困倦），对用户的点击、发送消息、搜索等操作有不同反应

## 一、布局重新设计

### 当前问题
- 320px 固定侧栏太死板，浪费屏幕空间
- 没有收起/展开机制
- 聊天区域不够沉浸
- Landing page 布局单调

### 新布局方向: "浮动面板 + 沉浸聊天"

```
┌─────────────────────────────────────────────────┐
│  ┌──────────────────────────────────────────┐   │
│  │  TopBar (浮动磨砂玻璃)                     │   │
│  │  [≡ 收起侧栏] [JChatMind Logo] [宠物区]   │   │
│  └──────────────────────────────────────────┘   │
│                                                 │
│  ┌─────────┐  ┌────────────────────────────┐   │
│  │         │  │                            │   │
│  │ 浮动    │  │   聊天内容区 (全沉浸)       │   │
│  │ 磨砂    │  │                            │   │
│  │ 侧栏    │  │                            │   │
│  │ (可收起) │  │                            │   │
│  │         │  │                            │   │
│  └─────────┘  ├────────────────────────────┤   │
│               │  ┌──────────────────────┐  │   │
│               │  │  浮动输入框 (居中)    │  │   │
│               │  └──────────────────────┘  │   │
│               └────────────────────────────┘   │
│                                                 │
│                    宠物在此区域自由活动            │
└─────────────────────────────────────────────────┘
```

### 关键改变
1. **TopBar 取代侧栏 header** — 浮动磨砂玻璃横条，包含 Logo + 侧栏收起按钮 + 宠物状态指示
2. **侧栏可收起** — 点击按钮平滑收起/展开 (width 320px → 0)，收起时内容区占满
3. **输入框居中浮动** — 不再贴底，悬浮在内容区底部中央，更像 ChatGPT 风格
4. **Landing page 更梦幻** — 居中大标题 + 功能卡片横向排列 + 宠物在旁边互动

### 文件变更

| File | Action | Why |
|------|--------|-----|
| `src/layout/Layout.tsx` | REWRITE | 新布局: TopBar + 侧栏(可收起) + 内容 + 宠物层 |
| `src/layout/Sidebar.tsx` | REWRITE | 支持收起动画, 浮动圆角面板 |
| `src/layout/Content.tsx` | UPDATE | 配合侧栏收起的过渡 |
| `src/components/JChatMindLayout.tsx` | UPDATE | 收起状态管理, 新布局组合 |
| `src/components/SideMenu.tsx` | UPDATE | 移除 header (已上移到 TopBar) |
| `src/components/views/AgentChatView.tsx` | UPDATE | 输入框浮动居中 |
| `src/components/views/agentChatView/EmptyAgentChatView.tsx` | REWRITE | 梦幻 landing + 宠物互动区 |
| `src/index.css` | UPDATE | 新布局 CSS, 侧栏过渡动画 |

---

## 二、2D 网页宠物系统

### 为什么选 2D 不选 3D
- 二次元风格下，手绘/像素精灵天然契合
- 2D 逐帧动画表情更丰富、更"萌"
- 轻量无依赖，CSS + requestAnimationFrame 即可
- 3D (Three.js) 太重，与磨砂玻璃风格不搭

### 宠物设计方案: "灵喵" (LingMiao)

一个二次元风格的小猫/小精灵角色，用纯 CSS 绘制（圆润身体 + 大眼睛 + 小尾巴），通过 CSS 变换驱动不同状态。

#### 状态机

```
        ┌──────────┐
        │  IDLE    │ ← 默认待机
        │ (呼吸+眨眼)│
        └────┬─────┘
             │
    ┌────────┼────────┬────────────┐
    ▼        ▼        ▼            ▼
┌───────┐ ┌──────┐ ┌────────┐ ┌───────┐
│ HAPPY │ │THINK │ │CURIOUS │ │ SLEEP │
│(蹦跳) │ │(转圈) │ │(歪头看) │ │(zzz)  │
└───────┘ └──────┘ └────────┘ └───────┘
    │        │        │            │
    └────────┴────────┴────────────┘
             │ 3s 无操作
             ▼
          回到 IDLE
```

#### 状态触发规则

| 用户操作 | 宠物状态 | 动画 |
|----------|---------|------|
| 打开页面 | IDLE | 呼吸起伏 + 每 3-5s 眨眼 |
| 鼠标悬停宠物 | CURIOUS | 歪头 + 眼睛跟随鼠标 |
| 点击宠物 | HAPPY | 原地弹跳 + 爱心飘出 |
| 发送消息 | THINK | 转圈 + 头顶冒泡 |
| 收到 AI 回复 | EXCITE | 快速弹跳 + 星星飘出 |
| 点击侧栏 tab | CURIOUS | 朝点击方向看 |
| 点击知识库 | THINK | 假装翻书动作 |
| 打开弹窗 | CURIOUS | 弹出探头看 |
| 60s 无操作 | SLEEP | 眯眼 + 呼吸变慢 + "z z z" |
| 鼠标移动 | IDLE | 眼睛跟随鼠标方向 |

#### 实现方案

- **纯 CSS 驱动**: 用 div + border-radius 画身体，CSS 动画做状态过渡
- **状态管理**: React Context + useReducer (PetContext)
- **事件监听**: 全局点击/鼠标事件 → 派发状态变更
- **粒子效果**: CSS 动画的爱心/星星/泡泡 (固定几个 DOM 节点循环利用)
- **位置**: 固定在右下角，z-index 最高层级之一

### 文件变更

| File | Action | Why |
|------|--------|-----|
| `src/components/pet/WebPet.tsx` | CREATE | 宠物主组件: CSS 精灵 + 状态动画 |
| `src/components/pet/PetContext.tsx` | CREATE | 宠物状态管理 (Context + Reducer) |
| `src/components/pet/pet.module.css` | CREATE | 宠物 CSS 绘制 + 所有状态动画 |
| `src/components/pet/ParticleSystem.tsx` | CREATE | 爱心/星星/泡泡粒子飘出效果 |
| `src/components/JChatMindLayout.tsx` | UPDATE | 集成 PetProvider + WebPet |
| `src/components/views/AgentChatView.tsx` | UPDATE | 发送/接收消息时触发宠物状态 |
| `src/components/views/agentChatView/EmptyAgentChatView.tsx` | UPDATE | Landing 页宠物互动 |
| `src/components/modals/GlassModal.tsx` | UPDATE | 弹窗打开时触发宠物好奇 |
| `src/components/SideMenu.tsx` | UPDATE | Tab 切换时触发宠物反应 |

---

## Tasks

### Task 1: 布局重构 — TopBar + 可收起侧栏
- **Files**: `Layout.tsx`, `Sidebar.tsx`, `Content.tsx`, `JChatMindLayout.tsx`
- **内容**:
  - 新增 TopBar 组件 (浮动磨砂玻璃横条, 包含 Logo + 收起按钮)
  - Sidebar 增加 `collapsed` prop, 宽度 320px ↔ 0 过渡
  - JChatMindLayout 管理 `sidebarCollapsed` 状态
  - Content 自适应侧栏状态
- **Validate**: `npm run build` 通过, 侧栏可收起展开

### Task 2: SideMenu 精简 + 输入框浮动
- **Files**: `SideMenu.tsx`, `AgentChatView.tsx`, `EmptyAgentChatView.tsx`
- **内容**:
  - SideMenu 移除 header (上移到 TopBar), tab 区域填满
  - 聊天输入框: 浮动居中在内容区底部, 磨砂玻璃效果, 宽度限制 800px
  - Landing page: 标题更大更梦幻, 功能卡片横向排列
- **Validate**: 布局视觉效果正确

### Task 3: 宠物系统 — 状态管理 + CSS 绘制
- **Files**: `src/components/pet/PetContext.tsx`, `pet.module.css`
- **内容**:
  - PetContext: 定义 6 种状态 (idle, happy, think, curious, excite, sleep)
  - useReducer 状态机: 任何状态 → 3s 无操作 → idle; 60s → sleep
  - pet.module.css: 纯 CSS 绘制小精灵 (圆身体, 大眼睛, 小耳朵, 尾巴)
  - 每个状态的 CSS 动画 keyframes
- **Validate**: CSS 渲染正确, 状态切换动画流畅

### Task 4: 宠物组件 — WebPet + 粒子效果
- **Files**: `src/components/pet/WebPet.tsx`, `src/components/pet/ParticleSystem.tsx`
- **内容**:
  - WebPet: 渲染 CSS 精灵 + 状态驱动的 className 切换
  - 眼睛跟随鼠标 (requestAnimationFrame 追踪)
  - 眨眼定时器 (3-5s 随机)
  - 粒子系统: 爱心/星星/泡泡 DOM 节点, CSS 动画飘出后移除
- **Validate**: 宠物渲染, 眼睛跟随, 粒子飘出

### Task 5: 宠物集成 — 全局事件绑定
- **Files**: `JChatMindLayout.tsx`, `AgentChatView.tsx`, `SideMenu.tsx`, `GlassModal.tsx`
- **内容**:
  - JChatMindLayout 包裹 PetProvider + 渲染 WebPet
  - AgentChatView: 发送消息 → think, 收到 SSE → excite
  - SideMenu: tab 切换 → curious
  - GlassModal: open → curious
  - 全局鼠标移动 → idle 眼睛跟随
- **Validate**: 各操作触发对应宠物状态

### Task 6: 全局打磨
- **Files**: `index.css`, `tailwind.config.js`
- **内容**:
  - 新布局相关的 CSS 过渡动画
  - 宠物相关的新 keyframes
  - 响应式微调
- **Validate**: `npm run build` 无报无错

## Validation

```bash
npm run build          # TypeScript + Vite 构建
npm run dev            # 开发服务器
```

手动验证清单:
- [ ] 侧栏点击收起/展开, 动画流畅
- [ ] TopBar 浮动磨砂效果
- [ ] 聊天输入框浮动居中
- [ ] 宠物渲染在右下角
- [ ] 宠物默认呼吸+眨眼
- [ ] 鼠标悬停宠物 → 歪头好奇
- [ ] 点击宠物 → 弹跳+爱心
- [ ] 发送消息 → 宠物转圈思考
- [ ] 收到回复 → 宠物兴奋弹跳
- [ ] 60s 无操作 → 宠物打瞌睡
- [ ] 打开弹窗 → 宠物好奇探头
- [ ] 切换 tab → 宠物朝方向看
- [ ] 构建无报错

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| CSS 绘制的宠物不够可爱 | Medium | 先做简单原型, 迭代调整比例(大头大眼) |
| 侧栏收起影响 Tab 布局 | Medium | 用 `overflow: hidden` + `width` 过渡, 不用 `display: none` |
| 宠物性能 (requestAnimationFrame) | Low | 眼睛跟随用 passive listener, 无操作时停止 |
| 状态竞争 (快速操作) | Medium | debounce 状态变更, 优先级: 用户主动交互 > 自动回 idle |
| CSS 动画与 framer-motion 冲突 | Low | 宠物用纯 CSS, 与 framer-motion 作用域分离 |

## Acceptance
- [ ] 布局: 侧栏可收起, TopBar 浮动, 输入框居中
- [ ] 宠物: 6 种状态动画正常
- [ ] 宠物: 对所有指定操作有反应
- [ ] 宠物: 待机呼吸+眨眼, 60s 打瞌睡
- [ ] 构建无报错
- [ ] 功能不变, 纯视觉+体验层改动
