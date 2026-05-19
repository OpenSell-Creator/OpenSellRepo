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

    let sidebarIsOpen   = false;
    let lastScroll      = 0;
    let touchStartY     = 0;
    let touchStartX     = 0;
    let navVisible      = true;   // JS-tracked — never read from CSS
    let intentToHide    = false;  // true only when user deliberately swiped up
    let touchActive     = false;  // true while finger is on screen
    const SWIPE_THRESHOLD = 30;

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
      touchStartY  = e.touches[0].clientY;
      touchStartX  = e.touches[0].clientX;
      touchActive  = true;
      intentToHide = false; // reset intent on every new touch
    }, { passive: true });

    // ── touchmove ────────────────────────────────────────────────────────────
    window.addEventListener('touchmove', (e) => {
      if (!e.touches || e.touches.length === 0) return;

      const deltaY = touchStartY - e.touches[0].clientY;
      const deltaX = Math.abs(touchStartX - e.touches[0].clientX);

      // Mark intent as soon as we see a clear upward swipe gesture
      if (deltaX < Math.abs(deltaY) && deltaY > SWIPE_THRESHOLD) {
        intentToHide = true;
      }

      // Block iOS elastic bounce / pull-to-refresh when nav is hidden
      if (deltaX < Math.abs(deltaY) && deltaY < -10 && !navVisible) {
        try { e.preventDefault(); } catch (_) {}
      }
    }, { passive: false });

    // ── touchend ─────────────────────────────────────────────────────────────
    window.addEventListener('touchend', (e) => {
      touchActive = false;

      // Safe touch reference — iOS drops changedTouches on system interrupts
      const touch =
        (e.changedTouches && e.changedTouches[0]) ||
        (e.touches        && e.touches[0]);
      if (!touch) return;

      const deltaY = touchStartY - touch.clientY;
      const deltaX = Math.abs(touchStartX - touch.clientX);

      // Ignore horizontal swipes (carousels etc.)
      if (deltaX > Math.abs(deltaY)) return;

      if (deltaY > SWIPE_THRESHOLD) {
        // Deliberate upward swipe → hide and lock hidden
        intentToHide = true;
        hideNav();
      } else if (deltaY < -SWIPE_THRESHOLD) {
        // Deliberate downward swipe → show and clear lock
        intentToHide = false;
        showNav();
      }
      // Any delta smaller than threshold (including elastic bounce return)
      // does nothing — navbars stay in whatever state they were
    }, { passive: true });

    // ── scroll ───────────────────────────────────────────────────────────────
    // The key fix for iOS elastic bounce:
    // On a non-scrollable page iOS still fires scroll events during the bounce
    // and then fires them again in reverse as the page snaps back. That reverse
    // scroll (currentScroll < lastScroll) is what was wrongly calling showNav().
    //
    // Guard: only call showNav() from scroll if the user has NOT expressed an
    // intent to hide (i.e. no upward swipe happened) AND the finger is not
    // currently on the screen (i.e. it is a real scroll, not a bounce return).
    window.addEventListener('scroll', () => {
      const currentScroll = window.scrollY;

      if (currentScroll > lastScroll + 4) {
        // Scrolling down — always hide
        hideNav();
      } else if ((currentScroll < lastScroll || currentScroll <= 0) && !intentToHide && !touchActive) {
        // Scrolling up — only show if the user didn't deliberately swipe to hide
        // and the finger is not still on screen (iOS bounce guard)
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

    // ── Close sidebar on link tap (mobile) ────────────────────────────────────
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