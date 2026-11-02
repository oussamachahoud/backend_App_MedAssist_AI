/**
 * MedAssist AI — Clinical Chart.js Configurations
 * Custom Neon & Glassmorphism themes matching the landing page.
 * Integrated with DashboardI18n for dynamic multilingual tooltips and labels.
 */

const CHART_COLORS = {
  teal: '#00C9A7',
  cyan: '#48CAE4',
  blue: '#0077B6',
  purple: '#8B5CF6',
  amber: '#F59E0B',
  red: '#EF4444',
  slate: '#64748B',
  gridLine: 'rgba(255, 255, 255, 0.06)',
  textMuted: '#94A3B8',
};

const DIAGNOSIS_COLORS = {
  MEL: '#EF4444', // Melanoma (Red)
  BCC: '#F59E0B', // Basal Cell Carcinoma (Amber)
  SCC: '#FB923C', // Squamous Cell Carcinoma (Orange)
  ACK: '#A855F7', // Actinic Keratosis (Purple)
  NEV: '#10B981', // Nevus (Green)
  SEK: '#38BDF8', // Seborrheic Keratosis (Cyan)
};

const RISK_COLORS = {
  LOW: '#10B981',
  MODERATE: '#F59E0B',
  HIGH: '#EF4444',
  CRITICAL: '#991B1B',
  INCONCLUSIVE: '#64748B',
};

const chartInstances = {};

function destroyChart(canvasId) {
  if (chartInstances[canvasId]) {
    chartInstances[canvasId].destroy();
    delete chartInstances[canvasId];
  }
}

/**
 * Render Diagnosis Distribution Donut Chart
 */
function renderDiagnosisDonut(canvasId, distribution) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  const rawKeys = Object.keys(distribution);
  const labels = rawKeys.map(k => window.dashboardI18n ? window.dashboardI18n.t('diag_' + k.toLowerCase(), k) : k);
  const data = Object.values(distribution);
  const backgroundColors = rawKeys.map(l => DIAGNOSIS_COLORS[l] || CHART_COLORS.teal);

  if (labels.length === 0) {
    labels.push(window.dashboardI18n ? window.dashboardI18n.t('empty_no_data', 'No data') : 'No data');
    data.push(1);
    backgroundColors.push('rgba(255, 255, 255, 0.1)');
  }

  chartInstances[canvasId] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: backgroundColors,
        borderColor: '#040914',
        borderWidth: 3,
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'right',
          labels: {
            color: CHART_COLORS.textMuted,
            font: { family: 'Inter', size: 12, weight: '500' },
            padding: 12,
            boxWidth: 12,
            boxHeight: 12,
          },
        },
        tooltip: {
          backgroundColor: 'rgba(7, 19, 36, 0.95)',
          titleColor: '#fff',
          bodyColor: CHART_COLORS.teal,
          borderColor: 'rgba(0, 201, 167, 0.3)',
          borderWidth: 1,
          padding: 10,
          cornerRadius: 8,
        },
      },
      cutout: '70%',
    },
  });
}

/**
 * Render Risk Distribution Horizontal/Vertical Bar Chart
 */
function renderRiskBarChart(canvasId, distribution) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  const standardRisks = ['LOW', 'MODERATE', 'HIGH', 'CRITICAL', 'INCONCLUSIVE'];
  const labels = standardRisks.map(r => window.dashboardI18n ? window.dashboardI18n.t('risk_' + r.toLowerCase(), r) : r);
  const data = standardRisks.map(r => distribution[r] || 0);
  const bgColors = standardRisks.map(r => RISK_COLORS[r]);
  const dsLabel = window.dashboardI18n ? window.dashboardI18n.t('doc_metric_total', 'Analyses Count') : 'Analyses Count';

  chartInstances[canvasId] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: dsLabel,
        data: data,
        backgroundColor: bgColors,
        borderRadius: 6,
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: CHART_COLORS.textMuted, font: { family: 'Inter', size: 11, weight: '600' } },
        },
        y: {
          grid: { color: CHART_COLORS.gridLine },
          ticks: { color: CHART_COLORS.textMuted, precision: 0 },
          beginAtZero: true,
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(7, 19, 36, 0.95)',
          borderColor: 'rgba(0, 201, 167, 0.3)',
          borderWidth: 1,
          cornerRadius: 8,
        },
      },
    },
  });
}

/**
 * Render Geographic Wilaya Bar Chart for Admin
 */
function renderWilayaBarChart(canvasId, wilayaDist) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  const labels = Object.keys(wilayaDist).map(w =>
    (typeof getWilayaLabel === 'function') ? getWilayaLabel(w) : `Wilaya ${w}`
  );
  const data = Object.values(wilayaDist);
  const dsLabel = window.dashboardI18n ? window.dashboardI18n.t('adm_metric_registered_accounts', 'Registered Clinicians') : 'Registered Clinicians';

  chartInstances[canvasId] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels.length ? labels : ['No Doctors'],
      datasets: [{
        label: dsLabel,
        data: data.length ? data : [0],
        backgroundColor: CHART_COLORS.teal,
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: CHART_COLORS.textMuted, font: { family: 'Inter', size: 11, weight: '600' } },
        },
        y: {
          grid: { color: CHART_COLORS.gridLine },
          ticks: { color: CHART_COLORS.textMuted, precision: 0 },
          beginAtZero: true,
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(7, 19, 36, 0.95)',
          borderColor: 'rgba(0, 201, 167, 0.3)',
          borderWidth: 1,
          cornerRadius: 8,
        },
      },
    },
  });
}

window.charts = {
  renderDiagnosisDonut,
  renderRiskBarChart,
  renderWilayaBarChart,
};
