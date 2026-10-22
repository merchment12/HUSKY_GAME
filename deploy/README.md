# Деплой на свой сервер (Debian/Ubuntu)

Домен покупать не нужно: Telegram требует валидный HTTPS, а бесплатного
имени на твой IP для этого достаточно.

## 1. Имя для сервера

**DuckDNS** (рекомендую, имя остаётся за тобой):
заходишь на duckdns.org через Telegram/GitHub/Google, придумываешь поддомен,
вписываешь IP сервера → получаешь `что-то.duckdns.org`.

**sslip.io** (вообще без регистрации): для IP `203.0.113.7` имя
`203-0-113-7.sslip.io` уже резолвится в него. Минус — при смене IP меняется имя.

```bash
IP=$(curl -s ifconfig.me); NAME="${IP//./-}.sslip.io"; echo "$NAME"
```

Проверь: `dig +short твоё-имя` должен вернуть IP сервера.

## 2. Сертификат

```bash
apt install nginx certbot python3-certbot-nginx
cp deploy/nginx-husky.conf /etc/nginx/sites-available/husky
sed -i 's/husky-mark.duckdns.org/ТВОЁ-ИМЯ/g' /etc/nginx/sites-available/husky
ln -s /etc/nginx/sites-available/husky /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d ТВОЁ-ИМЯ      # сам добавит блок https, ssl_* и продление
```
Порты 80 и 443 должны быть открыты — certbot проверяет домен по http.

## 3. Приложение

```bash
adduser --system --group --home /srv/husky husky
rsync -a server/ /srv/husky/server/
cp "Хаски_ Зов Севера (1).html" /srv/husky/index.html
cd /srv/husky && python3 -m venv .venv && .venv/bin/pip install -r server/requirements.txt
chown -R husky:husky /srv/husky

cp deploy/husky.env.example /etc/husky.env   # вписать BOT_TOKEN и своё имя
chmod 600 /etc/husky.env
cp deploy/husky.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now husky
journalctl -u husky -f
```

В логе должно быть `API на http://127.0.0.1:8080` и `webhook: https://…/tg/…`.

## 4. Telegram

1. @BotFather → `/newapp` → бот → Web App URL = `https://ТВОЁ-ИМЯ/` → короткое имя,
   например `play`. Получишь ссылку `https://t.me/твой_бот/play`.
2. В `/srv/husky/index.html` впиши в блоке `CFG` (около 493-й строки):
   ```js
   BOT_LINK: 'https://t.me/твой_бот/play',
   API: '',
   ```
3. `systemctl restart husky` не нужен — html читается при каждом запросе.

## Обновление игры

```bash
cp "Хаски_ Зов Севера (1).html" /srv/husky/index.html   # и всё
systemctl restart husky                                  # только если менялся код в server/
```

Сейвы лежат в `/var/lib/husky/husky.db`, бэкап — `sqlite3 ... ".backup"` или просто копия файла.
