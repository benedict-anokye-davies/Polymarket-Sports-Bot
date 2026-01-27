import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import apiClient from '@/api/client';

interface User {
  id: string;
  username: string;
  email: string;
  onboarding_completed: boolean;
  onboarding_step: number;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (email: string, password: string) => Promise<User | undefined>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  checkAuth: () => Promise<void>;
  refreshUser: () => Promise<void>;
  setOnboardingCompleted: () => void;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          const response = await apiClient.login(email, password);
          const token = response.access_token;

          // Store both access token and refresh token
          localStorage.setItem('auth_token', token);
          if (response.refresh_token) {
            localStorage.setItem('refresh_token', response.refresh_token);
          }

          // Get fresh user info from server
          const user = await apiClient.getCurrentUser();

          set({
            token,
            user,
            isAuthenticated: true,
            isLoading: false,
          });

          return user;
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Login failed',
            isLoading: false,
          });
          throw error;
        }
      },

      register: async (username: string, email: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          await apiClient.register(username, email, password);

          // Auto-login after registration
          const response = await apiClient.login(email, password);
          const token = response.access_token;

          // Store both access token and refresh token
          localStorage.setItem('auth_token', token);
          if (response.refresh_token) {
            localStorage.setItem('refresh_token', response.refresh_token);
          }

          const user = await apiClient.getCurrentUser();

          set({
            token,
            user,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Registration failed',
            isLoading: false,
          });
          throw error;
        }
      },

      logout: () => {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('refresh_token');
        set({
          user: null,
          token: null,
          isAuthenticated: false,
        });
      },

      checkAuth: async () => {
        const token = localStorage.getItem('auth_token');
        if (!token) {
          localStorage.removeItem('refresh_token');
          set({ isAuthenticated: false, user: null, token: null });
          return;
        }

        try {
          const user = await apiClient.getCurrentUser();
          set({
            token,
            user,
            isAuthenticated: true,
          });
        } catch {
          localStorage.removeItem('auth_token');
          localStorage.removeItem('refresh_token');
          set({
            user: null,
            token: null,
            isAuthenticated: false,
          });
        }
      },

      refreshUser: async () => {
        try {
          const user = await apiClient.getCurrentUser();
          set({ user });
        } catch (error) {
          console.error('Failed to refresh user:', error);
        }
      },

      setOnboardingCompleted: () => {
        set((state) => ({
          user: state.user ? { ...state.user, onboarding_completed: true } : null
        }));
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ 
        token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
