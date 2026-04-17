# Xynera Frontend (Next.js)

This frontend uses Next.js App Router for the Signal-to-Action workspace experience.

## Stack

- Next.js (App Router)
- Tailwind CSS
- Lucide React
- Vercel AI SDK (`ai` package)

## Key routes

- `/` landing page
- `/login` sign in
- `/register` sign up
- `/workspace` protected campaign workspace with Ephemeral Interfaces

## Ephemeral interfaces

The workspace renders message cards dynamically by `ui_type`.

Current supported types:

- `signal_map`
- `variant_comparison`
- `channel_selector`

Renderer entrypoint: `components/ephemeral/EphemeralRenderer.jsx`

## Local development

```bash
npm install
npm run dev
```

## Production build

```bash
npm run build
npm run start
```
