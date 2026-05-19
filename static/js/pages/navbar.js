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

  // ── Viewport width helper ─────────────────────────────────────────────────
  const getViewportWidth = () =>
    window.visualViewport ? window.visualViewport.width : window.innerWidth;

  // ── Mobile nav hide/show block ────────────────────────────────────────────
  if (getViewportWidth() < 992) {

    let sidebarIsOpen  = false;
    let lastScroll     = 0;
    let touchStartY    = 0;
    let touchStartX    = 0;
    let navVisible     = true;
    let touchActive    = false;

    // How many px the user must scroll upward continuously before
    // the nav reappears during momentum. Low = very responsive,
    // high = requires more deliberate upward scroll.
    const SHOW_SCROLL_THRESHOLD = 8;
    const SWIPE_THRESHOLD       = 30;

    // Tracks how far the user has scrolled upward since direction reversed.
    // Resets to 0 every time scroll goes downward again.
    let upwardScrollAccumulator = 0;

    // ── Show / hide ──────────────────────────────────────────────────────────
    function showNav() {
      navVisible = true;
      upwardScrollAccumulator = 0;
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
      upwardScrollAccumulator = 0; // reset whenever we hide
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
      touchStartY = e.touches[0].clientY;
      touchStartX = e.touches[0].clientX;
      touchActive = true;
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
      touchActive = false;
      const touch =
        (e.changedTouches && e.changedTouches[0]) ||
        (e.touches        && e.touches[0]);
      if (!touch) return;

      const deltaY = touchStartY - touch.clientY;
      const deltaX = Math.abs(touchStartX - touch.clientX);

      if (deltaX > Math.abs(deltaY)) return; // horizontal — ignore

      if (deltaY > SWIPE_THRESHOLD) {
        hideNav();  // deliberate swipe up → hide
      } else if (deltaY < -SWIPE_THRESHOLD) {
        showNav();  // deliberate swipe down → show
      }
      // Small delta (elastic bounce return) → do nothing, state unchanged
    }, { passive: true });

    // ── scroll ───────────────────────────────────────────────────────────────
    window.addEventListener('scroll', () => {
      const currentScroll = window.scrollY;
      const delta         = currentScroll - lastScroll;

      if (delta > 0) {
        // ── Scrolling down ──────────────────────────────────────────────────
        // Always hide. Reset accumulator — direction changed.
        upwardScrollAccumulator = 0;
        if (currentScroll > 4) hideNav();

      } else if (delta < 0) {
        // ── Scrolling up ────────────────────────────────────────────────────
        // Accumulate upward distance scrolled since direction reversed.
        // Only show once the user has scrolled up enough to be intentional,
        // AND the finger is not on screen (avoids iOS elastic bounce return).
        upwardScrollAccumulator += Math.abs(delta);

        if (
          upwardScrollAccumulator >= SHOW_SCROLL_THRESHOLD &&
          !touchActive
        ) {
          showNav();
        }
      }

      // At the very top — always show
      if (currentScroll <= 0) showNav();

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