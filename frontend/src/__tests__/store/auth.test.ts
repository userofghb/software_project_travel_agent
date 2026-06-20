import { useAuthStore } from '../../store/auth';
import type { UserMeResponse } from '../../api/types';

describe('Auth Store', () => {
  beforeEach(() => {
    // Reset store state before each test
    useAuthStore.setState({
      accessToken: null,
      user: null,
    });
  });

  describe('initial state', () => {
    it('should have initial state', () => {
      const state = useAuthStore.getState();
      expect(state.accessToken).toBeNull();
      expect(state.user).toBeNull();
    });
  });

  describe('setSession', () => {
    it('should set access token and user on setSession', () => {
      const mockUser = { id: 1, username: 'testuser' } as UserMeResponse;
      const mockToken = 'test-token-123';
      
      useAuthStore.getState().setSession(mockToken, mockUser);
      
      const state = useAuthStore.getState();
      expect(state.accessToken).toBe(mockToken);
      expect(state.user).toEqual(mockUser);
    });
  });

  describe('setUser', () => {
    it('should update user on setUser', () => {
      const mockUser = { id: 1, username: 'testuser' } as UserMeResponse;
      
      useAuthStore.getState().setUser(mockUser);
      
      const state = useAuthStore.getState();
      expect(state.user).toEqual(mockUser);
    });

    it('should set user to null', () => {
      // First set a user
      const mockUser = { id: 1, username: 'testuser' } as UserMeResponse;
      useAuthStore.getState().setUser(mockUser);
      
      // Then clear user
      useAuthStore.getState().setUser(null);
      
      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
    });
  });

  describe('clearSession', () => {
    it('should clear access token and user on clearSession', () => {
      // First set session
      const mockUser = { id: 1, username: 'testuser' } as UserMeResponse;
      const mockToken = 'test-token-123';
      useAuthStore.getState().setSession(mockToken, mockUser);
      
      // Then clear
      useAuthStore.getState().clearSession();
      
      const state = useAuthStore.getState();
      expect(state.accessToken).toBeNull();
      expect(state.user).toBeNull();
    });
  });
});