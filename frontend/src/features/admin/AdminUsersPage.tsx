import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  KeyRound,
  Search,
  Shield,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";

import { useSession } from "../auth/useSession";
import { ApiError, api } from "../../shared/api/client";
import type { AdminUser, CreateUserPayload } from "../../shared/api/types";
import { formatDisplayDate } from "../../shared/utils/formatDate";
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

function userDisplayName(user: AdminUser): string {
  const full = [user.name, user.surname].filter(Boolean).join(" ").trim();
  return full || user.login;
}

export function AdminUsersPage() {
  const queryClient = useQueryClient();
  const session = useSession();
  const [search, setSearch] = useState("");
  const [createForm, setCreateForm] = useState<CreateUserPayload>(initialCreatePayload);
  const [drafts, setDrafts] = useState<Record<string, UserDraft>>({});
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const usersQuery = useQuery({
    queryKey: ["admin-users"],
    queryFn: api.adminGetUsers,
    enabled: !!session.data?.admin,
  });

  const createMutation = useMutation({
    mutationFn: api.adminCreateUser,
    onSuccess: async () => {
      setFeedback({ type: "success", text: "Пользователь успешно создан" });
      setCreateForm(initialCreatePayload);
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (error) => setFeedback({ type: "error", text: (error as Error).message }),
  });

  const updateNameMutation = useMutation({
    mutationFn: api.adminUpdateUserNameSurname,
    onSuccess: async () => {
      setFeedback({ type: "success", text: "Данные пользователя обновлены" });
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (error) => setFeedback({ type: "error", text: (error as Error).message }),
  });

  const updatePasswordMutation = useMutation({
    mutationFn: api.adminUpdateUserPassword,
    onSuccess: () => setFeedback({ type: "success", text: "Пароль пользователя обновлён" }),
    onError: (error) => setFeedback({ type: "error", text: (error as Error).message }),
  });

  const deleteMutation = useMutation({
    mutationFn: api.adminDeleteUser,
    onSuccess: async (result) => {
      setFeedback({ type: "success", text: result.message });
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (error) => setFeedback({ type: "error", text: (error as Error).message }),
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

  if (session.isLoading) {
    return (
      <section className={styles.page}>
        <div className={styles.loading}>Загрузка...</div>
      </section>
    );
  }

  if (!session.data?.admin) {
    return (
      <section className={styles.page}>
        <div className={styles.denied}>Доступ только для администраторов.</div>
      </section>
    );
  }

  if (usersQuery.error && (usersQuery.error as ApiError).status === 401) {
    return (
      <section className={styles.page}>
        <div className={styles.denied}>Сессия истекла. Выполните вход снова.</div>
      </section>
    );
  }

  const totalUsers = usersQuery.data?.length ?? 0;
  const adminCount = usersQuery.data?.filter((u) => u.admin).length ?? 0;

  return (
    <section className={styles.page}>
      <header className={styles.hero}>
        <div className={styles.heroMain}>
          <span className={styles.heroIcon}>
            <Shield size={22} />
          </span>
          <div>
            <h1>Админ панель</h1>
            <p className={styles.subtitle}>Управление пользователями и правами доступа</p>
          </div>
        </div>
        <div className={styles.stats}>
          <div className={styles.stat}>
            <Users size={16} />
            <span>{totalUsers} пользователей</span>
          </div>
          <div className={styles.stat}>
            <Shield size={16} />
            <span>{adminCount} админов</span>
          </div>
        </div>
      </header>

      {feedback ? (
        <div className={feedback.type === "success" ? styles.feedbackSuccess : styles.feedbackError}>
          {feedback.text}
        </div>
      ) : null}

      {usersQuery.error ? (
        <div className={styles.feedbackError}>Ошибка: {(usersQuery.error as Error).message}</div>
      ) : null}

      <article className={styles.card}>
        <div className={styles.cardHeader}>
          <span className={styles.cardIcon}>
            <UserPlus size={18} />
          </span>
          <div>
            <h2>Создать пользователя</h2>
            <p className={styles.cardHint}>Новая учётная запись появится в списке ниже</p>
          </div>
        </div>
        <div className={styles.createGrid}>
          <label className={styles.field}>
            <span>Логин</span>
            <input
              value={createForm.login}
              onChange={(e) => setCreateForm((prev) => ({ ...prev, login: e.target.value }))}
              placeholder="username"
            />
          </label>
          <label className={styles.field}>
            <span>Пароль</span>
            <input
              type="password"
              value={createForm.password}
              onChange={(e) => setCreateForm((prev) => ({ ...prev, password: e.target.value }))}
              placeholder="••••••••"
            />
          </label>
          <label className={styles.field}>
            <span>Имя</span>
            <input
              value={createForm.name}
              onChange={(e) => setCreateForm((prev) => ({ ...prev, name: e.target.value }))}
              placeholder="Имя"
            />
          </label>
          <label className={styles.field}>
            <span>Фамилия</span>
            <input
              value={createForm.surname}
              onChange={(e) => setCreateForm((prev) => ({ ...prev, surname: e.target.value }))}
              placeholder="Фамилия"
            />
          </label>
          <label className={styles.field}>
            <span>Роль</span>
            <input
              value={createForm.role}
              onChange={(e) => setCreateForm((prev) => ({ ...prev, role: e.target.value }))}
              placeholder="user"
            />
          </label>
          <label className={styles.adminToggle}>
            <input
              type="checkbox"
              checked={createForm.admin}
              onChange={(e) => setCreateForm((prev) => ({ ...prev, admin: e.target.checked }))}
            />
            <span>Назначить администратором</span>
          </label>
        </div>
        <button
          type="button"
          className={styles.primaryBtn}
          disabled={!createForm.login || !createForm.password || createMutation.isPending}
          onClick={() => createMutation.mutate(createForm)}
        >
          {createMutation.isPending ? "Создание..." : "Создать пользователя"}
        </button>
      </article>

      <div className={styles.listHeader}>
        <div className={styles.listTitle}>
          <h3>Пользователи</h3>
          <span className={styles.listCount}>{filteredUsers.length}</span>
        </div>
        <div className={styles.searchBar}>
          <Search size={16} />
          <input
            className={styles.search}
            placeholder="Поиск по логину, имени или фамилии..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {usersQuery.isLoading ? <div className={styles.loading}>Загрузка пользователей...</div> : null}

      {!usersQuery.isLoading && !filteredUsers.length ? (
        <div className={styles.empty}>Пользователи не найдены</div>
      ) : null}

      <div className={styles.list}>
        {filteredUsers.map((user) => {
          const draft = getDraft(user);
          const displayName = userDisplayName(user);
          return (
            <article key={user.login} className={styles.userCard}>
              <div className={styles.userTop}>
                <span className={styles.userAvatar}>{displayName.slice(0, 1).toUpperCase()}</span>
                <div className={styles.userInfo}>
                  <div className={styles.userTitleRow}>
                    <strong className={styles.userLogin}>@{user.login}</strong>
                    <span className={user.admin ? styles.badgeAdmin : styles.badgeUser}>
                      {user.admin ? "Администратор" : "Пользователь"}
                    </span>
                    <span className={styles.badgeRole}>{user.role}</span>
                  </div>
                  <p className={styles.userName}>{displayName}</p>
                  <p className={styles.userDate}>Создан: {formatDisplayDate(user.created_at)}</p>
                </div>
                <button
                  type="button"
                  className={styles.deleteBtn}
                  onClick={() => {
                    const confirmed = window.confirm(`Удалить пользователя ${user.login}?`);
                    if (confirmed) deleteMutation.mutate(user.login);
                  }}
                  disabled={deleteMutation.isPending}
                  title="Удалить пользователя"
                >
                  <Trash2 size={15} />
                </button>
              </div>

              <div className={styles.userSections}>
                <section className={styles.userSection}>
                  <h4>ФИО</h4>
                  <div className={styles.sectionRow}>
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
                      type="button"
                      className={styles.secondaryBtn}
                      onClick={() =>
                        updateNameMutation.mutate({ login: user.login, name: draft.name, surname: draft.surname })
                      }
                      disabled={updateNameMutation.isPending}
                    >
                      Сохранить
                    </button>
                  </div>
                </section>

                <section className={styles.userSection}>
                  <h4>
                    <KeyRound size={14} />
                    Пароль
                  </h4>
                  <div className={styles.sectionRow}>
                    <input
                      placeholder="Новый пароль"
                      type="password"
                      value={draft.new_pwd}
                      onChange={(e) => updateDraft(user.login, { new_pwd: e.target.value })}
                    />
                    <button
                      type="button"
                      className={styles.secondaryBtn}
                      onClick={() => updatePasswordMutation.mutate({ login: user.login, new_pwd: draft.new_pwd })}
                      disabled={!draft.new_pwd || updatePasswordMutation.isPending}
                    >
                      Обновить
                    </button>
                  </div>
                </section>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
