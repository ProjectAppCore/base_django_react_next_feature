# User Flow Map

**Single source of truth for all user flows in the application.**

Use this document to understand each flow's steps, branching conditions, role restrictions, and API contracts before writing or reviewing E2E tests.

**Version:** 1.0.2
**Last Updated:** 2026-10-10

Actualización de ronda 4: recuperación con token completo y detalle de producto que distingue ausencia de indisponibilidad temporal. La ejecución final de QA se acredita por separado; este mapa describe el comportamiento implementado. El registro ejecutable de los flujos E2E está en `frontend/e2e/flow-definitions.json`.

---

## Table of Contents

1. [Module Index](#module-index)
2. [Auth Module](#auth-module)
3. [Public Module](#public-module)
4. [App Module](#app-module)
5. [Backoffice Module](#backoffice-module)
6. [Cross-Reference](#cross-reference)

---

## Module Index

| Flow ID | Name | Module | Priority | Roles | Frontend Route |
|---------|------|--------|----------|-------|----------------|
| `auth-sign-in` | Sign In | auth | P1 | guest | `/sign-in` |
| `auth-sign-up` | Sign Up | auth | P1 | guest | `/sign-up` |
| `auth-google-login` | Google OAuth Login | auth | P2 | guest | `/sign-in`, `/sign-up` |
| `auth-forgot-password` | Forgot Password | auth | P2 | guest | `/forgot-password` |
| `auth-sign-out` | Sign Out | auth | P2 | user | `/dashboard` |
| `auth-session-persistence` | Session Persistence | auth | P2 | user | any protected route |
| `auth-backoffice-access` | Acceso administrativo | auth | P1 | guest, user, staff | `/dashboard`, `/backoffice` |
| `public-home` | Home Page | public | P2 | guest | `/` |
| `public-navigation` | Site Navigation | public | P3 | guest | all pages |
| `public-catalog-browse` | Browse Catalog | public | P2 | guest | `/catalog` |
| `public-product-detail` | Product Detail | public | P2 | guest | `/products/[productId]` |
| `public-blogs-browse` | Browse Blogs | public | P3 | guest | `/blogs` |
| `public-blog-detail` | Blog Detail | public | P3 | guest | `/blogs/[blogId]` |
| `app-cart-add` | Add to Cart | app | P1 | guest | `/products/[productId]` |
| `app-cart-manage` | Manage Cart | app | P1 | guest | `/checkout` |
| `app-cart-persistence` | Cart Persistence | app | P2 | guest | `/checkout` |
| `app-checkout-complete` | Complete Checkout | app | P1 | guest | `/checkout` |
| `app-dashboard` | Dashboard | app | P2 | user | `/dashboard` |
| `backoffice-users-list` | Users List | backoffice | P2 | staff | `/backoffice` |
| `backoffice-sales-list` | Sales List | backoffice | P2 | staff | `/backoffice` |

---

## Auth Module

### auth-sign-in

| Field | Value |
|-------|-------|
| **Priority** | P1 |
| **Roles** | guest |
| **Frontend route** | `/sign-in` |
| **API endpoints** | `POST /api/sign_in/` |

**Preconditions:** User is not authenticated. A registered account exists.

**Steps:**

1. User navigates to `/sign-in`.
2. Page renders form with **Email**, **Password** fields and **Sign in** button.
3. User fills in email and password.
4. User clicks **Sign in**.
5. Frontend sends `POST /api/sign_in/` with `{ email, password }`.
6. Backend validates credentials and returns `{ access, refresh }` (HTTP 200).
7. Frontend stores tokens in cookies (`access_token`, `refresh_token`).
8. Frontend redirects to `/dashboard`.

**Branching conditions:**

| Condition | Behavior |
|-----------|----------|
| Empty email or password | HTML `required` prevents submission |
| Email not registered | `401 { error: "Invalid credentials" }` — error below form |
| Wrong password | `401 { error: "Invalid credentials" }` — error below form |
| Account inactive | `403 { error: "Account is inactive" }` — error below form |

---

### auth-sign-up

| Field | Value |
|-------|-------|
| **Priority** | P1 |
| **Roles** | guest |
| **Frontend route** | `/sign-up` |
| **API endpoints** | `POST /api/sign_up/` |

**Preconditions:** User is not authenticated.

**Steps:**

1. User navigates to `/sign-up`.
2. Page renders form: **First Name**, **Last Name**, **Email**, **Password**, **Confirm Password**, **Create account** button.
3. User fills in all fields.
4. User clicks **Create account**.
5. Frontend validates passwords match and length >= 8.
6. Frontend sends `POST /api/sign_up/` with `{ email, password, first_name, last_name }`.
7. Backend creates user and returns `{ access, refresh }` (HTTP 201).
8. Frontend stores tokens and redirects to `/dashboard`.

**Branching conditions:**

| Condition | Behavior |
|-----------|----------|
| Passwords do not match | Client error: "Passwords do not match" — no API call |
| Password < 8 chars | Client error: "Password must be at least 8 characters" — no API call |
| Email already registered | `400 { error: "User with this email already exists" }` |
| Missing email or password | `400 { error: "Email and password are required" }` |

---

### auth-google-login

| Field | Value |
|-------|-------|
| **Priority** | P2 |
| **Roles** | guest |
| **Frontend route** | `/sign-in`, `/sign-up` |
| **API endpoints** | `POST /api/google_login/` |

**Preconditions:** `NEXT_PUBLIC_GOOGLE_CLIENT_ID` env var is set. User is not authenticated.

**Steps:**

1. User navigates to `/sign-in` or `/sign-up`.
2. Google Sign-In button rendered via `@react-oauth/google`.
3. User clicks Google button and completes OAuth consent.
4. Frontend receives credential JWT, decodes `email`, `given_name`, `family_name`, `picture`.
5. Frontend sends `POST /api/google_login/` with `{ credential, email, given_name, family_name, picture }`.
6. Backend validates token via Google tokeninfo, gets or creates user.
7. Backend returns `{ access, refresh, created, google_validated }` (HTTP 200).
8. Frontend stores tokens and redirects to `/dashboard`.

**Branching conditions:**

| Condition | Behavior |
|-----------|----------|
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` missing | "Missing NEXT_PUBLIC_GOOGLE_CLIENT_ID" shown instead of button |
| Credential missing | `400 { error: "Google credential is required" }` |
| Invalid credential (prod) | `401 { error: "Invalid Google credential" }` |
| Audience mismatch (prod) | `401 { error: "Invalid Google client" }` |
| New user | User created with unusable password; `created: true` |
| Existing user | Matched by email; names updated if blank |

---

### auth-forgot-password

| Field | Value |
|-------|-------|
| **Priority** | P2 |
| **Roles** | guest |
| **Frontend route** | `/forgot-password` |
| **API endpoints** | `POST /api/send_passcode/`, `POST /api/verify_passcode_and_reset_password/` |

**Display:** Desde **Forgot password?** en sign-in, el usuario accede al formulario de email. Una solicitud aceptada abre el paso con **Recovery code**, **New Password**, **Confirm New Password**, **Reset password** y **Back to email**.

**Success:**

1. El usuario escribe su email y pulsa **Send verification code**.
2. Para una cuenta existente, el servidor genera un token de Django ligado al estado de la contraseña, invalida los tokens pendientes anteriores y envía el token por correo. La API conserva las rutas y el campo `code`.
3. El usuario pega el token completo; el input admite hasta 64 caracteres y conserva letras y separadores. Introduce contraseñas coincidentes de al menos ocho caracteres.
4. Al pulsar **Reset password**, la API verifica el token y su vigencia menor a 15 minutos, cambia la contraseña e invalida los tokens pendientes en una transacción protegida por el lock de la cuenta.
5. HTTP 200 redirige a `/sign-in`.

**Error:**

| Condition | Behavior |
|-----------|----------|
| Email desconocido al solicitar | HTTP 200 con mensaje genérico; la página avanza al paso de recuperación |
| Campos obligatorios ausentes | HTTP 400; no cambia la contraseña |
| Token inválido, vencido, reemplazado o utilizado | HTTP 400 `Invalid or expired code`; se conserva el formulario y el token escrito |
| Contraseñas no coincidentes | `Passwords do not match`; no se envía el reset |
| Nueva contraseña menor a ocho caracteres | `Password must be at least 8 characters`; el cliente y la API rechazan la entrada |
| **Back to email** | Regresa al primer paso |

**Failure:** Si el envío de correo falla, la API responde HTTP 500 `Failed to send email`, invalida el token de esa solicitud y el formulario mantiene visible el error de envío. Una excepción interna del reset conserva la respuesta genérica y registra únicamente una operación fija y la clase de excepción, sin texto sensible ni traceback.

**Límite:** El token fuerte reduce el riesgo de adivinar un código corto; esta ronda no añade cuotas persistentes de emisión o verificación ni certifica protección contra abuso del envío de correo. La serialización se comprueba en MySQL aislado; SQLite no acredita `select_for_update`.

---

### auth-sign-out

| Field | Value |
|-------|-------|
| **Priority** | P2 |
| **Roles** | user |
| **Frontend route** | `/dashboard` |
| **API endpoints** | None (client-side only) |

**Preconditions:** User is authenticated.

**Steps:**

1. User is on `/dashboard`.
2. User clicks **Sign out** button.
3. Frontend clears JWT tokens from cookies via `authStore.signOut()`.
4. User is redirected to `/sign-in` (or home) by the auth guard.

**Branching conditions:** None — sign-out is always client-side.

---

### auth-session-persistence

| Field | Value |
|-------|-------|
| **Priority** | P2 |
| **Roles** | user |
| **Frontend route** | any protected route |
| **API endpoints** | `GET /api/validate_token/`, `POST /api/token/refresh/` |

**Preconditions:** User has valid tokens in cookies.

**Steps:**

1. User navigates to a protected route (`/dashboard`, `/backoffice`).
2. Frontend reads `access_token` from cookies.
3. Frontend sends `GET /api/validate_token/` with Bearer token.
4. Backend validates JWT and returns `{ valid: true, user: { id, email, first_name, last_name, role, is_staff } }`.
5. User is shown the protected content.

**Branching conditions:**

| Condition | Behavior |
|-----------|----------|
| No tokens in cookies | Redirect to `/sign-in` via `useRequireAuth` hook |
| Access token expired | Frontend calls `POST /api/token/refresh/` with refresh token |
| Refresh token expired | Redirect to `/sign-in` |

---

## Public Module

### public-home

| Field | Value |
|-------|-------|
| **Priority** | P2 |
| **Roles** | guest |
| **Frontend route** | `/` |
| **API endpoints** | `GET /api/products-data/`, `GET /api/blogs-data/` |

**Preconditions:** None.

**Steps:**

1. User navigates to `/`.
2. Page renders hero section with heading "Everything you need, in one place".
3. CTA buttons: **Shop now** (→ `/catalog`), **Read blogs** (→ `/blogs`), **Go to cart** (→ `/checkout`).
4. **ProductCarousel** component loads products from API and displays cards.
5. **BlogCarousel** component loads blogs from API and displays cards.

**Branching conditions:**

| Condition | Behavior |
|-----------|----------|
| Products API unavailable | Carousel shows empty or error state |
| Blogs API unavailable | Carousel shows empty or error state |

---

### public-navigation

| Field | Value |
|-------|-------|
| **Priority** | P3 |
| **Roles** | guest |
| **Frontend route** | all pages |
| **API endpoints** | None |

**Preconditions:** None.

**Steps:**

1. Every page renders a shared header with navigation links.
2. Header contains links to: Home (`/`), Catalog (`/catalog`), Blogs (`/blogs`), Sign-in (`/sign-in`).
3. Footer is present on all pages.
4. Navigation links work across page transitions.
5. Browser back/forward buttons maintain correct history.

**Branching conditions:** None — purely structural.

---

### public-catalog-browse

| Field | Value |
|-------|-------|
| **Priority** | P2 |
| **Roles** | guest |
| **Frontend route** | `/catalog` |
| **API endpoints** | `GET /api/products-data/` |

**Preconditions:** None.

**Steps:**

1. User navigates to `/catalog`.
2. Page displays heading "Catalog" with loading skeleton.
3. Frontend fetches `GET /api/products-data/` via `productStore.fetchProducts()`.
4. Products render as a grid of `ProductCard` components (image, title, price).
5. Each card links to `/products/[productId]`.

**Branching conditions:**

| Condition | Behavior |
|-----------|----------|
| API loading | Skeleton grid (12 placeholders) shown |
| API error | "Catalog unavailable" message with **Retry** button |
| No products in DB | "No products yet" dashed-border message |

---

### public-product-detail

| Field | Value |
|-------|-------|
| **Priority** | P2 |
| **Roles** | guest |
| **Frontend route** | `/products/[productId]` |
| **API endpoints** | `GET /api/products/{productId}/` |

**Display:** El usuario abre una tarjeta del catálogo y ve loading mientras la API obtiene el producto; una respuesta 200 muestra título, precio, descripción, galería y **Add to cart**.

**Branching conditions:**

| Condition | Behavior | Outcome |
|-----------|----------|---------|
| ID no numérico | `Product not found.` y **Back to catalog**, sin consultar la API | error |
| API 404 | `Product not found.` y **Back to catalog**, sin Retry | error |
| Fallo temporal de red o servidor | `Product unavailable`, explicación, **Retry** y **Back to catalog** | failure |
| Retry devuelve 200 | Loading termina y aparece el producto solicitado | success |
| Retry vuelve a fallar | Permanece el estado recuperable | failure |
| Retry devuelve 404 | Cambia al estado de producto inexistente | error |
| Navegación a otro producto | La resolución o rechazo anterior no sobrescribe la vista actual | display |
| Sin imágenes | Placeholder en lugar de galería | display |

Retry dispara una sola nueva consulta; durante loading no aparece el botón. No hay reintentos automáticos. **Add to cart** conserva el flujo `app-cart-add`.

---

### public-blogs-browse

| Field | Value |
|-------|-------|
| **Priority** | P3 |
| **Roles** | guest |
| **Frontend route** | `/blogs` |
| **API endpoints** | `GET /api/blogs-data/` |

**Preconditions:** None.

**Steps:**

1. User navigates to `/blogs`.
2. Page displays heading "Blogs" with loading skeleton.
3. Frontend fetches `GET /api/blogs-data/` via `blogStore.fetchBlogs()`.
4. Blogs render as a grid of `BlogCard` components.
5. Each card links to `/blogs/[blogId]`.

**Branching conditions:**

| Condition | Behavior |
|-----------|----------|
| API loading | Skeleton grid (9 placeholders) shown |
| API error | "Blogs unavailable" message with **Retry** button |
| No blogs in DB | "No blogs yet" dashed-border message |

---

### public-blog-detail

| Field | Value |
|-------|-------|
| **Priority** | P3 |
| **Roles** | guest |
| **Frontend route** | `/blogs/[blogId]` |
| **API endpoints** | `GET /api/blogs-data/[blogId]/` |

**Preconditions:** La ruta contiene un identificador de blog; puede ser inválido o corresponder a un blog inexistente.

**Steps:**

1. User navigates to `/blogs/[blogId]`.
2. Con un identificador válido, la página muestra "Loading..." mientras pide el detalle.
3. Si el blog existe, muestra su título, contenido y media asociada.
4. El usuario puede volver a `/blogs`; si ocurre un fallo temporal, puede pulsar **Retry**.

**Branching conditions:**

| Condition | Behavior |
|-----------|----------|
| Identificador inválido o API `404` | "Blog not found." y enlace **Back to blogs**; termina la carga |
| Fallo de red o API `5xx` | "Blog unavailable" y botón **Retry**; termina la carga |
| Retry tras un fallo temporal | Vuelve a pedir el detalle; una respuesta correcta muestra el blog |
| Cambia el identificador durante una petición | Se ignora la respuesta anterior para no mostrar otro blog |

Registro E2E relacionado: `blog-detail-view`, con resultados `display`, `error`, `failure` y `success`.

---

## App Module

### app-cart-add

| Field | Value |
|-------|-------|
| **Priority** | P1 |
| **Roles** | guest |
| **Frontend route** | `/products/[productId]` |
| **API endpoints** | None (client-side state via Zustand + localStorage) |

**Preconditions:** User is on a product detail page.

**Steps:**

1. User views a product on `/products/[productId]`.
2. User clicks **Add to cart** button.
3. `cartStore.addToCart(product, 1)` adds the product with quantity 1 to local state.
4. Cart state persists to `localStorage`.
5. User can navigate to `/checkout` to see the item.

**Branching conditions:**

| Condition | Behavior |
|-----------|----------|
| Product already in cart | Quantity incremented |
| Product not in cart | New entry added with quantity 1 |

---

### app-cart-manage

| Field | Value |
|-------|-------|
| **Priority** | P1 |
| **Roles** | guest |
| **Frontend route** | `/checkout` |
| **API endpoints** | None (client-side state) |

**Preconditions:** User has at least one item in cart.

**Steps:**

1. User navigates to `/checkout`.
2. Cart section displays each item: image, title, price, quantity input, **Remove** button, line total.
3. **Update quantity:** User changes the number input → `cartStore.updateQuantity(id, qty)`.
4. **Remove item:** User clicks **Remove** → `cartStore.removeFromCart(id)`.
5. **Subtotal** recalculates automatically: `items.reduce((acc, item) => acc + item.price * item.quantity, 0)`.

**Branching conditions:**

| Condition | Behavior |
|-----------|----------|
| Cart is empty | "Your cart is empty." message; checkout button disabled |
| Single item removed | If last item, shows empty cart message |
| Quantity set to 0 or negative | Minimum enforced by `min={1}` on input |

---

### app-cart-persistence

| Field | Value |
|-------|-------|
| **Priority** | P2 |
| **Roles** | guest |
| **Frontend route** | `/checkout` |
| **API endpoints** | None |

**Preconditions:** User has items in cart.

**Steps:**

1. User adds products to cart (see `app-cart-add`).
2. User reloads the page or navigates away and returns.
3. Cart state is restored from `localStorage` via Zustand persist middleware.
4. All items, quantities, and subtotal remain intact.

**Branching conditions:**

| Condition | Behavior |
|-----------|----------|
| localStorage cleared | Cart resets to empty |
| Corrupt localStorage data | Cart may reset to empty (Zustand default) |

---

### app-checkout-complete

| Field | Value |
|-------|-------|
| **Priority** | P1 |
| **Roles** | guest |
| **Frontend route** | `/checkout` |
| **API endpoints** | `POST /api/create-sale/` |

**Preconditions:** User has at least one item in cart.

**Steps:**

1. User navigates to `/checkout` with items in cart.
2. Shipping form displays: **Email**, **Address**, **City**, **State**, **Postal code** fields.
3. User fills in all shipping fields.
4. **Complete checkout** button becomes enabled (requires non-empty cart).
5. User clicks **Complete checkout**.
6. Frontend builds payload:
   ```json
   {
     "email": "...",
     "address": "...",
     "city": "...",
     "state": "...",
     "postal_code": "...",
     "sold_products": [{ "product_id": 1, "quantity": 2 }, ...]
   }
   ```
7. Frontend sends `POST /api/create-sale/` with payload.
8. El backend crea la venta, sus líneas y sus relaciones en una sola transacción (HTTP `201`); ante un fallo revierte todas esas escrituras.
9. Frontend clears cart via `cartStore.clearCart()`.
10. Success message: "Checkout completed."

**Branching conditions:**

| Condition | Behavior |
|-----------|----------|
| Cart is empty | **Complete checkout** button disabled (`disabled={!items.length}`) |
| API failure | "Could not complete checkout."; conserva carrito y formulario para corregir o reintentar |
| Button shows loading state | Text changes to "..." during submission |
| Producto inexistente en el payload | `400` con errores del serializer; no persiste la venta ni sus líneas |
| Producto eliminado después de validar | `400`; revierte incluso las líneas creadas antes del producto eliminado |
| Reintento después de corregir un producto inválido | Crea una única venta completa; el rechazo anterior no deja registros parciales |

Registro E2E relacionado: `purchase-complete-flow` usa una respuesta `201` real y comprueba los datos devueltos, la confirmación y el carrito vacío.

---

### app-dashboard

| Field | Value |
|-------|-------|
| **Priority** | P2 |
| **Roles** | user |
| **Frontend route** | `/dashboard` |
| **API endpoints** | `GET /api/validate_token/` (via auth guard) |

**Preconditions:** User is authenticated with valid JWT.

**Steps:**

1. User navigates to `/dashboard`.
2. `useRequireAuth()` hook validates the token.
3. Si está autenticado, muestra "Dashboard" y **Sign out**. El enlace **Backoffice** aparece únicamente con `is_staff = true`.
4. Un administrador puede pulsar **Backoffice** para navegar a `/backoffice`.
5. User can click **Sign out** to clear session (see `auth-sign-out`).

**Branching conditions:**

| Condition | Behavior |
|-----------|----------|
| Not authenticated | Redirect to `/sign-in` |
| Token expired | Attempt refresh; if fail, redirect to `/sign-in` |
| Usuario autenticado sin `is_staff` | Puede usar Dashboard; no aparece el enlace Backoffice |

---

## Backoffice Module

### backoffice-users-list

| Field | Value |
|-------|-------|
| **Priority** | P2 |
| **Roles** | staff |
| **Frontend route** | `/backoffice` |
| **API endpoints** | `GET /api/users/` |

**Preconditions:** User is authenticated with `is_staff = true`.

**Steps:**

1. User navigates to `/backoffice`.
2. `useRequireAuth()` hook validates the token.
3. Espera a que termine la restauración de la sesión y confirma `is_staff`; solo entonces pide `GET /api/users/` con Bearer token.
4. Users table renders columns: **Email**, **Role**, **Staff**, **Active**.
5. Each row shows user data.

**Branching conditions:**

| Condition | Behavior |
|-----------|----------|
| Not authenticated | Redirect to `/sign-in` |
| Sesión pendiente | "Checking access..."; no pide ni muestra datos administrativos |
| Usuario autenticado sin `is_staff` | "Access denied", "Admin access required." y enlace **Back to dashboard**; no pide ni muestra las tablas |
| API `403` aunque la sesión local parezca administrativa | Muestra la misma denegación y oculta los datos; el permiso real lo decide la API |
| Fallo de red o API `5xx` | "Could not load backoffice data."; no presenta el fallo como una lista vacía correcta |
| Cambio de sesión o pérdida del permiso | Limpia los datos administrativos anteriores |
| No users | "No data" row shown |

Las lecturas `GET /api/users/` y `GET /api/users/[id]/` exigen `is_staff`: anónimo recibe `403` con "Authentication required."; un usuario autenticado sin permiso recibe `403` con "Admin access required." antes de buscar el objeto. Un administrador conserva `200` o `404` con "Not found.". Un JWT inválido conserva el `401` de autenticación.

---

### backoffice-sales-list

| Field | Value |
|-------|-------|
| **Priority** | P2 |
| **Roles** | staff |
| **Frontend route** | `/backoffice` |
| **API endpoints** | `GET /api/sales/` |

**Preconditions:** User is authenticated with `is_staff = true`.

**Steps:**

1. User navigates to `/backoffice` (loaded together with users).
2. Frontend fetches `GET /api/sales/` with Bearer token.
3. Sales table renders columns: **Id**, **Email**, **City**, **State**, **Postal**.
4. Each row shows sale data.

**Branching conditions:**

| Condition | Behavior |
|-----------|----------|
| Sin permiso o API `403` | Misma denegación de acceso que `backoffice-users-list`; no muestra ventas |
| Fallo temporal | "Could not load backoffice data." |
| No sales | "No data" row shown |

Las lecturas `GET /api/sales/` y `GET /api/sales/[id]/` siguen el mismo contrato administrativo que las lecturas de usuarios. El registro E2E `auth-backoffice-access` cubre acceso permitido, denegación, sesión pendiente y fallo temporal con resultados `success`, `error`, `display` y `failure`.

---

## Cross-Reference

| Artifact | Path | Purpose |
|----------|------|---------|
| Flow Definitions (JSON) | `e2e/flow-definitions.json` | Machine-readable flow registry for the E2E reporter |
| Flow Tag Constants | `e2e/helpers/flow-tags.ts` | Reusable tag arrays for Playwright tests |
| E2E Spec Files | `e2e/<module>/*.spec.ts` | Playwright test implementations per module |
| Flow Coverage Report | `e2e-results/flow-coverage.json` | Auto-generated coverage status per flow |
| Architecture Standard | `docs/DJANGO_REACT_ARCHITECTURE_STANDARD.md` | Sections 3.7.5–3.7.10 define the flow methodology |
| E2E Flow Coverage Standard | `docs/E2E_FLOW_COVERAGE_REPORT_STANDARD.md` | Reporter implementation and JSON schema |

### Maintenance Rules

- **Adding a new flow:** Add entry here with full steps/branches, then add to `e2e/flow-definitions.json`, then create E2E tests.
- **Modifying a flow:** Update steps and branches in this document first, then update tests accordingly.
- **Removing a flow:** Remove from this document, `e2e/flow-definitions.json`, and all `@flow:` tags in specs.
- **Bump `Version` and `Last Updated`** on every change.
