(() => {
  const page = document.querySelector(".home-preview");
  if (!page) return;

  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const header = document.querySelector("#previewHeader");
  const revealTargets = [...document.querySelectorAll(".home-preview .reveal")];
  const workflowSteps = [...document.querySelectorAll(".home-preview .workflow-step")];
  const workflowPanels = [...document.querySelectorAll(".home-preview [data-step]")];

  function setCondensedHeader() {
    if (!header) return;
    header.classList.toggle("is-condensed", window.scrollY > 28);
  }

  function setActiveStep(stepId) {
    workflowSteps.forEach((step) => {
      const active = step.dataset.stepLink === stepId;
      step.classList.toggle("is-active", active);
      if (active) {
        step.setAttribute("aria-current", "step");
      } else {
        step.removeAttribute("aria-current");
      }
    });
  }

  function syncActiveStep() {
    if (!workflowPanels.length) return;
    const focusY = window.innerHeight * 0.45;
    const visiblePanels = workflowPanels
      .map((panel) => {
        const rect = panel.getBoundingClientRect();
        const center = rect.top + rect.height / 2;
        return {
          step: panel.dataset.step,
          visible: rect.bottom > 0 && rect.top < window.innerHeight,
          distance: Math.abs(center - focusY),
        };
      })
      .filter((panel) => panel.visible)
      .sort((a, b) => a.distance - b.distance);
    if (visiblePanels[0]?.step) setActiveStep(visiblePanels[0].step);
  }

  function revealImmediately() {
    revealTargets.forEach((target) => target.classList.add("is-visible"));
    workflowPanels[0] && setActiveStep(workflowPanels[0].dataset.step);
  }

  if (prefersReducedMotion.matches) {
    page.classList.add("reduce-motion");
    revealImmediately();
    setCondensedHeader();
    window.addEventListener(
      "scroll",
      () => {
        setCondensedHeader();
        syncActiveStep();
      },
      { passive: true },
    );
    return;
  }

  page.classList.add("has-motion");
  setCondensedHeader();
  syncActiveStep();
  window.addEventListener(
    "scroll",
    () => {
      setCondensedHeader();
      syncActiveStep();
    },
    { passive: true },
  );

  const revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        revealObserver.unobserve(entry.target);
      });
    },
    { rootMargin: "0px 0px -12% 0px", threshold: 0.12 },
  );

  revealTargets.forEach((target) => revealObserver.observe(target));

  const stepObserver = new IntersectionObserver(
    () => syncActiveStep(),
    { rootMargin: "-18% 0px -42% 0px", threshold: [0, 0.18, 0.32, 0.5, 0.68, 0.86] },
  );

  workflowPanels.forEach((panel) => stepObserver.observe(panel));
})();
