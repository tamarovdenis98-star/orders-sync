# Чек-лист подготовки (сделать ДО теста)

## Сервер
- [ ] DNS: A-запись `test.твойдомен` → IP VPS (или без домена: `SITE_ADDRESS=:80`, `PUBLIC_URL=http://IP`)
- [ ] SSH по ключу. В `C:\Users\<ты>\.ssh\config`:
      ```
      Host myvps
          HostName 1.2.3.4
          User root
          IdentityFile ~/.ssh/id_ed25519
      ```
      Проверка: `ssh myvps echo ok` выполняется без пароля.
- [ ] `ssh myvps 'bash -s' < scripts/server-setup.sh` ставит Docker и открывает порты 80/443.

## Проект
- [ ] Заполнить `deploy.conf`.
- [ ] В Git Bash: `./deploy.sh`. В конце должно быть `OK: https://...`. Открыть URL в браузере.
- [ ] GitHub: `git init && git add . && git commit -m init && gh repo create test-task --public --source=. --push`
- [ ] Запустить `claude` в этой папке и дать пробную задачу: «добавь эндпоинт /api/ping и задеплой».
      Убедиться, что он сам делает deploy → curl → commit → push.
- [ ] Репетиция с таймером на 20 минут (например, сокращатель ссылок). Потом `git reset` к шаблону.

## В день теста
1. Открыть Git Bash в `D:\test_project`, запустить `claude`.
2. Вставить текст задания целиком и добавить: «Работай по CLAUDE.md. Сначала минимальная версия и деплой».
3. Сдать ссылки (прод-URL + GitHub) **за 3 минуты до конца**, лучше раньше.

## Если что-то сломалось
- Логи: `ssh myvps "cd /opt/app && docker compose logs --tail=100"`
- Сертификат не выдаётся: проверь DNS и порт 80. Временно можно `SITE_ADDRESS=:80` и http по IP.
