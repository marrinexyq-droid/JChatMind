# Plan: 二次元磨砂玻璃 UI 重设计

**Complexity**: Large (影响几乎所有 UI 文件)

## Summary

将 JChatMind 从默认 Ant Design 工业风改造为二次元 / 赛博梦幻风格：
- 全局渐变背景 + 动态光效
- 流体磨砂玻璃 (frosted glass / glassmorphism) 作为主要容器
- 二次元色彩系统 (粉紫 / 薰衣草 / 天蓝 / 樱花粉)
- 弹窗使用丝滑 spring 动画 (framer-motion)
- 卡片 hover 带光晕浮动效果
- 保留所有功能，只改视觉层

## Design Direction

| 维度 | 选择 |
|------|------|
| **Tone** | 二次元梦幻 / 赛博少女风 — 轻盈、通透、有灵气 |
| **主色调** | `#c084fc` 薰衣草紫, `#f0abfc` 樱花粉, `#67e8f9` 冰蓝, `#a78bfa` 梦幻紫 |
| **背景** | 多层渐变 mesh gradient + 微妙动态光斑 |
| **容器** | `backdrop-blur` 磨砂玻璃, 半透明白底 + 紫色描边微光 |
| **字体** | 标题: "ZCOOL KuaiLe" (中文二次元感), 正文: "Quicksand" (圆润友好) |
| **弹窗动画** | framer-motion `AnimatePresence` + spring 弹性进入 + backdrop blur fade |
| **卡片交互** | hover 时 `translateY(-2px)` + 紫色辉光 box-shadow |
| **圆角** | 大圆角 `rounded-2xl` (16px), 通透柔软感 |
| **滚动条** | 自定义半透明紫色滚动条 |

## Files to Change

| File | Action | Why |
|------|--------|-----|
| `src/index.css` | REWRITE | 全局 CSS 变量、背景层、Ant Design 覆盖、滚动条、字体引入 |
| `tailwind.config.js` | REWRITE | 新的 keyframes (glass-enter, float, shimmer-pink, pulse-glow) |
| `src/main.tsx` | UPDATE | Ant Design ConfigProvider 加 theme token 覆盖 |
| `src/layout/Layout.tsx` | UPDATE | 全局 mesh gradient 背景层 |
| `src/layout/Sidebar.tsx` | UPDATE | 磨砂玻璃侧栏 |
| `src/layout/Content.tsx` | UPDATE | 内容区透明化 |
| `src/components/SideMenu.tsx` | UPDATE | 二次元 header + tab 样式 |
| `src/components/tabs/AgentTabContent.tsx` | UPDATE | 玻璃卡片列表 |
| `src/components/tabs/ChatTabContent.tsx` | UPDATE | 玻璃卡片列表 |
| `src/components/tabs/KnowledgeBaseTabContent.tsx` | UPDATE | 玻璃卡片列表 |
| `src/components/views/agentChatView/EmptyAgentChatView.tsx` | UPDATE | 梦幻 landing page |
| `src/components/views/agentChatView/AgentChatHistory.tsx` | UPDATE | 聊天气泡配色 |
| `src/components/views/agentChatView/AgentChatInput.tsx` | UPDATE | 磨砂输入框 |
| `src/components/views/KnowledgeBaseView.tsx` | UPDATE | 磨砂卡片 + 表格 |
| `src/components/modals/AddAgentModal.tsx` | UPDATE | framer-motion 动画弹窗 |
| `src/components/modals/AddKnowledgeBaseModal.tsx` | UPDATE | framer-motion 动画弹窗 |
| `package.json` | UPDATE | 添加 `framer-motion` 依赖 |

## Tasks

### Task 1: 全局基础 — CSS 变量 + 背景 + 字体
- **Files**: `src/index.css`, `tailwind.config.js`, `package.json`
- **内容**:
  - 引入 Google Fonts (ZCOOL KuaiLe + Quicksand)
  - 定义 CSS 变量 `--glass-bg`, `--glass-border`, `--glass-shadow`, 主色调变量
  - 全局 mesh gradient 背景 (多层 radial-gradient 叠加)
  - 自定义滚动条 (半透明紫)
  - Ant Design 全局 token 覆盖 (ConfigProvider theme)
  - tailwind.config.js 添加新 keyframes
- **Validate**: `npm run dev` 背景渐变可见, 字体加载成功

### Task 2: Ant Design 主题 Token 覆盖
- **Files**: `src/main.tsx`
- **内容**:
  - ConfigProvider 内添加 `theme: { token: { colorPrimary, borderRadius, colorBgContainer, ... } }`
  - 组件级覆盖: Modal (背景透明 + blur), Input (玻璃感), Button (渐变), Table (透明), Card (玻璃)
- **Validate**: 所有 Ant Design 组件自动获得二次元配色

### Task 3: Layout + Sidebar 磨砂玻璃化
- **Files**: `src/layout/Layout.tsx`, `src/layout/Sidebar.tsx`, `src/layout/Content.tsx`
- **内容**:
  - Layout 添加 mesh gradient 背景 div (固定定位, z-0)
  - Sidebar: `backdrop-blur-xl bg-white/20 border-r border-white/30`
  - Content: 透明背景, 让全局渐变透出
- **Validate**: 侧栏磨砂效果, 内容区背景渐变可见

### Task 4: SideMenu 二次元 Header
- **Files**: `src/components/SideMenu.tsx`
- **内容**:
  - Logo 区域: 紫粉色渐变文字 + 发光效果
  - Tab 样式: 玻璃态 active indicator
  - 整体配色从工业灰改为半透明白+紫
- **Validate**: 侧栏 header 视觉焕新

### Task 5: 列表卡片玻璃化
- **Files**: `src/components/tabs/AgentTabContent.tsx`, `ChatTabContent.tsx`, `KnowledgeBaseTabContent.tsx`
- **内容**:
  - 卡片: `backdrop-blur-md bg-white/25 border border-white/30 rounded-2xl`
  - Hover: `translateY(-2px)` + 紫色辉光 box-shadow
  - 渐变图标区域改用二次元色调 (粉紫/冰蓝/樱花粉)
  - transition 使用 spring-like cubic-bezier
- **Validate**: 列表卡片磨砂效果 + hover 浮动

### Task 6: EmptyAgentChatView 梦幻 Landing
- **Files**: `src/components/views/agentChatView/EmptyAgentChatView.tsx`
- **内容**:
  - 特性卡片: 玻璃卡片 + 二次元渐变图标
  - 标题区域: 渐变文字
  - 输入框: 磨砂玻璃效果
- **Validate**: landing page 视觉统一

### Task 7: 聊天区域配色
- **Files**: `src/components/views/agentChatView/AgentChatHistory.tsx`, `AgentChatInput.tsx`
- **内容**:
  - 用户气泡: 紫色渐变背景
  - 助手气泡: 半透明白色磨砂
  - 输入框: 磨砂玻璃 Sender
  - 工具调用指示器: 二次元配色
- **Validate**: 聊天界面配色和谐

### Task 8: KnowledgeBaseView + 表格
- **Files**: `src/components/views/KnowledgeBaseView.tsx`
- **内容**:
  - Card 和 Table 通过 ConfigProvider 已自动覆盖
  - 额外微调: 上传区域玻璃感
- **Validate**: 知识库页面视觉统一

### Task 9: 弹窗 framer-motion 动画 (核心亮点)
- **Files**: `src/components/modals/AddAgentModal.tsx`, `AddKnowledgeBaseModal.tsx`, `package.json`
- **内容**:
  - `npm install framer-motion`
  - 用 framer-motion 包装 Ant Design Modal:
    - 进入: scale(0.9)→scale(1) + opacity 0→1 + spring 弹性
    - 退出: scale(1)→scale(0.95) + opacity 1→0
    - 背景遮罩: opacity 渐变 + backdrop-blur
  - Modal 内容区域: 磨砂玻璃背景 + 二次元描边
  - 内部面板切换: 淡入淡出 + 轻微位移
- **Validate**: 弹窗打开/关闭丝滑有弹性, 面板切换流畅

### Task 10: 全局打磨 + 微交互
- **Files**: `tailwind.config.js`, `src/index.css`
- **内容**:
  - 光标: 自定义粉色小光标 (可选)
  - 选中文本颜色: 紫色高亮
  - focus ring: 紫色辉光
  - 所有 transition 统一 cubic-bezier 曲线
- **Validate**: 全局交互体验统一

## Validation

```bash
npm run dev          # 启动开发服务器
npm run build        # 确保构建无报错
```

手动验证清单:
- [ ] 全局 mesh gradient 背景可见
- [ ] Sidebar 磨砂玻璃效果 + 半透明
- [ ] 所有列表卡片磨砂 + hover 浮动
- [ ] 弹窗打开有 spring 弹性动画
- [ ] 弹窗关闭有平滑退出动画
- [ ] 聊天气泡配色和谐
- [ ] 字体加载正常 (中文二次元字体)
- [ ] 移动端无布局崩塌
- [ ] 构建无报错

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| framer-motion 与 Ant Design Modal 冲突 | Medium | 不替换 Modal, 用 motion.div 包裹 Modal children, 或用自定义 modal wrapper |
| backdrop-blur 浏览器兼容 | Low | 现代浏览器均支持, 提供 fallback bg opacity |
| 字体加载闪烁 (FOUT) | Medium | 使用 `font-display: swap` + preload |
| Ant Design 内部样式优先级 | Medium | 使用 ConfigProvider token 而非强行 CSS override |
| 渐变背景性能 | Low | 使用 CSS 而非 canvas, 移动端可降级 |

## Acceptance

- [ ] 所有 10 个 task 完成
- [ ] `npm run build` 无报错
- [ ] 全局视觉风格统一为二次元磨砂玻璃
- [ ] 弹窗动画丝滑有弹性
- [ ] 所有功能不变, 仅视觉层改动
