"use client";

export function AuthCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <h1 className="text-center text-3xl font-bold text-brand-700">ThreadOS</h1>
        <h2 className="mt-4 text-center text-xl font-semibold text-gray-900">{title}</h2>
        {subtitle && (
          <p className="mt-2 text-center text-sm text-gray-500">{subtitle}</p>
        )}
      </div>
      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow rounded-lg">{children}</div>
      </div>
    </div>
  );
}
