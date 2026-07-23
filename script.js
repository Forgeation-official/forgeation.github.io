/* =========================================================

   Forgeation Ver.3

   script.js

   ========================================================= */

"use strict";

document.addEventListener("DOMContentLoaded", () => {

  /* ---------------------------------------------------------

     基本設定

  --------------------------------------------------------- */

  const body = document.body;

  const header = document.querySelector(

    "header, .site-header, .main-header, #header"

  );

  /* ---------------------------------------------------------

     蒼のオープニング

     HTML側に以下のいずれかが存在する場合のみ動作

     #opening / .opening / .opening-screen / .splash

  --------------------------------------------------------- */

  const opening = document.querySelector(

    "#opening, .opening, .opening-screen, .splash"

  );

  if (opening) {

    body.classList.add("is-opening");

    const closeOpening = () => {

      opening.classList.add("is-hidden");

      body.classList.remove("is-opening");

      body.classList.add("opening-finished");

      window.setTimeout(() => {

        opening.setAttribute("aria-hidden", "true");

        opening.style.display = "none";

      }, 1000);

    };

    const openingButton = opening.querySelector(

      "[data-opening-close], .opening-close, .enter-button"

    );

    if (openingButton) {

      openingButton.addEventListener("click", closeOpening);

    }

    window.setTimeout(closeOpening, 3200);

  } else {

    body.classList.add("opening-finished");

  }

  /* ---------------------------------------------------------

     モバイルメニュー

  --------------------------------------------------------- */

  const menuButton = document.querySelector(

    ".menu-toggle, .hamburger, .nav-toggle, [data-menu-toggle]"

  );

  const navigation = document.querySelector(

    ".global-nav, .main-nav, .site-nav, nav"

  );

  const closeMenu = () => {

    if (!menuButton || !navigation) return;

    menuButton.classList.remove("is-active");

    navigation.classList.remove("is-open");

    body.classList.remove("menu-open");

    menuButton.setAttribute("aria-expanded", "false");

  };

  const openMenu = () => {

    if (!menuButton || !navigation) return;

    menuButton.classList.add("is-active");

    navigation.classList.add("is-open");

    body.classList.add("menu-open");

    menuButton.setAttribute("aria-expanded", "true");

  };

  if (menuButton && navigation) {

    menuButton.setAttribute("aria-expanded", "false");

    menuButton.addEventListener("click", () => {

      const isOpen = navigation.classList.contains("is-open");

      if (isOpen) {

        closeMenu();

      } else {

        openMenu();

      }

    });

    navigation.querySelectorAll("a").forEach((link) => {

      link.addEventListener("click", closeMenu);

    });

    document.addEventListener("click", (event) => {

      const target = event.target;

      if (

        navigation.classList.contains("is-open") &&

        !navigation.contains(target) &&

        !menuButton.contains(target)

      ) {

        closeMenu();

      }

    });

    window.addEventListener("resize", () => {

      if (window.innerWidth >= 900) {

        closeMenu();

      }

    });

  }

  /* ---------------------------------------------------------

     ヘッダーのスクロール変化

  --------------------------------------------------------- */

  const updateHeader = () => {

    if (!header) return;

    if (window.scrollY > 40) {

      header.classList.add("is-scrolled");

    } else {

      header.classList.remove("is-scrolled");

    }

  };

  updateHeader();

  window.addEventListener("scroll", updateHeader, { passive: true });

  /* ---------------------------------------------------------

     ページ内リンクのスムーススクロール

  --------------------------------------------------------- */

  document.querySelectorAll('a[href^="#"]').forEach((link) => {

    link.addEventListener("click", (event) => {

      const href = link.getAttribute("href");

      if (!href || href === "#") return;

      const target = document.querySelector(href);

      if (!target) return;

      event.preventDefault();

      const headerHeight = header ? header.offsetHeight : 0;

      const targetPosition =

        target.getBoundingClientRect().top +

        window.scrollY -

        headerHeight -

        12;

      window.scrollTo({

        top: targetPosition,

        behavior: "smooth",

      });

      history.pushState(null, "", href);

    });

  });

  /* ---------------------------------------------------------

     スクロール表示アニメーション

     .reveal / .fade-up / [data-reveal]

  --------------------------------------------------------- */

  const revealElements = document.querySelectorAll(

    ".reveal, .fade-up, [data-reveal]"

  );

  if ("IntersectionObserver" in window && revealElements.length > 0) {

    const revealObserver = new IntersectionObserver(

      (entries, observer) => {

        entries.forEach((entry) => {

          if (!entry.isIntersecting) return;

          entry.target.classList.add("is-visible");

          observer.unobserve(entry.target);

        });

      },

      {

        root: null,

        threshold: 0.12,

        rootMargin: "0px 0px -40px 0px",

      }

    );

    revealElements.forEach((element, index) => {

      element.style.setProperty("--reveal-delay", `${index * 45}ms`);

      revealObserver.observe(element);

    });

  } else {

    revealElements.forEach((element) => {

      element.classList.add("is-visible");

    });

  }

  /* ---------------------------------------------------------

     アカデミーカード

     クリック可能領域を広げる

  --------------------------------------------------------- */

  const academyCards = document.querySelectorAll(

    ".academy-card, .academy-item, [data-card-link]"

  );

  academyCards.forEach((card) => {

    const link = card.querySelector("a[href]");

    if (!link) return;

    card.setAttribute("tabindex", "0");

    card.setAttribute("role", "link");

    card.addEventListener("click", (event) => {

      if (event.target.closest("a, button, input, textarea, select")) return;

      window.location.href = link.href;

    });

    card.addEventListener("keydown", (event) => {

      if (event.key !== "Enter" && event.key !== " ") return;

      event.preventDefault();

      window.location.href = link.href;

    });

  });

  /* ---------------------------------------------------------

     画像の読み込み完了処理

  --------------------------------------------------------- */

  const images = document.querySelectorAll("img");

  images.forEach((image) => {

    const loaded = () => {

      image.classList.add("is-loaded");

    };

    if (image.complete) {

      loaded();

    } else {

      image.addEventListener("load", loaded, { once: true });

      image.addEventListener(

        "error",

        () => {

          image.classList.add("is-error");

        },

        { once: true }

      );

    }

  });

  /* ---------------------------------------------------------

     ページトップボタン

     既存ボタンがなければ自動生成

  --------------------------------------------------------- */

  let pageTopButton = document.querySelector(

    ".page-top, #page-top, [data-page-top]"

  );

  if (!pageTopButton) {

    pageTopButton = document.createElement("button");

    pageTopButton.type = "button";

    pageTopButton.className = "page-top";

    pageTopButton.setAttribute("aria-label", "ページ上部へ戻る");

    pageTopButton.innerHTML = "↑";

    body.appendChild(pageTopButton);

  }

  const updatePageTop = () => {

    if (window.scrollY > 500) {

      pageTopButton.classList.add("is-visible");

    } else {

      pageTopButton.classList.remove("is-visible");

    }

  };

  pageTopButton.addEventListener("click", () => {

    window.scrollTo({

      top: 0,

      behavior: "smooth",

    });

  });

  updatePageTop();

  window.addEventListener("scroll", updatePageTop, { passive: true });

  /* ---------------------------------------------------------

     現在ページのナビゲーション表示

  --------------------------------------------------------- */

  const currentPath = window.location.pathname

    .split("/")

    .pop()

    .toLowerCase();

  document.querySelectorAll("nav a[href], .global-nav a[href]").forEach(

    (link) => {

      const linkPath = link

        .getAttribute("href")

        .split("#")[0]

        .split("/")

        .pop()

        .toLowerCase();

      if (

        linkPath &&

        currentPath &&

        linkPath === currentPath

      ) {

        link.classList.add("is-current");

        link.setAttribute("aria-current", "page");

      }

    }

  );

  /* ---------------------------------------------------------

     3要素プロフィール表示

     data-profile-target="#profile-nogu" 等に対応

  --------------------------------------------------------- */

  const profileTriggers = document.querySelectorAll(

    "[data-profile-target]"

  );

  const profilePanels = document.querySelectorAll(

    ".profile-panel, [data-profile-panel]"

  );

  const closeProfiles = () => {

    profilePanels.forEach((panel) => {

      panel.classList.remove("is-open");

      panel.setAttribute("aria-hidden", "true");

    });

    body.classList.remove("profile-open");

  };

  profileTriggers.forEach((trigger) => {

    trigger.addEventListener("click", () => {

      const selector = trigger.dataset.profileTarget;

      const targetPanel = selector

        ? document.querySelector(selector)

        : null;

      if (!targetPanel) return;

      const alreadyOpen = targetPanel.classList.contains("is-open");

      closeProfiles();

      if (!alreadyOpen) {

        targetPanel.classList.add("is-open");

        targetPanel.setAttribute("aria-hidden", "false");

        body.classList.add("profile-open");

      }

    });

  });

  document.querySelectorAll(

    ".profile-close, [data-profile-close]"

  ).forEach((button) => {

    button.addEventListener("click", closeProfiles);

  });

  profilePanels.forEach((panel) => {

    panel.addEventListener("click", (event) => {

      if (event.target === panel) {

        closeProfiles();

      }

    });

  });

  /* ---------------------------------------------------------

     Escapeキー共通処理

  --------------------------------------------------------- */

  document.addEventListener("keydown", (event) => {

    if (event.key !== "Escape") return;

    closeMenu();

    closeProfiles();

  });

  /* ---------------------------------------------------------

     外部リンクの安全設定

  --------------------------------------------------------- */

  document.querySelectorAll('a[target="_blank"]').forEach((link) => {

    const rel = new Set(

      (link.getAttribute("rel") || "")

        .split(" ")

        .filter(Boolean)

    );

    rel.add("noopener");

    rel.add("noreferrer");

    link.setAttribute("rel", Array.from(rel).join(" "));

  });

  /* ---------------------------------------------------------

     JavaScript起動完了

  --------------------------------------------------------- */

  body.classList.add("js-ready");

});