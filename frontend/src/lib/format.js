export const gbp = (value) =>
  new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 }).format(
    Number(value || 0)
  );

export const gbpPrecise = (value) =>
  new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 2 }).format(
    Number(value || 0)
  );

export const num = (value) =>
  new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 }).format(Number(value || 0));

export const num1 = (value) =>
  new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 }).format(Number(value || 0));

export const formatDateShort = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric" }).format(d);
};

export const formatDay = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short" }).format(d);
};

export const daysFromNow = (iso) => {
  if (!iso) return 0;
  const target = new Date(iso);
  const today = new Date();
  target.setHours(0, 0, 0, 0);
  today.setHours(0, 0, 0, 0);
  return Math.round((target - today) / (1000 * 60 * 60 * 24));
};
