function escapeHtml(unsafe) {
  if (unsafe === null || unsafe === undefined) return '';
  return String(unsafe)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
window.escapeHtml = escapeHtml;

/**
 * MedAssist AI — Central API Client & JWT Interceptor
 * Handles authentication, token refresh, error handling, and all endpoints.
 */

const API_BASE = '/api/v1';

class ApiClient {
  constructor() {
    this.token = localStorage.getItem('medassist_access_token');
    this.refreshToken = localStorage.getItem('medassist_refresh_token');
  }

  setTokens(accessToken, refreshToken) {
    this.token = accessToken;
    if (accessToken) {
      localStorage.setItem('medassist_access_token', accessToken);
    } else {
      localStorage.removeItem('medassist_access_token');
    }

    if (refreshToken) {
      this.refreshToken = refreshToken;
      localStorage.setItem('medassist_refresh_token', refreshToken);
    } else if (refreshToken === null) {
      this.refreshToken = null;
      localStorage.removeItem('medassist_refresh_token');
    }
  }

  getCurrentUser() {
    const raw = localStorage.getItem('medassist_user');
    return raw ? JSON.parse(raw) : null;
  }

  setCurrentUser(user) {
    if (user) {
      localStorage.setItem('medassist_user', JSON.stringify(user));
    } else {
      localStorage.removeItem('medassist_user');
    }
  }

  async logout() {
    if (this.refreshToken) {
      try {
        await fetch(`${API_BASE}/auth/logout`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: this.refreshToken }),
        });
      } catch (_) {}
    }
    this.setTokens(null, null);
    this.setCurrentUser(null);
    try {
      localStorage.removeItem('medassist_access_token');
      localStorage.removeItem('medassist_refresh_token');
      localStorage.removeItem('medassist_user');
      sessionStorage.setItem('medassist_logged_out', 'true');
    } catch (_) {}
    window.location.href = '/dashboard/login.html';
  }

  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const headers = options.headers || {};

    if (this.token && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    // Do not set Content-Type if sending FormData
    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    options.headers = headers;

    try {
      let response = await fetch(url, options);

      // Handle 401 Unauthorized -> Attempt token refresh
      if (response.status === 401 && this.refreshToken && !endpoint.includes('/auth/login') && !endpoint.includes('/auth/refresh')) {
        const refreshed = await this.tryRefreshToken();
        if (refreshed) {
          headers['Authorization'] = `Bearer ${this.token}`;
          response = await fetch(url, options);
        } else {
          this.logout();
          throw new Error('Session expired. Please log in again.');
        }
      }

      if (!response.ok) {
        let errorData = {};
        try {
          errorData = await response.json();
        } catch (_) {}
        const detail = errorData.detail || `Request failed with status ${response.status}`;
        throw new Error(detail);
      }

      // Check if response is JSON or binary (e.g. PDF blob)
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/pdf') || contentType.includes('application/octet-stream')) {
        return await response.blob();
      }

      return await response.json();
    } catch (err) {
      console.error(`API Error on [${options.method || 'GET'}] ${endpoint}:`, err);
      throw err;
    }
  }

  async tryRefreshToken() {
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: this.refreshToken }),
      });
      if (res.ok) {
        const data = await res.json();
        this.setTokens(data.access_token, data.refresh_token);
        return true;
      }
    } catch (_) {}
    return false;
  }

  // ── Authentication Endpoints ───────────────────────────────────────────────
  async login(email, password) {
    const data = await this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    this.setTokens(data.access_token, data.refresh_token);
    this.setCurrentUser(data.user);
    try { sessionStorage.removeItem('medassist_logged_out'); } catch (_) {}
    return data;
  }

  async registerDoctor(payload) {
    return await this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getMe() {
    const user = await this.request('/auth/me');
    this.setCurrentUser(user);
    return user;
  }

  async changePassword(currentPassword, newPassword) {
    return await this.request('/auth/change-password', {
      method: 'PUT',
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });
  }

  // ── Analyses Endpoints ─────────────────────────────────────────────────────
  async listAnalyses(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return await this.request(`/analyses${qs ? '?' + qs : ''}`);
  }

  async getAnalysis(id) {
    return await this.request(`/analyses/${id}`);
  }

  async updateFeedback(id, feedback) {
    return await this.request(`/analyses/${id}/feedback`, {
      method: 'PUT',
      body: JSON.stringify(feedback),
    });
  }

  async deleteAnalysis(id) {
    return await this.request(`/analyses/${id}`, { method: 'DELETE' });
  }

  async exportPdf(id) {
    return await this.request(`/analyses/${id}/export-pdf`, { method: 'POST' });
  }

  async predictLesion(formData) {
    return await this.request('/predict', {
      method: 'POST',
      body: formData,
    });
  }

  // ── Patients Endpoints ─────────────────────────────────────────────────────
  async listPatients(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return await this.request(`/patients${qs ? '?' + qs : ''}`);
  }

  async createPatient(payload) {
    return await this.request('/patients', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getPatient(id) {
    return await this.request(`/patients/${id}`);
  }

  async updatePatient(id, payload) {
    return await this.request(`/patients/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }

  async deletePatient(id) {
    return await this.request(`/patients/${id}`, { method: 'DELETE' });
  }

  // ── Referrals Endpoints ────────────────────────────────────────────────────
  async createReferral(payload) {
    return await this.request('/referrals', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async listSentReferrals(status = null) {
    const qs = status ? `?status=${status}` : '';
    return await this.request(`/referrals/sent${qs}`);
  }

  async listReceivedReferrals(status = null) {
    const qs = status ? `?status=${status}` : '';
    return await this.request(`/referrals/received${qs}`);
  }

  async getReferral(id) {
    return await this.request(`/referrals/${id}`);
  }

  async respondReferral(id, payload) {
    return await this.request(`/referrals/${id}/respond`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }

  // ── Profile & Doctor Stats ────────────────────────────────────────────────
  async getMyProfile() {
    return await this.request('/profile');
  }

  async updateMyProfile(payload) {
    return await this.request('/profile', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }

  async getDoctorStats() {
    return await this.request('/profile/stats');
  }

  // ── Admin Endpoints ────────────────────────────────────────────────────────
  async getAdminStats() {
    return await this.request('/admin/stats');
  }

  async getAdminAnalytics() {
    return await this.request('/admin/analytics');
  }

  async listUsers(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return await this.request(`/admin/users${qs ? '?' + qs : ''}`);
  }

  async verifyDoctor(userId) {
    return await this.request(`/admin/users/${userId}/verify`, { method: 'PUT' });
  }

  async updateUserStatus(userId, status) {
    return await this.request(`/admin/users/${userId}/status`, {
      method: 'PUT',
      body: JSON.stringify({ status }),
    });
  }

  async resetUserPassword(userId) {
    return await this.request(`/admin/users/${userId}/reset-pwd`, { method: 'POST' });
  }

  async getAuditLogs(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return await this.request(`/admin/audit-logs${qs ? '?' + qs : ''}`);
  }

  // ── Public Endpoints ───────────────────────────────────────────────────────
  async getPublicDoctors(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return await this.request(`/public/doctors${qs ? '?' + qs : ''}`);
  }

  async getFollowUp(token) {
    return await this.request(`/public/follow-up/${token}`);
  }

  // ── Platform Resources ───────────────────────────────────────────────────
  async getPlatformResources() {
    return await this.request('/public/platform-resources');
  }

  async updatePlatformResources(payload) {
    return await this.request('/admin/platform-resources', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }

  async uploadApk(file) {
    const formData = new FormData();
    formData.append('file', file);
    return await this.request('/admin/platform-resources/upload-apk', {
      method: 'POST',
      body: formData,
    });
  }

  async uploadThesis(file, lang = 'en') {
    const formData = new FormData();
    formData.append('file', file);
    return await this.request(`/admin/platform-resources/upload-thesis?lang=${lang}`, {
      method: 'POST',
      body: formData,
    });
  }

  async uploadQrCode(file) {
    const formData = new FormData();
    formData.append('file', file);
    return await this.request('/admin/platform-resources/upload-qr-code', {
      method: 'POST',
      body: formData,
    });
  }
}

// Global Toast Notification Helper
function showToast(message, type = 'success') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  const icon = type === 'success' ? '✓' : '⚠';
  toast.innerHTML = `<span style="font-weight:700;">${icon}</span> <span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Helper to extract high-res YouTube video thumbnail
function extractYouTubeThumbnail(url) {
  if (!url) return null;
  const match = url.match(/(?:shorts\/|v=|youtu\.be\/|embed\/)([a-zA-Z0-9_-]{11})/);
  if (match && match[1]) {
    return `https://img.youtube.com/vi/${match[1]}/hqdefault.jpg`;
  }
  return null;
}

// Global dynamic platform resources synchronizer
async function syncPlatformResources() {
  try {
    const res = await window.api.getPlatformResources();
    if (!res) return;
    const vidLinks = document.querySelectorAll('#res-video-link, #admin-res-video-link, a[data-resource="video"], a[href*="youtube.com"], #landing-video-play-link, #landing-video-action-link');
    const apkLinks = document.querySelectorAll('#res-apk-link, #admin-res-apk-link, a[download*="MedAssist-AI.apk"]');
    const landLinks = document.querySelectorAll('#res-landing-link, #admin-res-landing-link');
    const thesisEnLinks = document.querySelectorAll('#res-thesis-en-link, a[data-resource="thesis-en"]');
    const thesisFrLinks = document.querySelectorAll('#res-thesis-fr-link, a[data-resource="thesis-fr"]');

    if (res.video_walkthrough_url) {
      vidLinks.forEach(el => el.href = res.video_walkthrough_url);

      // Dynamic Thumbnail Update: YouTube Thumbnail or App Branding fallback
      const ytThumb = extractYouTubeThumbnail(res.video_walkthrough_url);
      const thumbElements = document.querySelectorAll('#demo-video-thumb, .demo-media-thumb, #landing-video-poster');
      thumbElements.forEach(img => {
        if (ytThumb) {
          img.src = ytThumb;
        } else {
          img.src = '/dashboard/assets/images/app-icon.jpg';
        }
      });
    }

    if (res.mobile_apk_url) {
      apkLinks.forEach(el => el.href = res.mobile_apk_url);
    }
    if (res.landing_page_url) {
      landLinks.forEach(el => el.href = res.landing_page_url);
    }
    if (res.thesis_en_url) {
      thesisEnLinks.forEach(el => el.href = res.thesis_en_url);
    }
    if (res.thesis_fr_url) {
      thesisFrLinks.forEach(el => el.href = res.thesis_fr_url);
    }
    if (res.qr_code_url) {
      const qrImgs = document.querySelectorAll('#landing-qr-image, .qr-container img, #admin-qr-preview-img');
      const cacheBust = '?t=' + Date.now();
      qrImgs.forEach(img => {
        img.src = res.qr_code_url + cacheBust;
      });
    }
  } catch (err) {
    console.warn('Could not sync platform resources:', err);
  }
}

// Global API instance & utilities
window.api = new ApiClient();
window.showToast = showToast;
window.extractYouTubeThumbnail = extractYouTubeThumbnail;
window.syncPlatformResources = syncPlatformResources;


