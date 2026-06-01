# nodejs-dev — Node.js Development Skill

## Inicialización de Proyectos
- **Express:** `npm init -y && npm install express`
- **NestJS:** `npm install -g @nestjs/cli && nest new project-name`
- **Next.js:** `npx create-next-app@latest project-name`
- **Testing:** Jest (`npm install --save-dev jest`) o Vitest (`npm install --save-dev vitest`)

## Comandos Útiles
- `npm run dev` / `npm start` / `npm test`
- `npx prisma generate` — Cliente Prisma
- `npx prisma migrate dev` — Migraciones Prisma

## Debugging
- Usar `node --inspect` + Chrome DevTools
- `node --inspect-brk` para pausar al inicio

## Buenas Prácticas
- Usar ES Modules (type: "module" en package.json)
- ESLint + Prettier para formato consistente
- Manejo de errores con try/catch async
- Variables de entorno via dotenv
