export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const SENTRY_DSN = process.env.SENTRY_DSN;
    if (SENTRY_DSN) {
      const Sentry = await import("@sentry/nextjs");
      Sentry.init({
        dsn: SENTRY_DSN,
        environment: process.env.APP_ENV ?? "development",
        tracesSampleRate: 0.1,
      });
    }
  }
}
