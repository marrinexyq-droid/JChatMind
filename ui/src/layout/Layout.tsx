interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="h-screen flex flex-col relative overflow-hidden" style={{ background: "var(--bg-primary)" }}>
      <div className="mesh-bg" />
      {children}
    </div>
  );
}