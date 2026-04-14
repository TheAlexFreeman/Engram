export const COMPILING = process.env.EMAIL_TEMPLATES_MODE === 'compile';

export const STATIC_BASE = process.env.EMAIL_DEV_STATIC_BASE || 'http://localhost:8020/static';

export const Var = <T>(name: string, exampleValue: T): T => {
  // NOTE: The return type of `Var` is only taking into account when `COMPILING ==
  // false`. We don't care about the return type when `COMPILING == true`, hence the `as
  // T` cast below.
  if (COMPILING) return `{{ ${name} }}` as T;
  return exampleValue;
};

export const Static = (path: string): string => {
  if (COMPILING) return `{% static_for_email '${path}' %}`;

  let pathtoUse = path;
  if (pathtoUse.startsWith('/')) {
    pathtoUse = pathtoUse.slice(1);
  }

  return `${STATIC_BASE}/${pathtoUse}`;
};

export const LANDING_SITE_ROOT_URL = Var(
  'landing_site_root_url',
  'http://localhost:8020?dev_email_ref=landing_site_root_url',
);
export const WEB_APP_ROOT_URL = Var(
  'web_app_root_url',
  'http://localhost:8020?dev_email_ref=web_app_root_url',
);
export const SUPPORT_EMAIL = Var('support_email', 'support@betterbase.com');
