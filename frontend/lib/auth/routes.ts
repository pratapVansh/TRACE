export const AUTH_ROUTES = {
  login: "/login",
  register: "/register",
  dashboard: "/dashboard",
} as const;

export const PUBLIC_AUTH_PATHS = [AUTH_ROUTES.login, AUTH_ROUTES.register] as const;
