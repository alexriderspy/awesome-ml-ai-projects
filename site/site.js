(function () {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const cloud = document.querySelector(".cloud");
  const hero = document.querySelector(".hero");
  const frame = document.querySelector(".finder .frame");
  let t0 = performance.now();

  function tick(now) {
    const y = window.scrollY;
    if (cloud && hero) {
      const p = Math.min(1, y / Math.max(1, hero.offsetHeight - window.innerHeight));
      const sway = reduce ? 0 : Math.sin((now - t0) / 4000) * 10;
      cloud.style.transform = `translateZ(${p * 900}px) rotateY(${sway + p * 25}deg) rotateX(${p * -6}deg)`;
      const copy = document.querySelector(".hero-copy");
      if (copy) copy.style.opacity = String(Math.max(0, 1 - p * 1.6));
    }
    if (frame) {
      const r = frame.parentElement.getBoundingClientRect();
      const q = Math.min(1, Math.max(0, 1 - r.top / window.innerHeight));
      frame.style.setProperty("--zoom", String(0.8 + q * 0.2));
    }
    requestAnimationFrame(tick);
  }
  if (cloud || frame) requestAnimationFrame(tick);

  const chips = document.querySelectorAll(".chip");
  const cards = document.querySelectorAll(".pcard");
  const count = document.querySelector("[data-count]");
  chips.forEach((chip) => chip.addEventListener("click", () => {
    const cat = chip.dataset.cat;
    chips.forEach((c) => c.setAttribute("aria-pressed", String(c === chip)));
    let shown = 0;
    cards.forEach((card) => {
      const on = cat === "all" || card.dataset.cat === cat;
      card.style.display = on ? "" : "none";
      if (on) shown += 1;
    });
    if (count) count.textContent = `${shown} of ${cards.length} projects`;
  }));

  const tasks = document.querySelector("ul.tasks");
  if (tasks) {
    const key = "progress:" + location.pathname;
    const boxes = [...tasks.querySelectorAll("input[type=checkbox]")];
    const bar = document.querySelector(".bar i");
    const label = document.querySelector("[data-progress]");
    let saved = [];
    try { saved = JSON.parse(localStorage.getItem(key) || "[]"); } catch (e) { saved = []; }
    boxes.forEach((b, i) => { b.disabled = false; b.checked = !!saved[i]; });
    const update = () => {
      const done = boxes.filter((b) => b.checked).length;
      if (bar) bar.style.width = `${(100 * done) / boxes.length}%`;
      if (label) label.textContent = `${done} of ${boxes.length} done`;
      try { localStorage.setItem(key, JSON.stringify(boxes.map((b) => b.checked))); } catch (e) {}
    };
    boxes.forEach((b) => b.addEventListener("change", update));
    update();
  }
})();
