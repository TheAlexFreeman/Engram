import { Navigate, createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/_auth/settings/')({
  component: SettingsIndex,
});

function SettingsIndex() {
  return <Navigate to="/settings/profile" />;
}
