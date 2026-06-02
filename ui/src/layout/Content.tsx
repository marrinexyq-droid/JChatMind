interface ContentProps {
  children: React.ReactNode;
}

export default function Content({ children }: ContentProps) {
  return (
    <main className="flex-1 relative overflow-hidden">
      {children}
    </main>
  );
}