import { createRoot } from "react-dom/client";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import App from "./App.tsx";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <ConfigProvider
    locale={zhCN}
    theme={{
      token: {
        colorPrimary: "#6366f1",
        borderRadius: 12,
        borderRadiusLG: 16,
        borderRadiusSM: 8,
        colorBgContainer: "rgba(26, 26, 46, 0.7)",
        colorBgElevated: "#1a1a2e",
        colorBgSpotlight: "rgba(99, 102, 241, 0.15)",
        colorBorder: "rgba(165, 180, 252, 0.2)",
        colorBorderSecondary: "rgba(165, 180, 252, 0.1)",
        colorText: "#e0e7ff",
        colorTextSecondary: "#a5b4fc",
        colorTextTertiary: "#7c7faa",
        colorTextPlaceholder: "#a5b4fc",
        fontFamily: "'Poppins', 'Outfit', sans-serif",
        controlOutline: "rgba(99, 102, 241, 0.3)",
        boxShadow: "0 4px 16px rgba(0, 0, 0, 0.15)",
        boxShadowSecondary: "0 2px 8px rgba(0, 0, 0, 0.1)",
        colorFillAlter: "rgba(99, 102, 241, 0.1)",
        colorTextLightSolid: "#f0f4ff",
        colorPrimaryHover: "#4f46e5",
        colorLink: "#06b6d4",
      },
      components: {
        Modal: {
          contentBg: "rgba(26, 26, 46, 0.9)",
          headerBg: "transparent",
          footerBg: "transparent",
          titleColor: "#e0e7ff",
          algorithm: true,
        },
        Button: {
          primaryColor: "#f0f4ff",
          algorithm: true,
        },
        Card: {
          colorBgContainer: "rgba(26, 26, 46, 0.5)",
        },
        Table: {
          colorBgContainer: "transparent",
          headerBg: "#1a1a2e",
          rowHoverBg: "rgba(99, 102, 241, 0.1)",
        },
        Input: {
          colorBgContainer: "rgba(26, 26, 46, 0.7)",
          activeBorderColor: "rgba(99, 102, 241, 0.8)",
          activeShadow: "0 0 20px rgba(99, 102, 241, 0.4)",
          algorithm: true,
        },
        Select: {
          colorBgContainer: "rgba(26, 26, 46, 0.7)",
          colorBgElevated: "#1a1a2e",
          colorText: "#e0e7ff",
          colorTextPlaceholder: "#a5b4fc",
          optionSelectedBg: "rgba(99, 102, 241, 0.2)",
          algorithm: true,
        },
        Tabs: {
          itemColor: "#a5b4fc",
          itemSelectedColor: "#e0e7ff",
          itemHoverColor: "#06b6d4",
          inkBarColor: "#6366f1",
        },
        Divider: {
          colorSplit: "rgba(165, 180, 252, 0.15)",
        },
        Slider: {
          trackBg: "rgba(99, 102, 241, 0.2)",
          railBg: "rgba(255, 255, 255, 0.06)",
          handleColor: "#6366f1",
          dotActiveBorderColor: "#6366f1",
        },
        Typography: {
          colorText: "#e0e7ff",
          colorTextDescription: "#a5b4fc",
          colorTextHeading: "#e0e7ff",
        },
        Dropdown: {
          colorBgElevated: "#1a1a2e",
        },
        Popconfirm: {
          colorBgElevated: "#1a1a2e",
        },
      },
    }}
  >
    <App />
  </ConfigProvider>
);