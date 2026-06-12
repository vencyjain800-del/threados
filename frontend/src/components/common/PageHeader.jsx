import { motion } from "framer-motion";

export function PageHeader({ title, subtitle, actions, children }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: [0.2, 0.8, 0.2, 1] }}
      className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between mb-6"
    >
      <div>
        <h1 className="font-display text-xl sm:text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
      {children}
    </motion.div>
  );
}
