import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

const apiClient = axios.create({ baseURL: API_BASE_URL });

function getAccessToken() {
  return localStorage.getItem("pms_access_token");
}
function getRefreshToken() {
  return localStorage.getItem("pms_refresh_token");
}
export function setTokens(access: string, refresh: string) {
  localStorage.setItem("pms_access_token", access);
  localStorage.setItem("pms_refresh_token", refresh);
}
export function clearTokens() {
  localStorage.removeItem("pms_access_token");
  localStorage.removeItem("pms_refresh_token");
}

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  const language = localStorage.getItem("pms_language") || "en";
  config.headers = config.headers ?? {};
  config.headers["Accept-Language"] = language;
  return config;
});

let isRefreshing = false;
let pendingQueue: Array<{ resolve: () => void; reject: (err: unknown) => void }> = [];

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
    if (error.response?.status === 401 && !originalRequest._retry && getRefreshToken()) {
      if (isRefreshing) {
        // Queue this request until the in-flight refresh completes — and
        // reject it (not just leave it hanging) if that refresh fails.
        // Previously only the success path resolved queued callbacks;
        // a failed refresh left every queued request's promise pending
        // forever, with no error and no way to tell what happened.
        return new Promise((resolve, reject) => {
          pendingQueue.push({ resolve: () => resolve(apiClient(originalRequest)), reject });
        });
      }
      originalRequest._retry = true;
      isRefreshing = true;
      try {
        const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: getRefreshToken(),
        });
        setTokens(data.access_token, data.refresh_token);
        pendingQueue.forEach((p) => p.resolve());
        pendingQueue = [];
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Reject every queued request explicitly, then clear tokens and
        // hand off to React Router instead of a hard window.location
        // redirect. A synchronous full-page navigation aborts whatever
        // request(s) are still in flight on the current page — the
        // abort then surfaces to that page's own error handling as a
        // bare "network error" with no status code, which is exactly
        // the confusing symptom this was producing: not a real
        // connectivity problem, but this redirect cutting the original
        // request off mid-flight.
        pendingQueue.forEach((p) => p.reject(refreshError));
        pendingQueue = [];
        clearTokens();
        if (!window.location.pathname.startsWith("/login")) {
          window.dispatchEvent(new CustomEvent("pms:session-expired"));
        }
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
