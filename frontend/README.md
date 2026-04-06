# Frontend (React + TypeScript)

## Запуск

```bash
npm install
npm run dev
```

Frontend ожидает backend на `http://<host>:8000` и работает с cookie-auth (`credentials: include`).

## Сборка

```bash
npm run build
```

## Реализованные экраны

- Login (`/login`)
- Chat (`/`) с layout в стиле OpenAI: sidebar + основной чат
- Workspaces (`/workspaces`)
- Workspace details + files (`/workspaces/:workspaceId`)
