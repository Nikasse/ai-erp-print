# Environment Check

Чекліст перевірки локального середовища розробки.

## Cursor

- [x] Cursor встановлений і запущений — 20 активних процесів

## Docker

- [x] Docker Desktop встановлений

```bash
docker --version
# Docker version 29.5.3, build d1c06ef
```

- [x] Docker-демон запущений — Server: 29.5.3
- [x] Контейнер `vibrant_johnson` (nginx:alpine) — Up 13 hours, порт 8080

```bash
docker ps
# vibrant_johnson | nginx:alpine | Up 13 hours
```

## localhost

- [x] `localhost:8080` — HTTP 200 (nginx з контейнера `vibrant_johnson`)
- [ ] Dev-сервер проекту не запущений — жодного порту (3000, 3001, 4000, 5173, 8000) не відповідає

```bash
# Запустити dev-сервер:
npm run dev
```

## ngrok-тунель

- [x] ngrok встановлений

```bash
ngrok version
# ngrok version 3.39.8
```

- [ ] Тунель не активний — запустити після старту dev-сервера

```bash
ngrok http <PORT>
```

---

**Статус:** частково готове — потрібен запущений dev-сервер  
**Дата перевірки:** 2026-06-26
