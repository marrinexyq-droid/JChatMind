import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";

interface GlassModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  width?: number;
  children: React.ReactNode;
}

export default function GlassModal({
  open,
  onClose,
  title,
  width = 800,
  children,
}: GlassModalProps) {
  useEffect(() => {
    if (open) window.petActions?.setCurious?.();
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-[1000]"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            onClick={onClose}
            style={{
              background: "rgba(0, 0, 0, 0.5)",
              backdropFilter: "blur(8px)",
              WebkitBackdropFilter: "blur(8px)",
            }}
          />
          <div className="fixed inset-0 z-[1001] flex items-center justify-center pointer-events-none">
            <motion.div
              className="pointer-events-auto"
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ type: "spring", stiffness: 380, damping: 28, mass: 0.8 }}
              style={{
                width: `${width}px`,
                maxWidth: "95vw",
                maxHeight: "90vh",
                background: "rgba(26, 26, 46, 0.95)",
                backdropFilter: "blur(24px)",
                WebkitBackdropFilter: "blur(24px)",
                border: "1px solid rgba(165, 180, 252, 0.2)",
                borderRadius: "20px",
                boxShadow: "0 20px 60px rgba(0, 0, 0, 0.5), 0 0 20px rgba(99, 102, 241, 0.1)",
                overflow: "hidden",
                display: "flex",
                flexDirection: "column",
              }}
            >
              <div
                className="flex items-center justify-between px-6 py-4"
                style={{ borderBottom: "1px solid var(--glass-border)" }}
              >
                <h2
                  className="text-lg font-bold gradient-text m-0"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  {title}
                </h2>
                <button
                  onClick={onClose}
                  className="w-8 h-8 rounded-xl flex items-center justify-center cursor-pointer transition-all duration-200 text-sm"
                  style={{
                    background: "rgba(255,255,255,0.04)",
                    border: "1px solid var(--glass-border)",
                    color: "var(--text-secondary)",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "rgba(255,255,255,0.1)";
                    e.currentTarget.style.color = "var(--text-primary)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "rgba(255,255,255,0.04)";
                    e.currentTarget.style.color = "var(--text-secondary)";
                  }}
                >
                  ✕
                </button>
              </div>
              <div className="flex-1 overflow-y-auto">
                {children}
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
