/* MASE NUTRITION — menu, transições e pequenos detalhes */
document.addEventListener("DOMContentLoaded", () => {
  const reduzir = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // menu mobile
  const btn = document.querySelector(".nav-toggle");
  const nav = document.querySelector(".main-nav");
  if (btn && nav) btn.addEventListener("click", () => nav.classList.toggle("open"));

  // menu "Minha Conta"
  const contaMenu = document.querySelector(".account-menu");
  const contaBtn = document.querySelector(".account-toggle");
  if (contaMenu && contaBtn) {
    contaBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const abrir = !contaMenu.classList.contains("open");
      contaMenu.classList.toggle("open", abrir);
      contaBtn.setAttribute("aria-expanded", String(abrir));
    });
    document.addEventListener("click", (e) => {
      if (!contaMenu.contains(e.target)) {
        contaMenu.classList.remove("open");
        contaBtn.setAttribute("aria-expanded", "false");
      }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        contaMenu.classList.remove("open");
        contaBtn.setAttribute("aria-expanded", "false");
      }
    });
  }

  // sombra no cabeçalho ao rolar
  const header = document.querySelector(".site-header");
  const aoRolar = () => header && header.classList.toggle("scrolled", window.scrollY > 8);
  aoRolar();
  window.addEventListener("scroll", aoRolar, { passive: true });

  // revelar blocos marcados com data-reveal ao entrar na tela (com pequeno escalonamento entre irmãos)
  const alvos = document.querySelectorAll("[data-reveal]");
  const contagem = new Map();
  alvos.forEach((el) => {
    const n = contagem.get(el.parentElement) || 0;
    contagem.set(el.parentElement, n + 1);
    el.style.setProperty("--d", Math.min(n, 6) * 70 + "ms");
  });
  if ("IntersectionObserver" in window) {
    const obs = new IntersectionObserver(
      (entradas) => {
        entradas.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("in");
            obs.unobserve(e.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -30px 0px" }
    );
    alvos.forEach((el) => obs.observe(el));
  } else {
    alvos.forEach((el) => el.classList.add("in"));
  }

  // número do carrinho pulsa quando aumenta
  const badge = document.querySelector(".cart-count");
  const atual = badge ? parseInt(badge.textContent, 10) || 0 : 0;
  try {
    const anterior = parseInt(sessionStorage.getItem("cartQtd") || "0", 10);
    if (badge && atual > anterior) badge.classList.add("pop");
    sessionStorage.setItem("cartQtd", String(atual));
  } catch (e) { /* storage indisponível: sem animação */ }

  // fade ao sair da página (só links internos)
  if (!reduzir) {
    document.addEventListener("click", (e) => {
      const a = e.target.closest("a[href]");
      if (!a || e.defaultPrevented || e.button !== 0) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      if (a.target === "_blank" || a.hasAttribute("download")) return;
      const url = new URL(a.href, location.href);
      if (url.origin !== location.origin) return;
      if (url.pathname === location.pathname && url.search === location.search) return;
      e.preventDefault();
      document.body.classList.add("leaving");
      setTimeout(() => { location.href = a.href; }, 180);
    });
  }

  // checkout: evita clique duplo e mostra que está gerando o Pix
  const form = document.querySelector(".checkout-form");
  if (form) {
    form.addEventListener("submit", () => {
      const b = form.querySelector("button[type=submit]");
      if (b) {
        b.dataset.label = b.innerHTML;
        b.disabled = true;
        b.textContent = "Gerando Pix…";
      }
    });
  }
});

// voltar pelo histórico: desfaz o fade de saída e reabilita botões
window.addEventListener("pageshow", (e) => {
  if (!e.persisted) return;
  document.body.classList.remove("leaving");
  document.querySelectorAll("button[data-label]").forEach((b) => {
    b.disabled = false;
    b.innerHTML = b.dataset.label;
  });
});
