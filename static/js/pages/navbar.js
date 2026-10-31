document.addEventListener('DOMContentLoaded', function () {

  // ── DOM refs ──────────────────────────────────────────────────────────────
  const mainNavbar   = document.getElementById('mainNavbar');
  const bottomNav    = document.getElementById('bottomNav');
  const mainSidebar  = document.getElementById('mainSidebar');
  const menuBtn      = document.querySelector('[data-bs-target="#mainSidebar"]');
  const backBtn      = document.getElementById('navBackBar');
  const backArrow    = document.getElementById('navBackBtn');

  // ── Theme toggles (top bar, phone controls) ───────────────────────────────
  document.querySelectorAll('[data-theme-toggle]').forEach(btn => {
    btn.addEventListener('click', () => {
      if (window.themeManager) window.themeManager.toggleTheme();
    });
  });

  // ── Back button ───────────────────────────────────────────────────────────
  if (backArrow) backArrow.addEventListener('click', () => history.back());

  // ── Active item: sub-pages too (template covers exact matches) ────────────
  const path = window.location.pathname;
  document.querySelectorAll('.nb-item[href]').forEach(link => {
    const href = link.getAttribute('href');
    if (!href || href === '/') return;
    if (path === href || path.startsWith(href)) {
      link.classList.add('active');
      link.setAttribute('aria-current', 'page');
    }
  });

  // ── Menu button state (icon swap is CSS, driven by aria-expanded) ─────────
  if (mainSidebar && menuBtn) {
    mainSidebar.addEventListener('show.bs.offcanvas', () => {
      menuBtn.setAttribute('aria-expanded', 'true');
      document.body.classList.add('sidebar-open');
    });
    mainSidebar.addEventListener('hide.bs.offcanvas', () => {
      menuBtn.setAttribute('aria-expanded', 'false');
      document.body.classList.remove('sidebar-open');
    });
  }

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

  // ── Search form validation (top bar, back bar) ────────────────────────────
  document.querySelectorAll('.search-form').forEach(form => {
    form.addEventListener('submit', function (e) {
      const input = this.querySelector('input[name="query"]');
      if (input && !input.value.trim()) {
        e.preventDefault();
        input.focus();
      }
    });
  });

  // ── PWA install prompt ────────────────────────────────────────────────────
  let deferredPrompt;
  const pwaInstallSection = document.getElementById('pwaInstallSection');
  const pwaInstallBtn     = document.getElementById('pwaInstallBtn');

  const isStandalone =
    window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true;

  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    if (pwaInstallSection && !isStandalone) pwaInstallSection.hidden = false;
  });

  if (pwaInstallBtn) {
    pwaInstallBtn.addEventListener('click', async () => {
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      if (outcome === 'accepted' && pwaInstallSection) pwaInstallSection.hidden = true;
      deferredPrompt = null;
    });
  }

  // ── Tooltips ──────────────────────────────────────────────────────────────
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => new bootstrap.Tooltip(el));

  // ── Count badges: hide zero / empty ───────────────────────────────────────
  document.querySelectorAll('.nav-badge').forEach(badge => {
    const text = badge.textContent.trim();
    const count = parseInt(text, 10);
    badge.hidden = (text === '' || (!isNaN(count) && count === 0));
  });

});