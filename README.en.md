# Quick Share

[繁體中文](README.md) | English

A small file-drop website that runs on a personal Windows PC. Opening the home page gives you your own "room". Pick files or drag them onto the upload box and they upload automatically; then hand the share link (or its QR code) to anyone who should download them.

The interface is in Traditional Chinese.

- **No accounts.** Your room is remembered by a signed session cookie. Anyone with the share link can list and download; only the browser that owns the room can upload or delete.
- **Multiple files.** Files are uploaded one after another, each in its own request, so the total never trips the per-request size limit. Progress is shown while uploading and each file's result is listed afterwards.
- **Self-cleaning.** Each room keeps its 10 newest files (older ones are deleted), and a room with no new upload for 30 days is removed entirely. Both numbers, and the 100 MB per-file limit, are configurable.
- **Short links.** A room ID is 10 lowercase letters and digits, generated with Python's `secrets` module. It is the last segment of the share link.
- **No database.** Everything lives in the `uploads/` folder.
- **No front-end build step.** One Jinja template, one CSS file, one plain JavaScript file.

It is meant to sit behind Cloudflare, which provides HTTPS and limits a single request to 100 MB. The server itself only listens on `127.0.0.1`.

> The share link is the only thing protecting a room's files. Do not use this for confidential material.

## Requirements

- Windows
- Python 3.12

## Install

Open a command prompt in the project folder:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

To run the tests, also install:

```bat
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## Configure

1. Copy `.env.example` to `.env`.
2. Generate a secret key and paste it after `SECRET_KEY=` in `.env`:

   ```bat
   .venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
   ```

3. Adjust anything else you need. Changes take effect after a restart.

| Variable | Default | Meaning |
| --- | --- | --- |
| `SECRET_KEY` | required | Signs the session cookie. Changing it invalidates every owner's cookie. |
| `MAX_UPLOAD_MB` | `100` | Per-file size limit. Keep it at 100 or below behind Cloudflare. |
| `MAX_FILES_PER_ROOM` | `10` | Files kept per room; the oldest are deleted beyond this. |
| `ROOM_TTL_DAYS` | `30` | Days without a new upload before a room is deleted. |
| `OWNER_SESSION_DAYS` | `30` | Lifetime of the owner cookie, renewed on every visit. |
| `DISPLAY_NAME_LIMIT` | `12` | Characters kept at each end when a long file name is shortened. |
| `UPLOAD_DIR` | `uploads` | Where files are stored. Relative paths are resolved from the project root. |
| `LOG_FILE` | `logs/quickshare.log` | Log file location, resolved the same way. |
| `HOST` / `PORT` / `THREADS` | `127.0.0.1` / `5000` / `4` | waitress settings. Keep `HOST` at `127.0.0.1` behind Cloudflare. |
| `SESSION_COOKIE_SECURE` | `false` | Set to `true` when served over HTTPS. |

Notes:

- `.env` contains your secret key. It is listed in `.gitignore`; never commit it.
- Leave `SESSION_COOKIE_SECURE` at `false` when testing locally over `http://`. With `true`, the browser will not send the cookie over plain HTTP and every form will report that the page has expired.
- If a setting is missing or invalid, the program names the offending variable and exits.

## Run

Double-click `run.bat`, or run:

```bat
.venv\Scripts\python.exe run.py
```

Then open `http://127.0.0.1:5000/`. Press Ctrl+C to stop.

If startup reports that the address is already in use, another program is listening on that port. Close it, or change `PORT` in `.env`.

Logs are written to `logs/quickshare.log`.

## Test

```bat
.venv\Scripts\python.exe -m pytest
```

## Routes

| Path | Method | Who | Purpose |
| --- | --- | --- | --- |
| `/` | GET | cookie holder | Owner page |
| `/upload` | POST | cookie holder | Upload to your own room (CSRF token required) |
| `/share_view/<room_id>` | GET | anyone | Read-only share page |
| `/qrcode/<room_id>` | GET | anyone | QR code of the share link (PNG) |
| `/download/<room_id>/<filename>` | GET | anyone | Download as an attachment |
| `/remove/<room_id>/<filename>` | POST | room owner | Delete a file (CSRF token required) |

## Project layout

| Path | Purpose |
| --- | --- |
| `run.py` / `run.bat` | Load settings, build the app, start waitress |
| `app/__init__.py` | Application factory: `create_app(config)` |
| `app/config.py` | Read and validate `.env` |
| `app/storage.py` | Every file operation: room IDs, file-name cleaning, path safety, save, list, delete, expiry |
| `app/views.py` | Routes |
| `app/errors.py` | Error pages and logging |
| `app/messages.py` | All user-facing text |
| `app/templates/` | HTML templates |
| `app/static/` | CSS, JavaScript, icons |
| `tests/` | Automated tests |
| `docs/教學.md` | A walkthrough of the architecture, from the network layer up to the browser (Traditional Chinese) |

`app/storage.py` is the only module that touches the file system. Routes never build paths themselves, so the checks against path traversal live in one place.

## Security notes

- Room IDs and stored file names are validated against strict patterns, and the resolved path is checked to be inside the room folder before any read, write, or delete.
- Uploaded file names are reduced to Chinese characters, letters, digits, `.`, `_` and `-`. A random prefix keeps files with the same name from overwriting each other.
- Uploads are written to a temporary `.part` file and renamed when complete, so a half-uploaded file is never listed or downloadable.
- Upload and delete require a CSRF token. The session cookie is `HttpOnly` and `SameSite=Lax`.
- Downloads are always sent as attachments with `X-Content-Type-Options: nosniff`.
- The app trusts one proxy hop for `X-Forwarded-Proto`, so share links and QR codes use `https://` behind Cloudflare. Do not expose waitress directly to a network.
