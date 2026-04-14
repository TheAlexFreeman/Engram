import { Navigate, createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/_auth/accounts/$accountId/')({
  component: AccountIndex,
});

function AccountIndex() {
  return <Navigate from={Route.fullPath} to="settings" />;
}
