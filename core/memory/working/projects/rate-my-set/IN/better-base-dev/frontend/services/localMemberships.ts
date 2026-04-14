import { Membership } from '@/api/types/accounts/memberships';
import { membershipsAtom } from '@/state/auth';
import store from '@/state/store';

import { currentMembershipAtom } from './../state/auth';

export class LocalMembershipsService {
  getByAccountId(accountId: number): Membership | null {
    const all = store.get(membershipsAtom);

    for (const m of all) {
      if (m.account?.id === accountId) {
        return m;
      }
    }
    return null;
  }

  getCurrent(): Membership | null {
    const m = store.get(currentMembershipAtom);
    return m;
  }
}

const localMembershipsService = new LocalMembershipsService();

export default localMembershipsService;
