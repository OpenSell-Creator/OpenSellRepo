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

    let sidebarIsOpen = false;
    let lastScroll    = 0;
    let navVisible    = true;

    // ── Touch tracking ────────────────────────────────────────────────────
    let touchStartY        = 0;
    let touchStartX        = 0;
    let touchCurrentY      = 0;
    let fingerOnScreen     = false;   // true only while finger is physically down
    let swipeIntent        = null;    // 'up' | 'down' | null — set on touchend
    let swipeIntentTimer   = null;    // clears swipeIntent after momentum settles

    // Momentum detection: track recent scroll velocity
    let lastScrollTime     = 0;
    let lastScrollY        = 0;
    let scrollVelocity     = 0;       // px/ms (positive = scrolling down)

    // How many px of upward scrolling must arrive before re-showing nav
    // after a deliberate hide. Prevents a single bounce from showing it.
    const MOMENTUM_SHOW_THRESHOLD = 40;
    let upwardScrollAccum  = 0;       // accumulated upward px since last hide

    const SWIPE_THRESHOLD  = 40;      // px — min vertical swipe to register intent
    const HIDE_SCROLL_DELTA = 8;      // px — must scroll down this much to hide

    // ── Show / hide ───────────────────────────────────────────────────────
    function showNav() {
      if (navVisible) return;
      navVisible    = true;
      upwardScrollAccum = 0;
      mainNavbar.style.transform = 'translateY(0)';
      mainNavbar.style.opacity   = '1';
      if (bottomNav) {
        bottomNav.style.transform = 'translateY(0)';
        bottomNav.style.opacity   = '1';
      }
    }

    function hideNav() {
      if (sidebarIsOpen || !navVisible) return;
      navVisible        = false;
      upwardScrollAccum = 0;
      mainNavbar.style.transform = 'translateY(-100%)';
      mainNavbar.style.opacity   = '0';
      if (bottomNav) {
        bottomNav.style.transform = 'translateY(100%)';
        bottomNav.style.opacity   = '0';
      }
    }

    // ── Clear swipe intent after momentum has had time to settle ─────────
    function scheduleSwipeIntentReset() {
      clearTimeout(swipeIntentTimer);
      // 600 ms is enough for iOS momentum to settle on most devices
      swipeIntentTimer = setTimeout(() => {
        swipeIntent = null;
      }, 600);
    }

    // ── touchstart ───────────────────────────────────────────────────────
    window.addEventListener('touchstart', (e) => {
      if (!e.touches || e.touches.length === 0) return;
      touchStartY   = e.touches[0].clientY;
      touchStartX   = e.touches[0].clientX;
      touchCurrentY = touchStartY;
      fingerOnScreen = true;

      // Cancel any pending intent reset — finger is back down
      clearTimeout(swipeIntentTimer);
      // Do NOT reset swipeIntent here; let the new gesture override it
      // only when the touchend delta is large enough.
    }, { passive: true });

    // ── touchmove ────────────────────────────────────────────────────────
    window.addEventListener('touchmove', (e) => {
      if (!e.touches || e.touches.length === 0) return;
      touchCurrentY = e.touches[0].clientY;

      const deltaY = touchStartY - touchCurrentY;
      const deltaX = Math.abs(touchStartX - e.touches[0].clientX);

      // Block iOS elastic pull-to-refresh only when nav is hidden
      // and the gesture is clearly vertical (not a side-scroll / swipe)
      if (deltaX < Math.abs(deltaY) && deltaY < -10 && !navVisible) {
        try { e.preventDefault(); } catch (_) {}
      }
    }, { passive: false });

    // ── touchend ─────────────────────────────────────────────────────────
    window.addEventListener('touchend', (e) => {
      fingerOnScreen = false;

      const touch =
        (e.changedTouches && e.changedTouches[0]) ||
        (e.touches        && e.touches[0]);
      if (!touch) return;

      const deltaY = touchStartY - touch.clientY;
      const deltaX = Math.abs(touchStartX - touch.clientX);

      // Ignore horizontal swipes (page-swipe on iPads / carousels)
      if (deltaX > Math.abs(deltaY) * 1.2) {
        scheduleSwipeIntentReset();
        return;
      }

      if (deltaY > SWIPE_THRESHOLD) {
        // Deliberate upward swipe — hide and remember intent
        swipeIntent = 'up';
        hideNav();
        scheduleSwipeIntentReset();
      } else if (deltaY < -SWIPE_THRESHOLD) {
        // Deliberate downward swipe — show and clear intent
        swipeIntent = 'down';
        upwardScrollAccum = MOMENTUM_SHOW_THRESHOLD; // allow show immediately
        showNav();
        scheduleSwipeIntentReset();
      } else {
        // Small / ambiguous delta — schedule reset without changing intent
        scheduleSwipeIntentReset();
      }
    }, { passive: true });

    // ── touchcancel ───────────────────────────────────────────────────────
    window.addEventListener('touchcancel', () => {
      fingerOnScreen = false;
      scheduleSwipeIntentReset();
    }, { passive: true });

    // ── scroll ───────────────────────────────────────────────────────────
    window.addEventListener('scroll', () => {
      const currentScroll = window.scrollY;
      const now           = Date.now();
      const dt            = now - lastScrollTime || 16;

      // Rolling velocity estimate (positive = moving down the page)
      scrollVelocity = (currentScroll - lastScrollY) / dt;
      lastScrollY    = currentScroll;
      lastScrollTime = now;

      const delta = currentScroll - lastScroll;

      if (delta > HIDE_SCROLL_DELTA) {
        // ── Scrolling DOWN ───────────────────────────────────────────────
        // Reset upward accumulator whenever user scrolls down
        upwardScrollAccum = 0;
        hideNav();

      } else if (delta < 0 || currentScroll <= 0) {
        // ── Scrolling UP (or at top of page) ────────────────────────────

        if (currentScroll <= 0) {
          // Always show at top of page regardless of intent
          swipeIntent = null;
          showNav();
        } else if (swipeIntent === 'up' && fingerOnScreen) {
          // Finger still down after deliberate hide swipe — don't show yet
          // (handles the case where iOS starts momentum before touchend)
        } else if (swipeIntent === 'up' && !fingerOnScreen) {
          // Momentum scroll upward after a hide-swipe:
          // accumulate upward distance and only show after threshold met
          upwardScrollAccum += Math.abs(delta);
          if (upwardScrollAccum >= MOMENTUM_SHOW_THRESHOLD) {
            swipeIntent = null;
            showNav();
          }
        } else {
          // Normal upward scroll or deliberate down-swipe intent — show
          showNav();
        }
      }

      lastScroll = currentScroll;
    }, { passive: true });

    // ── Sidebar locks nav visible ─────────────────────────────────────────
    mainSidebar.addEventListener('show.bs.offcanvas', () => {
      sidebarIsOpen = true;
      showNav();
    });
    mainSidebar.addEventListener('hidden.bs.offcanvas', () => {
      sidebarIsOpen = false;
    });

    // ── Close sidebar on link tap ─────────────────────────────────────────
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