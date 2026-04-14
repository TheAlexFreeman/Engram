import { Navigate, createFileRoute } from '@tanstack/react-router';

import { verifiedGuard } from '@/permissions/guards';

export const Route = createFileRoute('/')({
  beforeLoad: verifiedGuard,
  component: Index,
});

function Index() {
  return <Navigate from={Route.fullPath} to="/settings" />;
}
