import Link from "next/link";

export default function NotFound(): JSX.Element {
  return (
    <div className="text-center py-16">
      <h1 className="text-4xl font-bold text-gray-900">404</h1>
      <p className="mt-2 text-lg text-gray-500">Page not found</p>
      <Link href="/" className="mt-4 inline-block text-indigo-600 hover:underline">
        Back to dashboard
      </Link>
    </div>
  );
}
