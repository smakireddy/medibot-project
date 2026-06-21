"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";
import { ROLE_META, type Role } from "@/lib/types";

const DEMO_USERS: { username: string; password: string; role: Role; display: string }[] = [
  { username: "dr.mehta",     password: "doctor123",  role: "doctor",            display: "Dr. Mehta" },
  { username: "nurse.priya",  password: "nurse123",   role: "nurse",             display: "Nurse Priya" },
  { username: "billing.ravi", password: "billing123", role: "billing_executive", display: "Ravi (Billing)" },
  { username: "tech.anand",   password: "tech123",    role: "technician",        display: "Anand (Tech)" },
  { username: "admin.sys",    password: "admin123",   role: "admin",             display: "System Admin" },
];

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]   = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin(u: string, p: string) {
    setLoading(true);
    setError("");
    try {
      const res = await login(u, p);
      localStorage.setItem("medibot_token",    res.access_token);
      localStorage.setItem("medibot_role",     res.role);
      localStorage.setItem("medibot_username", res.username);
      router.push("/chat");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="text-5xl mb-3">🏥</div>
          <h1 className="text-3xl font-bold text-gray-800">MediBot</h1>
          <p className="text-gray-500 mt-1">MediAssist Health Network — Internal AI Assistant</p>
        </div>

        {/* Login card */}
        <div className="bg-white rounded-2xl shadow-lg p-8">
          <h2 className="text-xl font-semibold text-gray-700 mb-6">Sign in to your account</h2>

          <form onSubmit={(e) => { e.preventDefault(); handleLogin(username, password); }} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. dr.mehta"
                className="w-full border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="password"
                className="w-full border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm"
                required
              />
            </div>

            {error && (
              <p className="text-red-500 text-sm bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg py-2.5 transition disabled:opacity-50"
            >
              {loading ? "Signing in…" : "Sign In"}
            </button>
          </form>

          {/* Quick login */}
          <div className="mt-6">
            <p className="text-xs text-gray-400 text-center mb-3">— Quick login (demo) —</p>
            <div className="grid grid-cols-1 gap-2">
              {DEMO_USERS.map((u) => {
                const meta = ROLE_META[u.role];
                return (
                  <button
                    key={u.username}
                    onClick={() => handleLogin(u.username, u.password)}
                    disabled={loading}
                    className={`flex items-center justify-between px-4 py-2.5 rounded-lg border text-sm font-medium transition hover:shadow-sm disabled:opacity-50 ${meta.bg} ${meta.color} border-current border-opacity-20`}
                  >
                    <span>{u.display}</span>
                    <span className="text-xs opacity-60 font-normal">{meta.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
