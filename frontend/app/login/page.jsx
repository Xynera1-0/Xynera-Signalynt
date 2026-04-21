"use client";

import Link from "next/link";
import { GoogleLogin } from "@react-oauth/google";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useAuth } from "../../components/auth/AuthProvider";
import ThemeToggle from "../../components/theme/ThemeToggle";

function LoginForm() {
  const { login, loginWithGoogle } = useAuth();
  const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  const googleEnabled = Boolean(googleClientId);
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/workspace";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  useEffect(() => {
    router.prefetch(next);
  }, [next, router]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setGoogleLoading(false);
    setLoading(true);
    try {
      await login(email, password);
      router.replace(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
    } finally {
      setLoading(false);
    }
  }

  const handleGoogleSuccess = useCallback(async (credentialResponse) => {
    const credential = credentialResponse?.credential;
    if (!credential) {
      setError("Google did not return a valid credential.");
      return;
    }

    setError(null);
    setGoogleLoading(true);
    try {
      await loginWithGoogle(credential);
      router.replace(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Google login failed.");
    } finally {
      setGoogleLoading(false);
    }
  }, [loginWithGoogle, next, router]);

  const handleGoogleError = useCallback(() => {
    setGoogleLoading(false);
    setError("Google sign-in failed.");
  }, []);

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md items-center px-4">
      <section className="glass-panel w-full rounded-3xl p-6 md:p-8 animate-fade-in">
        <div className="mb-4 flex justify-end">
          <ThemeToggle />
        </div>
        <p className="text-xs uppercase tracking-[0.2em] text-brand-300">Welcome back</p>
        <h1 className="text-main mt-2 text-2xl font-bold">Sign in to Xynera</h1>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="text-muted mb-1 block text-xs" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              className="input-field"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label className="text-muted mb-1 block text-xs" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              className="input-field"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Enter your password"
            />
          </div>

          {error && <p className="rounded-xl border border-rose-400/25 bg-rose-400/10 px-3 py-2 text-sm text-rose-300">{error}</p>}

          <button type="submit" disabled={loading} className="btn-primary w-full">
            {loading ? "Signing in..." : "Sign in"}
          </button>

          <div className="pt-2">
            <p className="text-muted mb-2 text-center text-xs uppercase tracking-[0.15em]">or continue with</p>
            {googleEnabled ? (
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
                <div className="flex justify-center">
                  <GoogleLogin
                    onSuccess={handleGoogleSuccess}
                    onError={handleGoogleError}
                    useOneTap={false}
                    shape="pill"
                    text="continue_with"
                    width="300"
                  />
                </div>
                {googleLoading && <p className="text-muted mt-2 text-center text-xs">Signing in with Google...</p>}
              </div>
            ) : (
              <p className="rounded-xl border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">
                Google sign-in is not configured yet. Add NEXT_PUBLIC_GOOGLE_CLIENT_ID to frontend environment.
              </p>
            )}
          </div>
        </form>

        <p className="text-muted mt-5 text-sm">
          No account yet?{" "}
          <Link href="/register" className="text-brand-200 hover:text-brand-100">
            Create one
          </Link>
        </p>
      </section>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<main className="mx-auto flex min-h-screen w-full max-w-md items-center px-4" />}>
      <LoginForm />
    </Suspense>
  );
}
