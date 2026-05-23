document.addEventListener('DOMContentLoaded', function () {

  // ── DOM refs ──────────────────────────────────────────────────────────────
  const mainNavbar    = document.getElementById('mainNavbar');
  const bottomNav     = document.getElementById('bottomNav');
  const mainSidebar   = document.getElementById('mainSidebar');
  const hamburgerBtn  = document.querySelector('.navbar-toggler');
  const hamburgerIcon = hamburgerBtn.querySelector('.hamburger-icon');
  const closeIcon     = hamburgerBtn.querySelector('.close-icon');
  const backBtn       = document.getElementById('navBackBar');

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
    let touchStartedInBackBar = false;
    let navVisible        = true;
    let intentToHide      = false;
    let bounceLock        = false; 
    let bounceLockTimer   = null;
    let swipeCooldown     = false; 
    let swipeCooldownTimer= null; 
    let upwardScrollAccum = 0;
    const SWIPE_THRESHOLD = 30;
    const SHOW_THRESHOLD  = 40;
    const BOUNCE_WINDOW   = 600; 
    const SWIPE_COOLDOWN  = 400;  

    // ── Page scrollability helper ─────────────────────────────────────────────
    function pageIsScrollable() {
      return document.documentElement.scrollHeight > window.innerHeight + 4;
    }

    // ── Back bar helper ───────────────────────────────────────────────────────
    function updateBackBtn(navIsHidden) {
      if (!backBtn) return;
      const hasHistory = history.length > 1 ||
        sessionStorage.getItem('os_visited_before') === '1';
      if (navIsHidden && hasHistory) {
        backBtn.classList.add('nav-back-bar--visible');
        backBtn.setAttribute('aria-hidden', 'false');
      } else {
        backBtn.classList.remove('nav-back-bar--visible');
        backBtn.setAttribute('aria-hidden', 'true');
      }
    }
    sessionStorage.setItem('os_visited_before', '1');

    // ── Show / hide ───────────────────────────────────────────────────────────
    function showNav() {
      navVisible = true;
      mainNavbar.style.transform    = 'translateY(0)';
      mainNavbar.style.opacity      = '1';
      mainNavbar.style.pointerEvents = 'auto';
      if (bottomNav) {
        bottomNav.style.transform    = 'translateY(0)';
        bottomNav.style.opacity      = '1';
        bottomNav.style.pointerEvents = 'auto';
      }
      updateBackBtn(false);
    }

    function hideNav() {
      if (sidebarIsOpen) return;
      navVisible = false;
      mainNavbar.style.transform    = 'translateY(-100%)';
      mainNavbar.style.opacity      = '0';
      mainNavbar.style.pointerEvents = 'none';
      if (bottomNav) {
        bottomNav.style.transform    = 'translateY(100%)';
        bottomNav.style.opacity      = '0';
        bottomNav.style.pointerEvents = 'none';
      }
      updateBackBtn(true);
    }

    // ── touchstart ───────────────────────────────────────────────────────────
    window.addEventListener('touchstart', (e) => {
      if (!e.touches || e.touches.length === 0) return;

      touchStartY = e.touches[0].clientY;
      touchStartX = e.touches[0].clientX;
      upwardScrollAccum = 0;

      // Detect if this touch originated inside the back bar.
      // If so, we must never preventDefault on its touchmove — doing so kills
      // button taps and link navigations on iOS (the bug reported).
      touchStartedInBackBar = backBtn
        ? backBtn.contains(e.touches[0].target)
        : false;

      // A new deliberate touch always clears the bounce-scroll lock so the
      // scroll handler can function normally again.
      clearTimeout(bounceLockTimer);
      bounceLock = false;

      // Do NOT clear swipeCooldown here — it must survive the touchstart that
      // immediately follows a swipe on non-scrollable pages, which is exactly
      // the iOS synthetic touch that was causing phantom show() calls.
    }, { passive: true });

    // ── touchmove ────────────────────────────────────────────────────────────
    window.addEventListener('touchmove', (e) => {
      if (!e.touches || e.touches.length === 0) return;

      // CRITICAL FIX: never preventDefault on touches that began inside the
      // back bar. Those touches need to reach their target (buttons, inputs,
      // links) uninterrupted. The old code called preventDefault for any
      // upward drag while !navVisible, which swallowed back-bar taps on iOS.
      if (touchStartedInBackBar) return;

      const deltaY = touchStartY - e.touches[0].clientY;
      const deltaX = Math.abs(touchStartX - e.touches[0].clientX);

      // Block iOS pull-to-refresh / elastic overscroll only when:
      // nav is hidden AND drag is clearly vertical-upward AND not in back bar.
      if (deltaX < Math.abs(deltaY) && deltaY < -10 && !navVisible) {
        try { e.preventDefault(); } catch (_) {}
      }
    }, { passive: false });

    // ── touchend ─────────────────────────────────────────────────────────────
    window.addEventListener('touchend', (e) => {
      // Touches that started in the back bar are entirely hands-off —
      // let the browser/iOS handle them as normal taps/navigations.
      if (touchStartedInBackBar) {
        touchStartedInBackBar = false;
        return;
      }

      const touch =
        (e.changedTouches && e.changedTouches[0]) ||
        (e.touches        && e.touches[0]);
      if (!touch) return;

      const deltaY = touchStartY - touch.clientY;
      const deltaX = Math.abs(touchStartX - touch.clientX);

      if (deltaX > Math.abs(deltaY)) return; // horizontal swipe — ignore

      if (deltaY > SWIPE_THRESHOLD) {
        // Deliberate swipe-up → hide nav.
        intentToHide = true;
        hideNav();

        // Engage a finite bounce-scroll lock so the elastic rebound scroll
        // events that iOS fires don't immediately show the nav.
        bounceLock = true;
        clearTimeout(bounceLockTimer);
        bounceLockTimer = setTimeout(() => { bounceLock = false; }, BOUNCE_WINDOW);

        // swipeCooldown gates showNav() in the scroll handler.
        // On scrollable pages it expires after SWIPE_COOLDOWN ms — real upward
        // scroll momentum will take over via the accumulator after that.
        // On non-scrollable pages it never expires via a timer: only a
        // deliberate swipe-down clears it. This is what keeps the nav hidden
        // on bouncy iOS pages where scrollY is permanently 0.
        swipeCooldown = true;
        clearTimeout(swipeCooldownTimer);
        if (pageIsScrollable()) {
          swipeCooldownTimer = setTimeout(() => { swipeCooldown = false; }, SWIPE_COOLDOWN);
        }
        // Non-scrollable: swipeCooldown stays true until swipe-down below.

      } else if (deltaY < -SWIPE_THRESHOLD) {
        // Deliberate swipe-down → show nav, clear all locks.
        intentToHide  = false;
        bounceLock    = false;
        swipeCooldown = false;
        clearTimeout(bounceLockTimer);
        clearTimeout(swipeCooldownTimer);
        showNav();
      }
      // Small delta (tap / micro-bounce) → state unchanged.
    }, { passive: true });

    // ── scroll ───────────────────────────────────────────────────────────────
    window.addEventListener('scroll', () => {
      const currentScroll = window.scrollY;

      // Ignore scroll events during the post-swipe bounce window.
      if (bounceLock) {
        lastScroll = currentScroll;
        return;
      }

      const delta = currentScroll - lastScroll;

      if (delta > 4) {
        // Real downward scroll → hide.
        upwardScrollAccum = 0;
        intentToHide      = true;
        hideNav();

      } else if (delta < -2 && currentScroll > 0) {
        // Upward scroll — accumulate until threshold, then show.
        // Only relevant on scrollable pages; non-scrollable pages never have
        // currentScroll > 0 so this branch never fires for them.
        upwardScrollAccum += Math.abs(delta);
        if (upwardScrollAccum >= SHOW_THRESHOLD && !swipeCooldown) {
          intentToHide = false;
          showNav();
        }

      } else if (currentScroll <= 0 && pageIsScrollable()) {
        // Reached the very top on a SCROLLABLE page → show.
        // Intentionally excluded from non-scrollable pages: scrollY is always
        // 0 there, so this branch would fire on every iOS bounce event and
        // immediately reverse the swipe-up hide. On non-scrollable pages only
        // a deliberate swipe-down (handled in touchend) shows the nav.
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
      if (backBtn) backBtn.classList.remove('nav-back-bar--visible');
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