import { type User } from '../accounts/users';

export interface AuthenticatedUser extends User {
  isAuthenticated: true;
}

export interface UnauthenticatedUser {
  id: null;
  isAuthenticated: false;
}
