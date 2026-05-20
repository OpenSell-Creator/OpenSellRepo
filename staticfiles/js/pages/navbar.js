document.addEventListener('DOMContentLoaded', function () {

  // ── DOM refs ──────────────────────────────────────────────────────────────
  const mainNavbar    = document.getElementById('mainNavbar');
  const bottomNav     = document.getElementById('bottomNav');
  const mainSidebar   = document.getElementById('mainSidebar');
  const hamburgerBtn  = document.querySelector('.navbar-toggler');
  const hamburgerIcon = hamburgerBtn.querySelector('.hamburger-icon');
  const closeIcon     = hamburgerBtn.querySelector('.close-icon');

  // ── Active nav links ──────────────────────────────────────────────────────
  const path = window.location.pathname;
  document.querySelectorAll('.nav-link').forEach(link => {
    const href = link.getAttribute('href');
    if (href === path || (path.includes(href) && href !== '/')) {
      link.classList.add('active');
    }
  });

  // ── Hamburger ↔ X animation ───────────────────────────────────────────────
  mainSidebar.addEventListener('show.bs.offcanvas', function () {
    hamburgerIcon.style.opacity   = '0';
    hamburgerIcon.style.transform = 'rotate(180deg)';
    closeIcon.style.display       = 'block';
    closeIcon.style.opacity       = '1';
    closeIcon.style.transform     = 'rotate(0)';
    document.body.classList.add('sidebar-open');
  });

  mainSidebar.addEventListener('hide.bs.offcanvas', function () {
    closeIcon.style.opacity   = '0';
    closeIcon.style.transform = 'rotate(-180deg)';
    setTimeout(() => {
      closeIcon.style.display       = 'none';
      hamburgerIcon.style.opacity   = '1';
      hamburgerIcon.style.transform = 'rotate(0)';
    }, 300);
    document.body.classList.remove('sidebar-open');
  });

  // ── Viewport width helper (iOS split-view / orientation safe) ─────────────
  const getViewportWidth = () =>
    window.visualViewport ? window.visualViewport.width : window.innerWidth;

  // ── Mobile nav hide/show block ────────────────────────────────────────────
  if (getViewportWidth() < 992) {

    let sidebarIsOpen     = false;
    let lastScroll        = 0;
    let touchStartY       = 0;
    let touchStartX       = 0;
    let navVisible        = true;
    let intentToHide      = false; // cleared only by swipe-down or scroll accumulator
    let fingerDown        = false; // true only while finger is on screen
    let bounceLock        = false; // blocks scroll handler during iOS elastic bounce
    let bounceLockTimer   = null;
    let upwardScrollAccum = 0;     // accumulated upward px since last downward scroll
    const SWIPE_THRESHOLD = 30;    // px of gesture needed to count as deliberate
    const SHOW_THRESHOLD  = 40;    // px of sustained upward scroll needed to show nav

    // ── Page scrollability helper ─────────────────────────────────────────────
    // Re-checked on each gesture so it works after dynamic content loads.
    function pageIsScrollable() {
      return document.documentElement.scrollHeight > window.innerHeight + 4;
    }

    // ── Show / hide ──────────────────────────────────────────────────────────
    function showNav() {
      navVisible = true;
      mainNavbar.style.transform = 'translateY(0)';
      mainNavbar.style.opacity   = '1';
      if (bottomNav) {
        bottomNav.style.transform = 'translateY(0)';
        bottomNav.style.opacity   = '1';
      }
    }

    function hideNav() {
      if (sidebarIsOpen) return;
      navVisible = false;
      mainNavbar.style.transform = 'translateY(-100%)';
      mainNavbar.style.opacity   = '0';
      if (bottomNav) {
        bottomNav.style.transform = 'translateY(100%)';
        bottomNav.style.opacity   = '0';
      }
    }

    // ── touchstart ───────────────────────────────────────────────────────────
    window.addEventListener('touchstart', (e) => {
      if (!e.touches || e.touches.length === 0) return;
      touchStartY       = e.touches[0].clientY;
      touchStartX       = e.touches[0].clientX;
      fingerDown        = true;
      upwardScrollAccum = 0; // reset accumulator on each new touch

      // Cancel any pending bounce lock when a new deliberate touch begins
      clearTimeout(bounceLockTimer);
      bounceLock = false;
    }, { passive: true });

    // ── touchmove ────────────────────────────────────────────────────────────
    window.addEventListener('touchmove', (e) => {
      if (!e.touches || e.touches.length === 0) return;
      const deltaY = touchStartY - e.touches[0].clientY;
      const deltaX = Math.abs(touchStartX - e.touches[0].clientX);
      // Block iOS elastic pull-to-refresh when nav is hidden
      if (deltaX < Math.abs(deltaY) && deltaY < -10 && !navVisible) {
        try { e.preventDefault(); } catch (_) {}
      }
    }, { passive: false });

    // ── touchend ─────────────────────────────────────────────────────────────
    window.addEventListener('touchend', (e) => {
      fingerDown = false;

      const touch =
        (e.changedTouches && e.changedTouches[0]) ||
        (e.touches        && e.touches[0]);
      if (!touch) return;

      const deltaY = touchStartY - touch.clientY;
      const deltaX = Math.abs(touchStartX - touch.clientX);

      if (deltaX > Math.abs(deltaY)) return; // horizontal swipe — ignore

      const scrollable = pageIsScrollable();

      if (deltaY > SWIPE_THRESHOLD) {
        // Deliberate swipe-up → hide
        intentToHide = true;
        hideNav();

        // On non-scrollable pages the bounce-return scroll events are the only
        // thing that follows — lock them out permanently until a swipe-down.
        // On scrollable pages use a short window; the accumulator takes over after.
        bounceLock = true;
        clearTimeout(bounceLockTimer);
        bounceLockTimer = setTimeout(
          () => { bounceLock = false; },
          scrollable ? 500 : 9999999
        );

      } else if (deltaY < -SWIPE_THRESHOLD) {
        // Deliberate swipe-down → always show and clear all locks
        intentToHide = false;
        bounceLock   = false;
        clearTimeout(bounceLockTimer);
        showNav();
      }
      // Small delta (tap / micro-bounce) → state unchanged
    }, { passive: true });

    // ── scroll ───────────────────────────────────────────────────────────────
    window.addEventListener('scroll', () => {
      const currentScroll = window.scrollY;

      // While bounceLock is active, ignore all scroll events.
      // Non-scrollable pages: indefinite lock (only swipe-down clears it).
      // Scrollable pages: short 500ms window after swipe-up, then accumulator governs.
      if (bounceLock) {
        lastScroll = currentScroll;
        return;
      }

      const delta = currentScroll - lastScroll;

      if (delta > 4) {
        // Real downward scroll → hide
        upwardScrollAccum = 0;
        intentToHide      = true;
        hideNav();

      } else if (delta < -2 && currentScroll > 0) {
        // Upward scroll momentum on a scrollable page.
        // Accumulate until threshold — Android-style direction-reversal reveal.
        upwardScrollAccum += Math.abs(delta);
        if (upwardScrollAccum >= SHOW_THRESHOLD) {
          intentToHide = false;
          showNav();
        }

      } else if (currentScroll <= 0) {
        // Reached the very top — always show
        upwardScrollAccum = 0;
        intentToHide      = false;
        showNav();
      }

      lastScroll = currentScroll;
    }, { passive: true });

    // ── Sidebar locks nav visible ─────────────────────────────────────────────
    mainSidebar.addEventListener('show.bs.offcanvas', () => {
      sidebarIsOpen = true;
      showNav();
    });
    mainSidebar.addEventListener('hidden.bs.offcanvas', () => {
      sidebarIsOpen = false;
    });

    // ── Close sidebar on link tap ─────────────────────────────────────────────
    const sidebarLinks = document.querySelectorAll('#mainSidebar a:not([data-bs-toggle])');
    const sidebar      = document.getElementById('mainSidebar');
    sidebarLinks.forEach(link => {
      link.addEventListener('click', function () {
        const bsOffcanvas = bootstrap.Offcanvas.getInstance(sidebar);
        if (bsOffcanvas) bsOffcanvas.hide();
      });
    });

  } // end mobile block

  // ── Search form validation ────────────────────────────────────────────────
  const searchForms = document.querySelectorAll('.search-form, .sidebar-search-form');
  searchForms.forEach(form => {
    form.addEventListener('submit', function (e) {
      const input = this.querySelector('input[name="query"]');
      if (!input.value.trim()) {
        e.preventDefault();
        input.focus();
      }
    });
  });

  // ── PWA install prompt ────────────────────────────────────────────────────
  let deferredPrompt;
  const pwaInstallSection = document.getElementById('pwaInstallSection');
  const pwaInstallBtn     = document.getElementById('pwaInstallBtn');

  if (
    window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true
  ) {
    if (pwaInstallSection) pwaInstallSection.style.display = 'none';
  }

  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    if (pwaInstallSection) pwaInstallSection.style.display = 'block';
  });

  if (pwaInstallBtn) {
    pwaInstallBtn.addEventListener('click', async () => {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        if (outcome === 'accepted') {
          console.log('User accepted the install prompt');
          pwaInstallSection.style.display = 'none';
        }
        deferredPrompt = null;
      }
    });
  }

  // ── Tooltips ──────────────────────────────────────────────────────────────
  const tooltipTriggerList = [].slice.call(
    document.querySelectorAll('[data-bs-toggle="tooltip"]')
  );
  tooltipTriggerList.map(el => new bootstrap.Tooltip(el));

  // ── Notification badges ───────────────────────────────────────────────────
  function updateNotificationsBadges() {
    document.querySelectorAll('.notification-badge, .quick-action-badge').forEach(badge => {
      const count = parseInt(badge.textContent.trim());
      badge.style.display = (isNaN(count) || count === 0) ? 'none' : 'flex';
    });
  }
  updateNotificationsBadges();

  // ── Collapsible (animation by CSS) ───────────────────────────────────────
  document.querySelectorAll('[data-bs-toggle="collapse"]').forEach(el => {
    el.addEventListener('click', function () {});
  });

  // ── Smooth offcanvas open / close ─────────────────────────────────────────
  const offcanvasConfig = { backdrop: true, keyboard: true, scroll: false };
  const bsOffcanvas     = new bootstrap.Offcanvas(mainSidebar, offcanvasConfig);
  const originalShow    = bsOffcanvas.show;
  const originalHide    = bsOffcanvas.hide;

  bsOffcanvas.show = function () {
    mainSidebar.style.transform = 'translateX(100%)';
    originalShow.call(this);
    setTimeout(() => { mainSidebar.style.transform = 'translateX(0)'; }, 10);
  };

  bsOffcanvas.hide = function () {
    mainSidebar.style.transform = 'translateX(100%)';
    setTimeout(() => { originalHide.call(this); }, 300);
  };

});