/**
 * main.js — Loan EMI Tracker
 * ============================
 * Client-side enhancements:
 * - Toast auto-dismiss
 * - Confirm dialogs for destructive actions
 * - Mobile sidebar toggle
 */

'use strict';

// ── Toast Auto-dismiss ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {

  // Auto-dismiss toasts after 5 seconds
  const toasts = document.querySelectorAll('.toast');
  toasts.forEach(function (toast, i) {
    setTimeout(function () {
      toast.style.transition = 'opacity 0.4s, transform 0.4s';
      toast.style.opacity    = '0';
      toast.style.transform  = 'translateX(100px)';
      setTimeout(function () { toast.remove(); }, 400);
    }, 5000 + i * 300);  // Stagger multiple toasts
  });

  // ── Mobile sidebar toggle ────────────────────────────────────────────────
  // Adds a hamburger button on small screens
  const sidebar     = document.getElementById('sidebar');
  const mainContent = document.getElementById('mainContent');

  if (window.innerWidth <= 768) {
    const toggleBtn = document.createElement('button');
    toggleBtn.innerHTML  = '☰';
    toggleBtn.id         = 'sidebar-toggle';
    toggleBtn.style.cssText = `
      position: fixed; top: 16px; left: 16px; z-index: 200;
      background: var(--bg-700); border: 1px solid var(--bg-500);
      color: var(--text-primary); border-radius: var(--radius-sm);
      padding: 8px 12px; cursor: pointer; font-size: 1.1rem;
    `;
    document.body.appendChild(toggleBtn);

    toggleBtn.addEventListener('click', function () {
      sidebar.classList.toggle('mobile-open');
    });

    // Close sidebar when clicking outside
    mainContent?.addEventListener('click', function () {
      sidebar.classList.remove('mobile-open');
    });
  }

  // ── Table row click → navigate to detail ────────────────────────────────
  // Makes entire table rows clickable (UX improvement)
  document.querySelectorAll('tr[data-href]').forEach(function (row) {
    row.style.cursor = 'pointer';
    row.addEventListener('click', function (e) {
      // Don't navigate if clicking a button/link inside the row
      if (!e.target.closest('a, button, form')) {
        window.location.href = row.dataset.href;
      }
    });
  });

  // ── Active nav highlight from URL ────────────────────────────────────────
  // Django already sets 'active' via template logic, but this handles edge cases
  const currentPath = window.location.pathname;
  document.querySelectorAll('.nav-item').forEach(function (item) {
    if (item.getAttribute('href') && currentPath.startsWith(item.getAttribute('href')) &&
        item.getAttribute('href') !== '/dashboard/') {
      item.classList.add('active');
    }
  });
});
