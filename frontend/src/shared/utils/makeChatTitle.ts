const MAX_CHAT_TITLE_LEN = 80;

export function makeChatTitle(message: string): string {
  const text = message.trim().replace(/\s+/g, " ");
  if (!text) return "Новый чат";
  if (text.length <= MAX_CHAT_TITLE_LEN) return text;
  return `${text.slice(0, MAX_CHAT_TITLE_LEN - 1).trimEnd()}…`;
}
