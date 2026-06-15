import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Calendar, KeyRound, Shield, User, UserRound } from "lucide-react";

import { useSession } from "../auth/useSession";
import { api } from "../../shared/api/client";
import { formatDisplayDate } from "../../shared/utils/formatDate";
import styles from "./ProfilePage.module.css";

function displayName(name?: string, surname?: string, login?: string): string {
  const full = [name, surname].filter(Boolean).join(" ").trim();
  return full || login || "Пользователь";
}

export function ProfilePage() {
  const queryClient = useQueryClient();
  const session = useSession();
  const [name, setName] = useState("");
  const [surname, setSurname] = useState("");
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    if (!session.data) return;
    setName(session.data.name ?? "");
    setSurname(session.data.surname ?? "");
  }, [session.data]);

  const editNameMutation = useMutation({
    mutationFn: api.profileEditNameSurname,
    onSuccess: async (profile) => {
      setFeedback({ type: "success", text: "Имя и фамилия успешно обновлены" });
      await queryClient.setQueryData(["session"], profile);
    },
    onError: (error) => setFeedback({ type: "error", text: (error as Error).message }),
  });

  const editPasswordMutation = useMutation({
    mutationFn: api.profileEditPassword,
    onSuccess: () => {
      setFeedback({ type: "success", text: "Пароль успешно изменён" });
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
    },
    onError: (error) => setFeedback({ type: "error", text: (error as Error).message }),
  });

  if (session.isLoading) {
    return (
      <section className={styles.page}>
        <div className={styles.loading}>Загрузка профиля...</div>
      </section>
    );
  }

  if (session.error || !session.data) {
    return (
      <section className={styles.page}>
        <div className={styles.errorState}>Не удалось загрузить профиль.</div>
      </section>
    );
  }

  const fullName = displayName(session.data.name, session.data.surname, session.data.login);
  const initials = fullName.slice(0, 1).toUpperCase();

  return (
    <section className={styles.page}>
      <header className={styles.hero}>
        <div className={styles.avatar}>{initials}</div>
        <div className={styles.heroText}>
          <h1>{fullName}</h1>
          <p className={styles.subtitle}>@{session.data.login}</p>
          <div className={styles.badges}>
            <span className={session.data.admin ? styles.badgeAdmin : styles.badgeUser}>
              {session.data.admin ? <Shield size={13} /> : <User size={13} />}
              {session.data.admin ? "Администратор" : "Пользователь"}
            </span>
            <span className={styles.badgeRole}>{session.data.role}</span>
          </div>
        </div>
      </header>

      {feedback ? (
        <div className={feedback.type === "success" ? styles.feedbackSuccess : styles.feedbackError}>
          {feedback.text}
        </div>
      ) : null}

      <div className={styles.grid}>
        <article className={styles.card}>
          <div className={styles.cardHeader}>
            <span className={styles.cardIcon}>
              <UserRound size={18} />
            </span>
            <div>
              <h2>Основная информация</h2>
              <p className={styles.cardHint}>Данные вашей учётной записи</p>
            </div>
          </div>
          <dl className={styles.metaList}>
            <div className={styles.metaItem}>
              <dt>Логин</dt>
              <dd>{session.data.login}</dd>
            </div>
            <div className={styles.metaItem}>
              <dt>Роль</dt>
              <dd>{session.data.role}</dd>
            </div>
            <div className={styles.metaItem}>
              <dt>Статус</dt>
              <dd>{session.data.admin ? "Администратор" : "Пользователь"}</dd>
            </div>
            <div className={styles.metaItem}>
              <dt>
                <Calendar size={13} />
                Создан
              </dt>
              <dd>{formatDisplayDate(session.data.created_at)}</dd>
            </div>
          </dl>
        </article>

        <article className={styles.card}>
          <div className={styles.cardHeader}>
            <span className={styles.cardIcon}>
              <User size={18} />
            </span>
            <div>
              <h2>Изменить ФИО</h2>
              <p className={styles.cardHint}>Отображается в интерфейсе и боковой панели</p>
            </div>
          </div>
          <div className={styles.formGrid}>
            <label className={styles.field}>
              <span>Имя</span>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Введите имя" />
            </label>
            <label className={styles.field}>
              <span>Фамилия</span>
              <input value={surname} onChange={(e) => setSurname(e.target.value)} placeholder="Введите фамилию" />
            </label>
          </div>
          <button
            type="button"
            className={styles.primaryBtn}
            disabled={editNameMutation.isPending}
            onClick={() => editNameMutation.mutate({ name, surname })}
          >
            {editNameMutation.isPending ? "Сохранение..." : "Сохранить изменения"}
          </button>
        </article>

        <article className={`${styles.card} ${styles.cardWide}`}>
          <div className={styles.cardHeader}>
            <span className={`${styles.cardIcon} ${styles.cardIconAccent}`}>
              <KeyRound size={18} />
            </span>
            <div>
              <h2>Сменить пароль</h2>
              <p className={styles.cardHint}>Используйте надёжный пароль длиной не менее 8 символов</p>
            </div>
          </div>
          <div className={styles.formGrid}>
            <label className={styles.field}>
              <span>Текущий пароль</span>
              <input
                type="password"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </label>
            <label className={styles.field}>
              <span>Новый пароль</span>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="new-password"
              />
            </label>
            <label className={styles.field}>
              <span>Подтверждение</span>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="new-password"
              />
            </label>
          </div>
          <button
            type="button"
            className={styles.primaryBtn}
            disabled={!oldPassword || !newPassword || !confirmPassword || editPasswordMutation.isPending}
            onClick={() =>
              editPasswordMutation.mutate({
                old_pwd: oldPassword,
                new_pwd: newPassword,
                confirm_pwd: confirmPassword,
              })
            }
          >
            {editPasswordMutation.isPending ? "Обновление..." : "Обновить пароль"}
          </button>
        </article>
      </div>
    </section>
  );
}
