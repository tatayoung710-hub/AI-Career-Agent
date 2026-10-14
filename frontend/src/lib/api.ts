const baseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
const tokenKey = 'career_agent_token';

export const authSession = {
  getToken: () => sessionStorage.getItem(tokenKey),
  setToken: (token: string) => sessionStorage.setItem(tokenKey, token),
  clear: () => sessionStorage.removeItem(tokenKey),
};

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;
  constructor(status: number, detail: unknown) {
    const message = typeof detail === 'string' ? detail : Array.isArray(detail)
      ? detail.map((item: { msg?: string }) => item.msg ?? JSON.stringify(item)).join('；')
      : detail && typeof detail === 'object' && 'message' in detail
        ? String((detail as { message: unknown }).message) : JSON.stringify(detail) || `请求失败 (${status})`;
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const token = authSession.getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(`${baseUrl}${path}`, { ...options, headers });
  if (!response.ok) {
    let payload: { detail?: unknown } = {};
    try { payload = await response.json(); } catch { payload = { detail: response.statusText }; }
    if (response.status === 401 && !path.startsWith('/auth/')) {
      authSession.clear();
      window.dispatchEvent(new Event('career:unauthorized'));
    }
    throw new ApiError(response.status, payload.detail ?? payload);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
  post: <T>(path: string, body: unknown = {}) => request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, file: File, fields: Record<string, string> = {}) => {
    const form = new FormData(); form.append('file', file);
    Object.entries(fields).forEach(([key, value]) => form.append(key, value));
    return request<T>(path, { method: 'POST', body: form });
  },
  download: async (path: string, filename: string) => {
    const response = await fetch(`${baseUrl}${path}`, { headers: { Authorization: `Bearer ${authSession.getToken() || ''}` } });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({ detail: response.statusText }));
      throw new ApiError(response.status, payload.detail);
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
};

export function errorMessage(error: unknown): string {
  if (error instanceof TypeError) return '无法连接后端服务，请确认 API 已启动后重试。';
  return error instanceof Error ? error.message : '请求失败，请重试。';
}
