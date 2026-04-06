import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { api } from "../../shared/api/client";
import styles from "./LoginPage.module.css";

export function LoginPage() {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const mutation = useMutation({
    mutationFn: async () => {
      await api.login(login, password);
      return api.profile();
    },
    onSuccess: (profile) => {
      queryClient.setQueryData(["session"], profile);
      navigate("/", { replace: true });
    },
  });

  return (
    <main className={styles.page}>
      <section className={styles.card}>
        <h1>RAG Multimodal Data Analyzer</h1>
        <p className={styles.subtitle}>Войдите в аккаунт</p>
        <label>
          Логин
          <input value={login} onChange={(e) => setLogin(e.target.value)} autoComplete="username" />
        </label>
        <label>
          Пароль
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </label>
        <button
          onClick={() => mutation.mutate()}
          disabled={!login || !password || mutation.isPending}
          className={styles.submit}
        >
          {mutation.isPending ? "Входим..." : "Войти"}
        </button>
        {mutation.error ? <p className={styles.error}>{(mutation.error as Error).message}</p> : null}
      </section>
    </main>
  );
}
