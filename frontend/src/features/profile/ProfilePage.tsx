import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useSession } from "../auth/useSession";
import { api } from "../../shared/api/client";
import styles from "./ProfilePage.module.css";

export function ProfilePage() {
  const queryClient = useQueryClient();
  const session = useSession();
  const [name, setName] = useState("");
  const [surname, setSurname] = useState("");
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    if (!session.data) return;
    setName(session.data.name ?? "");
    setSurname(session.data.surname ?? "");
  }, [session.data]);

  const editNameMutation = useMutation({
    mutationFn: api.profileEditNameSurname,
    onSuccess: async (profile) => {
      setFeedback("Профиль обновлен");
      await queryClient.setQueryData(["session"], profile);
    },
    onError: (error) => setFeedback((error as Error).message),
  });

  const editPasswordMutation = useMutation({
    mutationFn: api.profileEditPassword,
    onSuccess: () => {
      setFeedback("Пароль успешно изменен");
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
    },
    onError: (error) => setFeedback((error as Error).message),
  });

  if (session.isLoading) return <section className={styles.page}>Загрузка...</section>;
  if (session.error || !session.data) return <section className={styles.page}>Не удалось загрузить профиль.</section>;

  return (
    <section className={styles.page}>
      <h1>Профиль</h1>

      <article className={styles.card}>
        <h2>Основная информация</h2>
        <div className={styles.meta}>
          <div><span>Логин:</span> {session.data.login}</div>
          <div><span>Роль:</span> {session.data.role}</div>
          <div><span>Статус:</span> {session.data.admin ? "Администратор" : "Пользователь"}</div>
          <div><span>Создан:</span> {session.data.created_at}</div>
        </div>
      </article>

      <article className={styles.card}>
        <h2>Изменить ФИО</h2>
        <div className={styles.grid}>
          <input placeholder="Имя" value={name} onChange={(e) => setName(e.target.value)} />
          <input placeholder="Фамилия" value={surname} onChange={(e) => setSurname(e.target.value)} />
        </div>
        <button
          className={styles.button}
          disabled={editNameMutation.isPending}
          onClick={() => editNameMutation.mutate({ name, surname })}
        >
          Сохранить
        </button>
      </article>

      <article className={styles.card}>
        <h2>Сменить пароль</h2>
        <div className={styles.grid}>
          <input
            type="password"
            placeholder="Старый пароль"
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
          />
          <input
            type="password"
            placeholder="Новый пароль"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />
          <input
            type="password"
            placeholder="Подтвердите новый пароль"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
          />
        </div>
        <button
          className={styles.button}
          disabled={!oldPassword || !newPassword || !confirmPassword || editPasswordMutation.isPending}
          onClick={() => editPasswordMutation.mutate({ old_pwd: oldPassword, new_pwd: newPassword, confirm_pwd: confirmPassword })}
        >
          Обновить пароль
        </button>
      </article>

      {feedback ? <div className={styles.feedback}>{feedback}</div> : null}
    </section>
  );
}
