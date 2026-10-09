# Launch posts

Image: `docs/social.png` (above the fold) or `docs/screenshot.png` (full page).
Repo link is filled in.

## LinkedIn (English)

"Which port is the blog on again?"

If you run several docker-compose stacks behind a host-level nginx, you've asked this before. Every Django app listens on 8000 inside its container, each is mapped to a different host port, and the answer lives in your head, an nginx file and the output of `ss -tlnp`.

I built port-catalog to answer it in one page. It's a small, read-only tool that merges:

• Docker publish mappings (grouped by compose project)
• UFW rules
• nginx server_name and proxy_pass
• raw host sockets, with the process name behind each one (nginx on 80, postgres on 5432)

It also warns about something that surprises a lot of people: Docker bypasses UFW. A port published on 0.0.0.0 can be reachable from outside even with no UFW allow rule. Every external bind gets flagged, with the safer `127.0.0.1:<port>` mapping suggested.

And it suggests the next free host ports, so you stop guessing.

• One image, no database, no CDN, works on air-gapped servers
• Web UI, JSON API and a one-shot CLI
• Binds to 127.0.0.1 by default and never modifies Docker, UFW or nginx
• Run it with `docker compose up -d --build`, or with uv and no image at all

Open source, MIT licensed: https://github.com/isalehgholami/port-catalog

#opensource #docker #devops #nginx #selfhosted

## Telegram (فارسی)

🔎 **port-catalog** — کدوم پورت مال کدوم پروژه‌ست؟

اگه روی یه سرور چند تا stack دارید و جلوشون یه nginx روی خود هاست، حتماً این سؤال رو داشتید: «بلاگ روی چه پورتی بود؟» همه‌ی Django ها داخل کانتینر روی ۸۰۰۰ هستن، هرکدوم یه پورت متفاوت روی هاست دارن، و جواب پخش شده بین `docker ps` و `ss -tlnp` و فایل‌های nginx.

یه ابزار کوچیک و **فقط‌خواندنی** ساختم که همه‌ی اینا رو تو یه صفحه جمع می‌کنه:

• پورت‌های Docker به تفکیک پروژه‌ی compose
• قوانین UFW
• server_name و proxy_pass های nginx
• سوکت‌های خود هاست، همراه با اسم پروسه (پورت ۸۰ → nginx، پورت ۵۴۳۲ → postgres)

⚠️ و یه هشدار مهم: Docker قوانین UFW رو دور می‌زنه. پورتی که روی 0.0.0.0 publish شده حتی بدون rule در UFW هم از بیرون در دسترسه. این ابزار همه‌ی این موارد رو علامت می‌زنه و حالت امن‌تر (`127.0.0.1:پورت`) رو پیشنهاد می‌ده.

بعلاوه پورت‌های آزاد بعدی رو بهتون می‌گه که دیگه حدس نزنید.

✅ یه image کوچیک، بدون دیتابیس، بدون CDN (روی سرور ایزوله هم کار می‌کنه)
✅ رابط وب + API + CLI
✅ پیش‌فرض فقط روی 127.0.0.1 و هیچ چیزی رو تغییر نمی‌ده
✅ با `docker compose up -d --build` یا با uv و بدون image

اوپن‌سورس با لایسنس MIT: https://github.com/isalehgholami/port-catalog

#docker #devops #nginx #opensource
