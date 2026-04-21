import Link from "next/link";
import ThemeToggle from "../components/theme/ThemeToggle";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl items-center justify-center px-4">
      <section className="glass-panel w-full rounded-3xl p-8 md:p-12 animate-fade-in">
        <div className="mb-6 flex justify-end">
          <ThemeToggle />
        </div>
        <p className="text-xs uppercase tracking-[0.24em] text-brand-200">Xynera Signal to Action</p>
        <h1 className="mt-3 text-main text-3xl font-extrabold leading-tight md:text-5xl">
          Campaign intelligence that materializes as action-ready interfaces.
        </h1>
        <p className="text-soft mt-4 max-w-2xl text-sm md:text-base">
          Turn research into generation and outreach in one threaded workspace. Click through dynamic UI cards to keep momentum high.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/login" className="btn-primary">
            Open workspace
          </Link>
          <Link href="/register" className="btn-ghost">
            Create account
          </Link>
        </div>
      </section>
    </main>
  );
}
