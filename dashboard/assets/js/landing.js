/* ===================================================
   MedAssist AI — Landing Page Scripts
   Features:
   - Neural network particle canvas with visibility pause
   - Dynamic bilingual toggle (AR / EN) with localStorage persistence
   - Media showcase tab switcher (Walkthrough vs 3D Motion)
   - Interactive screenshot showcase with dots & hover-pause
   - Navbar scroll effects & ScrollSpy active links
   - Mobile navigation menu
   - Smooth scrolling
   =================================================== */

document.addEventListener('DOMContentLoaded', () => {
  initNeuralCanvas();
  initNavbar();
  initMobileMenu();
  initLanguageToggle();
  initMediaTabs();
  initScreenshots();
  initScrollSpy();
  initScrollReveal();
  initSmoothScroll();
});


/* ============================================
   1. NEURAL NETWORK CANVAS BACKGROUND
   ============================================ */
function initNeuralCanvas() {
  const canvas = document.getElementById('neural-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  let width, height;
  let nodes = [];
  let animFrame;
  let isRunning = true;
  
  const NODE_COUNT = 55;
  const CONNECTION_DISTANCE = 170;
  const MOUSE_RADIUS = 180;
  let mouse = { x: -1000, y: -1000 };

  function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  }

  function createNodes() {
    nodes = [];
    for (let i = 0; i < NODE_COUNT; i++) {
      nodes.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.45,
        vy: (Math.random() - 0.5) * 0.45,
        radius: Math.random() * 2 + 1,
        pulse: Math.random() * Math.PI * 2,
      });
    }
  }

  function draw() {
    if (!isRunning) return;

    ctx.clearRect(0, 0, width, height);

    // Draw neural synapses
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < CONNECTION_DISTANCE) {
          const alpha = (1 - dist / CONNECTION_DISTANCE) * 0.16;
          ctx.beginPath();
          ctx.moveTo(nodes[i].x, nodes[i].y);
          ctx.lineTo(nodes[j].x, nodes[j].y);
          ctx.strokeStyle = `rgba(0, 201, 167, ${alpha})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }

    // Draw & update nodes
    for (const node of nodes) {
      node.pulse += 0.02;
      const pulseFactor = Math.sin(node.pulse) * 0.4 + 1;

      // Mouse interactivity
      const mdx = node.x - mouse.x;
      const mdy = node.y - mouse.y;
      const mDist = Math.sqrt(mdx * mdx + mdy * mdy);
      if (mDist < MOUSE_RADIUS) {
        const force = (MOUSE_RADIUS - mDist) / MOUSE_RADIUS;
        node.vx += (mdx / mDist) * force * 0.02;
        node.vy += (mdy / mDist) * force * 0.02;
      }

      // Physics update
      node.x += node.vx;
      node.y += node.vy;

      // Damping
      node.vx *= 0.99;
      node.vy *= 0.99;

      // Wrap boundaries
      if (node.x < 0) node.x = width;
      if (node.x > width) node.x = 0;
      if (node.y < 0) node.y = height;
      if (node.y > height) node.y = 0;

      // Center point
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.radius * pulseFactor, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(0, 201, 167, 0.7)';
      ctx.fill();

      // Outer glow
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.radius * pulseFactor * 2.8, 0, Math.PI * 2);
      const gradient = ctx.createRadialGradient(
        node.x, node.y, 0,
        node.x, node.y, node.radius * pulseFactor * 2.8
      );
      gradient.addColorStop(0, 'rgba(0, 201, 167, 0.18)');
      gradient.addColorStop(1, 'rgba(0, 201, 167, 0)');
      ctx.fillStyle = gradient;
      ctx.fill();
    }

    animFrame = requestAnimationFrame(draw);
  }

  // Mouse move tracking
  window.addEventListener('mousemove', (e) => {
    mouse.x = e.clientX;
    mouse.y = e.clientY;
  });

  // Touch tracking for mobile
  window.addEventListener('touchmove', (e) => {
    if (e.touches.length > 0) {
      mouse.x = e.touches[0].clientX;
      mouse.y = e.touches[0].clientY;
    }
  }, { passive: true });

  // Window resize
  window.addEventListener('resize', () => {
    resize();
    createNodes();
  });

  // Pause when tab not visible to save battery
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      isRunning = false;
      cancelAnimationFrame(animFrame);
    } else {
      isRunning = true;
      draw();
    }
  });

  resize();
  createNodes();
  draw();
}


/* ============================================
   2. NAVBAR
   ============================================ */
function initNavbar() {
  const navbar = document.getElementById('navbar');
  if (!navbar) return;

  function updateNavbar() {
    if (window.scrollY > 40) {
      navbar.classList.add('scrolled');
    } else {
      navbar.classList.remove('scrolled');
    }
  }

  window.addEventListener('scroll', updateNavbar, { passive: true });
  updateNavbar();
}


/* ============================================
   3. MOBILE NAVIGATION MENU
   ============================================ */
function initMobileMenu() {
  const toggle = document.getElementById('mobileToggle');
  const navLinks = document.getElementById('navLinks');

  if (!toggle || !navLinks) return;

  toggle.addEventListener('click', () => {
    const isOpen = navLinks.classList.toggle('open');
    toggle.classList.toggle('active', isOpen);
    document.body.style.overflow = isOpen ? 'hidden' : '';
  });

  // Close when tapping any link
  navLinks.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      navLinks.classList.remove('open');
      toggle.classList.remove('active');
      document.body.style.overflow = '';
    });
  });
}


/* ============================================
   4. BILINGUAL TOGGLE (ARABIC / ENGLISH)
   ============================================ */
function initLanguageToggle() {
  const btnEn = document.getElementById('btnEn');
  const btnAr = document.getElementById('btnAr');

  if (!btnEn || !btnAr) return;

  const titles = {
    en: 'MedAssist AI — Smarter Healthcare Solutions',
    ar: 'MedAssist AI — حلول ذكية لتشخيص الأمراض الجلدية'
  };

  function setLanguage(lang) {
    const htmlEl = document.documentElement;
    const bodyEl = document.body;

    if (lang === 'ar') {
      htmlEl.setAttribute('dir', 'rtl');
      htmlEl.setAttribute('lang', 'ar');
      bodyEl.setAttribute('dir', 'rtl');
      btnAr.classList.add('active');
      btnEn.classList.remove('active');
      document.title = titles.ar;
    } else {
      htmlEl.setAttribute('dir', 'ltr');
      htmlEl.setAttribute('lang', 'en');
      bodyEl.setAttribute('dir', 'ltr');
      btnEn.classList.add('active');
      btnAr.classList.remove('active');
      document.title = titles.en;
    }

    // Update all elements with data-en & data-ar
    document.querySelectorAll('[data-en][data-ar]').forEach(el => {
      const translated = el.getAttribute(`data-${lang}`);
      if (translated) {
        el.textContent = translated;
      }
    });

    try {
      localStorage.setItem('medassist_lang', lang);
    } catch (e) {
      // localStorage may fail in restricted sandboxes
    }
  }

  btnEn.addEventListener('click', () => setLanguage('en'));
  btnAr.addEventListener('click', () => setLanguage('ar'));

  // Load saved preference or default
  let savedLang = 'en';
  try {
    savedLang = localStorage.getItem('medassist_lang') || 'en';
  } catch (e) {}

  if (savedLang === 'ar') {
    setLanguage('ar');
  }
}


/* ============================================
   5. MEDIA TABS (Walkthrough vs 3D Motion)
   ============================================ */
function initMediaTabs() {
  const btnWalkthrough = document.getElementById('tabAppWalkthrough');
  const btnBrand = document.getElementById('tabBrandMotion');
  const paneWalkthrough = document.getElementById('paneWalkthrough');
  const paneBrand = document.getElementById('paneBrand');
  const brandVideo = document.getElementById('brandVideo');

  if (!btnWalkthrough || !btnBrand || !paneWalkthrough || !paneBrand) return;

  btnWalkthrough.addEventListener('click', () => {
    btnWalkthrough.classList.add('active');
    btnBrand.classList.remove('active');
    paneWalkthrough.classList.add('active');
    paneBrand.classList.remove('active');
    if (brandVideo && !brandVideo.paused) {
      brandVideo.pause();
    }
  });

  btnBrand.addEventListener('click', () => {
    btnBrand.classList.add('active');
    btnWalkthrough.classList.remove('active');
    paneBrand.classList.add('active');
    paneWalkthrough.classList.remove('active');
  });
}


/* ============================================
   6. SCREENSHOT SHOWCASE & DOTS
   ============================================ */
function initScreenshots() {
  const items = document.querySelectorAll('.screenshot-item');
  const dots = document.querySelectorAll('.carousel-dot');
  if (!items.length) return;

  let currentIndex = 1;
  let autoTimer = null;

  function setActive(index) {
    currentIndex = index;
    items.forEach((item, i) => {
      item.classList.toggle('active', i === index);
    });
    dots.forEach((dot, i) => {
      dot.classList.toggle('active', i === index);
    });
  }

  // Item click handler
  items.forEach((item, index) => {
    item.addEventListener('click', () => {
      setActive(index);
    });
  });

  // Dots click handler
  dots.forEach((dot, index) => {
    dot.addEventListener('click', () => {
      setActive(index);
    });
  });

  // Auto rotation
  function startAutoPlay() {
    stopAutoPlay();
    autoTimer = setInterval(() => {
      const nextIndex = (currentIndex + 1) % items.length;
      setActive(nextIndex);
    }, 4500);
  }

  function stopAutoPlay() {
    if (autoTimer) {
      clearInterval(autoTimer);
      autoTimer = null;
    }
  }

  const container = document.querySelector('.screenshots-showcase');
  if (container) {
    container.addEventListener('mouseenter', stopAutoPlay);
    container.addEventListener('mouseleave', startAutoPlay);
  }

  startAutoPlay();
}


/* ============================================
   7. SCROLLSPY (Active Navigation Link)
   ============================================ */
function initScrollSpy() {
  const sections = document.querySelectorAll('section[id]');
  const navLinks = document.querySelectorAll('.nav-links a[href^="#"]');

  if (!sections.length || !navLinks.length) return;

  function onScroll() {
    const scrollPos = window.scrollY + 120;

    sections.forEach(sec => {
      const top = sec.offsetTop;
      const height = sec.offsetHeight;
      const id = sec.getAttribute('id');

      if (scrollPos >= top && scrollPos < top + height) {
        navLinks.forEach(link => {
          if (link.getAttribute('href') === `#${id}`) {
            link.classList.add('active');
          } else {
            link.classList.remove('active');
          }
        });
      }
    });
  }

  window.addEventListener('scroll', onScroll, { passive: true });
}


/* ============================================
   8. SCROLL REVEAL (Intersection Observer)
   ============================================ */
function initScrollReveal() {
  const reveals = document.querySelectorAll('.reveal');
  if (!reveals.length) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('revealed');
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.12,
    rootMargin: '0px 0px -40px 0px'
  });

  reveals.forEach(el => observer.observe(el));
}


/* ============================================
   9. SMOOTH SCROLL FOR ANCHOR LINKS
   ============================================ */
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      const targetId = this.getAttribute('href');
      if (targetId === '#') return;

      const target = document.querySelector(targetId);
      if (target) {
        e.preventDefault();
        const headerOffset = 70;
        const elementPosition = target.getBoundingClientRect().top;
        const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

        window.scrollTo({
          top: offsetPosition,
          behavior: 'smooth'
        });
      }
    });
  });
}
