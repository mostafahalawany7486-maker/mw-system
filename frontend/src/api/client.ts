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
  return config;
});

let isRefreshing = false;
let pendingQueue: Array<() => void> = [];

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
    if (error.response?.status === 401 && !originalRequest._retry && getRefreshToken()) {
      if (isRefreshing) {
        // Queue this request until the in-flight refresh completes.
        return new Promise((resolve) => {
          pendingQueue.push(() => resolve(apiClient(originalRequest)));
        });
      }
      originalRequest._retry = true;
      isRefreshing = true;
      try {
        const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: getRefreshToken(),
        });
        setTokens(data.access_token, data.refresh_token);
        pendingQueue.forEach((cb) => cb());
        pendingQueue = [];
        return apiClient(originalRequest);
      } catch (refreshError) {
        clearTokens();
        window.location.href = "/login";
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
