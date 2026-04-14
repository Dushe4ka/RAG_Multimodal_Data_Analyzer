import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";

import { useSession } from "../auth/useSession";
import { ApiError, api } from "../../shared/api/client";
import type { AdminUser, CreateUserPayload } from "../../shared/api/types";
import styles from "./AdminUsersPage.module.css";

type UserDraft = {
  name: string;
  surname: string;
  new_pwd: string;
};

const initialCreatePayload: CreateUserPayload = {
  login: "",
  password: "",
  name: "",
  surname: "",
  role: "user",
  admin: false,
};

export function AdminUsersPage() {
  const queryClient = useQueryClient();
  const session = useSession();
  const [search, setSearch] = useState("");
  const [createForm, setCreateForm] = useState<CreateUserPayload>(initialCreatePayload);
  const [drafts, setDrafts] = useState<Record<string, UserDraft>>({});
  const [feedback, setFeedback] = useState<string | null>(null);

  const usersQuery = useQuery({
    queryKey: ["admin-users"],
    queryFn: api.adminGetUsers,
    enabled: !!session.data?.admin,
  });

  const createMutation = useMutation({
    mutationFn: api.adminCreateUser,
    onSuccess: async () => {
      setFeedback("Пользователь успешно создан");
      setCreateForm(initialCreatePayload);
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (error) => setFeedback((error as Error).message),
  });

  const updateNameMutation = useMutation({
    mutationFn: api.adminUpdateUserNameSurname,
    onSuccess: async () => {
      setFeedback("Данные пользователя обновлены");
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (error) => setFeedback((error as Error).message),
  });

  const updatePasswordMutation = useMutation({
    mutationFn: api.adminUpdateUserPassword,
    onSuccess: () => setFeedback("Пароль пользователя обновлен"),
    onError: (error) => setFeedback((error as Error).message),
  });

  const deleteMutation = useMutation({
    mutationFn: api.adminDeleteUser,
    onSuccess: async (result) => {
      setFeedback(result.message);
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (error) => setFeedback((error as Error).message),
  });

  const filteredUsers = useMemo(() => {
    const users = usersQuery.data ?? [];
    const normalized = search.trim().toLowerCase();
    if (!normalized) return users;
    return users.filter((user) => {
      const fullName = `${user.name} ${user.surname}`.toLowerCase();
      return user.login.toLowerCase().includes(normalized) || fullName.includes(normalized);
    });
  }, [usersQuery.data, search]);

  const getDraft = (user: AdminUser): UserDraft => {
    const existing = drafts[user.login];
    if (existing) return existing;
    return { name: user.name ?? "", surname: user.surname ?? "", new_pwd: "" };
  };

  const updateDraft = (login: string, next: Partial<UserDraft>) => {
    setDrafts((prev) => {
      const current = prev[login] ?? { name: "", surname: "", new_pwd: "" };
      return { ...prev, [login]: { ...current, ...next } };
    });
  };

  if (session.isLoading) return <section className={styles.page}>Загрузка...</section>;
  if (!session.data?.admin) return <section className={styles.page}>Доступ только для администраторов.</section>;
  if (usersQuery.error && (usersQuery.error as ApiError).status === 401) {
    return <section className={styles.page}>Сессия истекла. Выполните вход снова.</section>;
  }

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <h1>Админ панель</h1>
        <input
          className={styles.search}
          placeholder="Поиск по логину, имени или фамилии"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </header>

      <article className={styles.card}>
        <h2>Создать пользователя</h2>
        <div className={styles.createGrid}>
          <input
            placeholder="Логин"
            value={createForm.login}
            onChange={(e) => setCreateForm((prev) => ({ ...prev, login: e.target.value }))}
          />
          <input
            placeholder="Пароль"
            type="password"
            value={createForm.password}
            onChange={(e) => setCreateForm((prev) => ({ ...prev, password: e.target.value }))}
          />
          <input
            placeholder="Имя"
            value={createForm.name}
            onChange={(e) => setCreateForm((prev) => ({ ...prev, name: e.target.value }))}
          />
          <input
            placeholder="Фамилия"
            value={createForm.surname}
            onChange={(e) => setCreateForm((prev) => ({ ...prev, surname: e.target.value }))}
          />
          <input
            placeholder="Роль"
            value={createForm.role}
            onChange={(e) => setCreateForm((prev) => ({ ...prev, role: e.target.value }))}
          />
          <label className={styles.checkbox}>
            <input
              type="checkbox"
              checked={createForm.admin}
              onChange={(e) => setCreateForm((prev) => ({ ...prev, admin: e.target.checked }))}
            />
            Администратор
          </label>
        </div>
        <button
          className={styles.primaryButton}
          disabled={!createForm.login || !createForm.password || createMutation.isPending}
          onClick={() => createMutation.mutate(createForm)}
        >
          Создать
        </button>
      </article>

      {feedback ? <div className={styles.feedback}>{feedback}</div> : null}
      {usersQuery.error ? <div className={styles.error}>Ошибка: {(usersQuery.error as Error).message}</div> : null}
      {usersQuery.isLoading ? <div>Загрузка пользователей...</div> : null}

      <div className={styles.list}>
        {filteredUsers.map((user) => {
          const draft = getDraft(user);
          return (
            <article key={user.login} className={styles.userCard}>
              <div className={styles.userMeta}>
                <strong>{user.login}</strong>
                <span>{user.name || "—"} {user.surname || "—"}</span>
                <span>{user.role}</span>
                <span>{user.admin ? "admin" : "user"}</span>
              </div>
              <div className={styles.actions}>
                <input
                  placeholder="Имя"
                  value={draft.name}
                  onChange={(e) => updateDraft(user.login, { name: e.target.value })}
                />
                <input
                  placeholder="Фамилия"
                  value={draft.surname}
                  onChange={(e) => updateDraft(user.login, { surname: e.target.value })}
                />
                <button
                  onClick={() => updateNameMutation.mutate({ login: user.login, name: draft.name, surname: draft.surname })}
                  disabled={updateNameMutation.isPending}
                >
                  Сохранить ФИО
                </button>
                <input
                  placeholder="Новый пароль"
                  type="password"
                  value={draft.new_pwd}
                  onChange={(e) => updateDraft(user.login, { new_pwd: e.target.value })}
                />
                <button
                  onClick={() => updatePasswordMutation.mutate({ login: user.login, new_pwd: draft.new_pwd })}
                  disabled={!draft.new_pwd || updatePasswordMutation.isPending}
                >
                  Сменить пароль
                </button>
                <button
                  className={styles.dangerButton}
                  onClick={() => {
                    const confirmed = window.confirm(`Удалить пользователя ${user.login}?`);
                    if (confirmed) deleteMutation.mutate(user.login);
                  }}
                  disabled={deleteMutation.isPending}
                  title="Удалить пользователя"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
