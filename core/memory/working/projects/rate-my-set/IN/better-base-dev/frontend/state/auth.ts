import { atom } from 'jotai';

import type { Membership } from '@/api/types/accounts/memberships';
import type { AuthenticatedUser, UnauthenticatedUser } from '@/api/types/auth/users';
import type { InitialData } from '@/api/types/initialData';
import type { AccountCreateResult } from '@/services/accounts';

import { initialDataRoot } from '@/api/initialData';
import { deepCopy } from '@/utils/deepCopies';

const _initial: InitialData = initialDataRoot.get();

const _initialDataAtom = atom<InitialData>(_initial);

export interface SetInitialDataAtomSpecialIndicators {
  justLoggedIn?: boolean;
  justLoggedOut?: boolean;
  justChangedPassword?: boolean;
  justCreatedAccount?: AccountCreateResult;
}

export const initialDataAtom = atom<
  InitialData,
  [InitialData, SetInitialDataAtomSpecialIndicators],
  void
>(
  (get) => get(_initialDataAtom),
  (_get, set, newInitialData, indicators) => {
    // Deepcopy because `jotai` compares by object identity, at least to my
    // understanding as of the time of writing.
    const newInitialDataCopy = deepCopy(newInitialData);
    initialDataRoot.set(newInitialDataCopy);

    const latestInitial = initialDataRoot.get();

    if (indicators.justCreatedAccount != null) {
      latestInitial.memberships = [
        indicators.justCreatedAccount.membershipCreated,
        ...latestInitial.memberships,
      ];
    }

    set(_initialDataAtom, latestInitial);

    if (indicators?.justLoggedIn || indicators?.justLoggedOut || indicators?.justChangedPassword) {
      set(currentMembershipAtom, latestInitial.currentMembership);
      set(immediatelyRedirectToAtom, latestInitial.extra.signaling?.immediatelyRedirectTo || null);
    }

    if (indicators.justCreatedAccount != null) {
      set(currentMembershipAtom, indicators.justCreatedAccount.membershipCreated);
    }
  },
);

export const immediatelyRedirectToAtom = atom<string | null>(
  _initial?.extra.signaling?.immediatelyRedirectTo || null,
);

export const userAtom = atom<AuthenticatedUser | UnauthenticatedUser, [AuthenticatedUser], void>(
  (get) => get(initialDataAtom).user,
  (get, set, updatedUser) => {
    const latestInitial = get(initialDataAtom);
    // Deepcopy because `jotai` compares by object identity, at least to my
    // understanding as of the time of writing.
    const newInitialDataCopy = deepCopy(latestInitial);
    newInitialDataCopy.user = updatedUser;
    initialDataRoot.set(newInitialDataCopy);
    set(_initialDataAtom, initialDataRoot.get());
  },
);

// Can use this atom for Typescript if you know for sure that the user is authenticated
// and don't want to have to cast `useAtom(userAtom)[0]` to `AuthenticatedUser`, etc.
export const authUserAtom = atom((get) => get(userAtom) as AuthenticatedUser);

export const membershipsAtom = atom<Membership[], ['add' | 'remove', Membership], void>(
  (get) => get(initialDataAtom).memberships,
  (get, set, action, membership) => {
    // Deepcopy because `jotai` compares by object identity, at least to my
    // understanding as of the time of writing.
    const newInitialDataCopy = deepCopy(get(initialDataAtom));

    const newMemberships = [];
    let didRemoveOne: boolean = false;
    for (const m of newInitialDataCopy.memberships) {
      if (m.id === membership.id) {
        if (action === 'remove') {
          didRemoveOne = true;
        }
        continue;
      }
      newMemberships.push(m);
    }
    if (action === 'add') {
      newMemberships.unshift(membership);
    }

    if (action === 'remove' && !didRemoveOne) return;

    newInitialDataCopy.memberships = newMemberships;
    initialDataRoot.set(newInitialDataCopy);
    const latestInitial = initialDataRoot.get();
    set(_initialDataAtom, latestInitial);

    const latestSelected = latestInitial.currentMembership;
    if (action === 'add') {
      set(currentMembershipAtom, membership);
    } else if (action === 'remove') {
      set(currentMembershipAtom, latestSelected);
    } else {
      // Exhaustive check - `action` is `never` here if all cases are handled.
      throw new Error(`Unexpected action: ${action as string}`);
    }
  },
);

const _currentMembershipAtom = atom<Membership | null>(_initial.currentMembership);

export const currentMembershipAtom = atom<Membership | null, [Membership | null], void>(
  (get) => get(_currentMembershipAtom),
  (_get, set, membership) => {
    set(_currentMembershipAtom, membership);
    initialDataRoot.setCurrentMembership(membership);
  },
);
