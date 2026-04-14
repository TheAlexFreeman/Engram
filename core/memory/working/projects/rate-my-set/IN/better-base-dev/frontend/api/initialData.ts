import membershipService from '@/services/memberships';

import { getInitialServerData } from './initialServerData';
import { Membership } from './types/accounts/memberships';
import { AuthenticatedUser, UnauthenticatedUser } from './types/auth/users';
import { InitialData } from './types/initialData';

const _cached: { value: InitialData | null } = { value: null };

function get() {
  if (_cached.value == null) {
    const initialData = getInitialServerData();

    const membershipResult = selectBestInitialCurrentMembership(initialData);
    if (membershipResult.wasFound) {
      initialData.currentMembership = membershipResult.membership;
    }

    _cached.value = initialData;
  }

  return _cached.value;
}

function set(newInitialData: InitialData) {
  _cached.value = newInitialData;

  const membershipResult = selectBestInitialCurrentMembership(newInitialData);
  if (membershipResult.wasFound) {
    _cached.value.currentMembership = membershipResult.membership;
  }
}

function selectBestInitialCurrentMembership(initialData: InitialData):
  | {
      wasFound: true;
      foundSource: 'ss' | 'ls' | 'initial' | 'fallback';
      id: number;
      membership: Membership;
    }
  | {
      wasFound: false;
    } {
  const key = _getUserStorageKey(initialData.user, 'currentMembership');
  const sources = ['ss', 'ls', 'initial', 'fallback'] as const;
  const all = initialData.memberships || [];
  let found: Membership | null = null;
  let source: (typeof sources)[number] = 'ss';

  for (source of sources) {
    let raw: string | null = null;
    if (source === 'ss') {
      raw = sessionStorage.getItem(key);
    } else if (source === 'ls') {
      raw = localStorage.getItem(key);
    } else if (source === 'initial') {
      found = initialData.currentMembership ?? null;
      if (found == null) continue;
    } else if (source === 'fallback') {
      found = all[0] ?? null;
      if (found == null) continue;
    }

    if (found != null) {
      break;
    }

    const parsedId: number | null = parseInt(raw || '', 10);
    if (isNaN(parsedId) || parsedId == null) {
      continue;
    }

    for (const m of all) {
      if (m.id === parsedId) {
        found = m;
      }
    }
  }

  return found == null
    ? { wasFound: false }
    : {
        wasFound: true,
        foundSource: source,
        id: found.id,
        membership: found,
      };
}

function setCurrentMembership(m: Membership | null) {
  if (m?.id == null) return;

  const strId = m.id.toString();

  sessionStorage.setItem('currentMembership', strId);
  localStorage.setItem('currentMembership', strId);

  // Intentionally fire-and-forget.
  void _syncCurrentMembershipToServer(m);
}

function _getUserStorageKey(
  user: AuthenticatedUser | UnauthenticatedUser,
  section: string,
): string {
  const userId: number | null = user?.id ?? null;
  if (userId == null) {
    return `User(id=-1).${section}`;
  }
  return `User(id=${userId}).${section}`;
}

async function _syncCurrentMembershipToServer(m: Membership): Promise<Membership | null> {
  try {
    return await membershipService.select(m.id);
  } catch (e) {
    // oxlint-disable-next-line no-console -- Intentional warning for sync failure.
    console.warn(`Failed to sync current membership (id=${m.id}) to server:`, e);
    return null;
  }
}

export const initialDataRoot = {
  get,
  set,
  selectBestInitialCurrentMembership,
  setCurrentMembership,
};
