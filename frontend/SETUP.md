# 🔧 Frontend Setup Guide

## Quick Start

### 1. Install Dependencies
```bash
cd frontend
npm install
```

### 2. Environment Variables

Copy the example file and configure:
```bash
cp .env.example .env.local
```

Edit `.env.local`:
```env
# Required for Google OAuth
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com

# Optional - API base URL (defaults to /api which uses Next.js rewrites)
NEXT_PUBLIC_API_BASE_URL=/api

# Django backend origin (used by rewrites and media proxy)
NEXT_PUBLIC_BACKEND_ORIGIN=http://localhost:8000
```

### 3. Get Google OAuth Credentials

Quick steps:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create project → Create OAuth credentials (Web application)
3. Add `http://localhost:3000` and `http://127.0.0.1:3000` to authorized JavaScript origins
4. Copy Client ID to `.env.local` and restart `npm run dev`

### 4. Start Development Server

```bash
npm run dev
```

Frontend will be available at `http://localhost:3000`

---

## 📁 Project Structure

```
frontend/
├── app/                      # Next.js App Router pages
│   ├── __tests__/           # Page tests
│   ├── backoffice/          # Protected backoffice
│   ├── sign-in/             # Sign in page (email + Google)
│   ├── sign-up/             # Sign up page (email + Google)
│   ├── forgot-password/     # Password reset flow
│   ├── dashboard/           # Protected user dashboard
│   ├── catalog/             # Product catalog
│   ├── products/[productId]/ # Product detail pages
│   ├── blogs/               # Blog list
│   ├── blogs/[blogId]/      # Blog detail pages
│   ├── checkout/            # Checkout page
│   ├── providers.tsx        # App providers
│   └── page.tsx             # Home page
├── components/              # React components
│   ├── layout/              # Header, Footer
│   ├── product/             # ProductCard, ProductCarousel
│   └── blog/                # BlogCard, BlogCarousel
├── lib/                     # Utilities and stores
│   ├── __tests__/           # Fixtures/helpers
│   ├── constants.ts         # Shared constants
│   ├── hooks/               # Reusable hooks
│   ├── i18n/                # Localization
│   ├── stores/              # Zustand state management
│   │   ├── authStore.ts     # Authentication state
│   │   ├── cartStore.ts     # Shopping cart
│   │   ├── productStore.ts
│   │   ├── blogStore.ts
│   │   └── localeStore.ts
│   ├── services/            # API services
│   │   ├── http.ts          # Axios instance
│   │   └── tokens.ts        # Token management
│   └── types.ts             # TypeScript types
└── e2e/                     # Playwright E2E tests
```

---

## 🧪 Testing

### Unit Tests
```bash
npm run test              # Run unit tests (Jest)
npm run test:watch        # Unit tests in watch mode
npm run test:ci           # Unit tests in CI mode
npm run test:coverage     # Unit tests with coverage + summary
```

### E2E Tests
```bash
npm run test:e2e          # All E2E tests
npm run e2e               # Alias for test:e2e
npm run test:e2e:ui       # Interactive UI
npm run test:e2e:headed   # With visible browser
npm run test:e2e:debug    # Debug mode
npm run e2e:desktop       # Desktop Chrome only
npm run e2e:mobile        # Mobile Chrome only
npm run e2e:tablet        # Tablet only
npm run e2e:clean         # Clear Playwright reports
```

### All Tests
```bash
npm run test:all          # Unit coverage + E2E
```

---

## 🚀 Available Scripts

```json
{
  "dev": "Start development server (Next.js)",
  "build": "Build for production",
  "start": "Start production server",
  "lint": "Run ESLint",
  "test": "Run unit tests (Jest)",
  "test:watch": "Unit tests in watch mode",
  "test:ci": "Unit tests in CI mode",
  "test:coverage": "Unit tests with coverage + summary",
  "test:e2e": "Run Playwright E2E tests",
  "test:e2e:ui": "E2E with Playwright UI",
  "test:e2e:headed": "E2E with visible browser",
  "test:e2e:debug": "E2E in debug mode",
  "e2e": "Alias for test:e2e",
  "e2e:desktop": "E2E on Desktop Chrome",
  "e2e:mobile": "E2E on Mobile Chrome",
  "e2e:tablet": "E2E on Tablet",
  "e2e:clean": "Clean Playwright reports",
  "e2e:coverage": "Clean reports then run all E2E tests",
  "test:all": "Run unit coverage + E2E"
}
```

---

## 🔐 Authentication Pages

### Sign In (`/sign-in`)
- Email/password form
- Google OAuth button
- Link to forgot password
- Link to sign up

### Sign Up (`/sign-up`)
- Email/password registration form
- Optional first name and last name
- Password confirmation
- Google OAuth button
- Link to sign in

### Forgot Password (`/forgot-password`)
- Paso 1: introducir el email y recibir un token de recuperación.
- Paso 2: pegar el token completo (hasta 64 caracteres, con letras y separadores), introducir contraseñas coincidentes de al menos ocho caracteres y enviar.
- El token caduca a los 15 minutos; pedir otro reemplaza los anteriores y cambiar la contraseña consume los pendientes. Las rutas API y el campo `code` se conservan.
- Los códigos de seis dígitos anteriores se invalidan mediante la migración 0006; es necesario solicitar un token nuevo.

---

## 📊 State Management (Zustand)

### Auth Store
```typescript
import { useAuthStore } from '@/lib/stores/authStore';

const {
  isAuthenticated,
  user,
  signIn,
  signUp,
  googleLogin,
  signOut,
  sendPasswordResetCode,
  resetPassword,
} = useAuthStore();
```

### Cart Store
```typescript
import { useCartStore } from '@/lib/stores/cartStore';

const {
  items,
  addToCart,
  removeFromCart,
  updateQuantity,
  clearCart,
  subtotal,
} = useCartStore();
```

---

## 🐛 Troubleshooting

### Images not loading

**Problem:** Products and blogs show empty cards without images

**Solution:** Make sure both servers are running:
```bash
# Terminal 1: Backend
cd backend && source venv/bin/activate && python manage.py runserver

# Terminal 2: Frontend
cd frontend && npm run dev
```

The backend needs to be running on `http://localhost:8000` for images to load via the Next.js proxy.

### Google OAuth not working

Common issues:
- Missing `NEXT_PUBLIC_GOOGLE_CLIENT_ID` in `.env.local`
- Authorized JavaScript origins not configured in Google Cloud Console
- Need to restart server after changing `.env.local`

### Port already in use

```bash
# Kill process on port 3000
lsof -ti:3000 | xargs -r kill -9

# Kill process on port 8000  
lsof -ti:8000 | xargs -r kill -9
```

---

## Documentation

| Guide | Scope |
|-------|-------|
| [`TESTING.md`](./TESTING.md) | Unit tests (Jest + RTL): tools, structure, coverage, commands, best practices |
| [`e2e/README.md`](./e2e/README.md) | E2E tests (Playwright): structure, commands, Flow Coverage system, flow definitions |

---

**Last Updated:** 2026-10-10


## Validación aislada de la ronda 4

Django 6.1.1 exige MySQL 8.4 o posterior. SQLite permite validar reglas y migraciones, pero no demuestra la serialización de `select_for_update`.

La validación de recuperación y producto utiliza un worktree propio, datos sintéticos, correo en memoria y `PYTHON_DOTENV_DISABLED=1`; no reutiliza `.env`, bases reales ni servidores de los puertos habituales. Las pruebas se seleccionan por archivo/caso: máximo veinte casos por ejecución, tres comandos por ciclo y dos archivos E2E. Las rutas con corchetes de Jest se pasan mediante `--runTestsByPath`.

Para producto, una respuesta 404 muestra inexistencia; un fallo temporal muestra **Product unavailable** y permite **Retry**. La auditoría E2E del SHA final debe comprobar ambos estados y la recuperación en una app real aislada. Los cinco tamaños responsive requieren su propia medición; Desktop Chrome no los certifica.
