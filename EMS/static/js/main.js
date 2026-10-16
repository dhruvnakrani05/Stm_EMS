/* ============================================
   EMS - Main JavaScript
   ============================================ */

document.addEventListener('DOMContentLoaded', function () {

    // ==========================================
    // Sidebar Toggle (Mobile)
    // ==========================================
    const sidebar = document.getElementById('sidebar');
    const menuToggle = document.getElementById('menuToggle');
    const sidebarClose = document.getElementById('sidebarClose');
    const mainContent = document.getElementById('mainContent');

    if (menuToggle) {
        menuToggle.addEventListener('click', function () {
            sidebar.classList.toggle('open');
        });
    }

    if (sidebarClose) {
        sidebarClose.addEventListener('click', function () {
            sidebar.classList.remove('open');
        });
    }

    // Close sidebar when clicking outside on mobile
    if (mainContent) {
        mainContent.addEventListener('click', function () {
            if (sidebar && sidebar.classList.contains('open')) {
                sidebar.classList.remove('open');
            }
        });
    }

    // ==========================================
    // Auto-dismiss alerts after 5 seconds
    // ==========================================
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function (alert, index) {
        setTimeout(function () {
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(function () {
                alert.remove();
            }, 300);
        }, 5000 + (index * 500));
    });

    // ==========================================
    // Animated Number Counters
    // ==========================================
    const counters = document.querySelectorAll('[data-count]');
    counters.forEach(function (counter) {
        const target = parseInt(counter.getAttribute('data-count'));
        const duration = 400;
        const step = Math.max(1, Math.floor(target / (duration / 16)));
        let current = 0;

        function updateCounter() {
            current += step;
            if (current >= target) {
                counter.textContent = target;
                return;
            }
            counter.textContent = current;
            requestAnimationFrame(updateCounter);
        }

        // Start counting when element is visible
        const observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    updateCounter();
                    observer.unobserve(entry.target);
                }
            });
        });
        observer.observe(counter);
    });

    // ==========================================
    // Table Row Click Navigation
    // ==========================================
    const clickableRows = document.querySelectorAll('tr[data-href]');
    clickableRows.forEach(function (row) {
        row.style.cursor = 'pointer';
        row.addEventListener('click', function () {
            window.location.href = this.dataset.href;
        });
    });

    // ==========================================
    // Confirmation Dialogs
    // ==========================================
    const deleteButtons = document.querySelectorAll('[data-confirm]');
    deleteButtons.forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            const message = this.getAttribute('data-confirm') || 'Are you sure?';
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });

    // ==========================================
    // Form Validation Visual Feedback
    // ==========================================
    const formInputs = document.querySelectorAll('.form-input, .form-select');
    formInputs.forEach(function (input) {
        input.addEventListener('blur', function () {
            if (this.value.trim() !== '') {
                this.style.borderColor = 'rgba(16, 185, 129, 0.3)';
            }
        });
        input.addEventListener('focus', function () {
            this.style.borderColor = '';
        });
    });

    // ==========================================
    // Smooth scroll for anchor links
    // ==========================================
    document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'auto' });
            }
        });
    });

    // ==========================================
    // Keyboard shortcuts
    // ==========================================
    document.addEventListener('keydown', function (e) {
        // Ctrl+K - Focus search
        if (e.ctrlKey && e.key === 'k') {
            e.preventDefault();
            const search = document.querySelector('.search-input');
            if (search) search.focus();
        }
    });
});
