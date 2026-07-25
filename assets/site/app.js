const papers = [
  {
    conference: "CVPR",
    status: "Highlight",
    priority: "must",
    priorityLabel: "Must read",
    title: "A Frame is Worth One Token: Efficient Generative World Modeling with Delta Tokens",
    summary: "DeltaWorld 把相邻帧的 VFM 特征差压成单个连续 delta token，将 512×512 视频缩短 1,024 倍；用 35 倍更少参数和 2,000 倍更少 FLOPs，一次前向就能给出多种未来。",
    match: "world model · efficient rollout · delta token",
    authors: "Tommie Kerssies, Gabriele Berton, Ju He, Qihang Yu, Wufei Ma, et al.",
    url: "https://cvpr.thecvf.com/virtual/2026/poster/38021"
  },
  {
    conference: "ICML",
    status: "Spotlight",
    priority: "must",
    priorityLabel: "Must read",
    title: "DreamDojo: A Real-Time Robot World Model from Large-Scale Human Videos",
    summary: "从 4.4 万小时第一视角人类视频学习连续 latent action，再用少量机器人数据后训练；蒸馏后达到 10.93 FPS，可直接服务实时遥操作、策略评估和 model-based planning。",
    match: "robot world model · latent action · real-time simulation",
    authors: "Shenyuan Gao, William Liang, Kaiyuan Zheng, Ayaan Malik, Seonghyeon Ye, et al.",
    url: "https://icml.cc/virtual/2026/poster/65193"
  },
  {
    conference: "ACL",
    status: "Poster",
    priority: "must",
    priorityLabel: "Must read",
    title: "From Word to World: Can Large Language Models be Implicit Text-based World Models?",
    summary: "把语言建模改写成交互中的 next-state prediction，并从 fidelity、scaling 和 agent utility 三层验证 LLM world model；action verification 让 GPT-4o 在 WebShop 提升 5.5%。",
    match: "text world model · agent utility · next-state prediction",
    authors: "Yixia Li, Hongru Wang, Jiahao Qiu, Zhenfei Yin, Dongdong Zhang, et al.",
    url: "https://aclanthology.org/2026.acl-long.366/"
  },
  {
    conference: "CVPR",
    status: "Highlight",
    priority: "worth",
    priorityLabel: "Worth reading",
    title: "Physical Object Understanding with a Physically Controllable World Model",
    summary: "用概率式 world model 从局部视频观察多个可能未来，再从跨未来的运动相关性涌现出对象和可动子部件；不仅识别物理结构，还能在 3D 中直接操控对象。",
    match: "physical control · object dynamics · probabilistic futures",
    authors: "Rahul Venkatesh, Klemen Kotar, Lilian Naing Chen, Wanhee Lee, Gia Ancone, et al.",
    url: "https://cvpr.thecvf.com/virtual/2026/poster/37466"
  },
  {
    conference: "ICML",
    status: "Poster",
    priority: "worth",
    priorityLabel: "Worth reading",
    title: "Causal-JEPA: Learning World Models through Object-Level Latent Interventions",
    summary: "把 JEPA 的遮挡预测从 patch 提升到对象层，通过 latent intervention 迫使模型理解交互而不是走捷径；反事实推理绝对提升约 20%，规划只需 patch world model 约 1% 的 latent 特征。",
    match: "causal world model · object interaction · JEPA",
    authors: "Heejeong Nam, Quentin Le Lidec, Lucas Maes, Yann LeCun, Randall Balestriero",
    url: "https://icml.cc/virtual/2026/poster/63623"
  },
  {
    conference: "ACL",
    status: "Poster",
    priority: "worth",
    priorityLabel: "Worth reading",
    title: "Current Agents Fail to Leverage World Model as Tool for Foresight",
    summary: "直接检验 agent 会不会把生成式 world model 当外部模拟器：部分 agent 调用率低于 1%，约 15% 会误用 rollout，强制模拟甚至让性能下降 5%，瓶颈在何时模拟和如何解释未来。",
    match: "agent foresight · simulation tool use · calibration",
    authors: "Cheng Qian, Emre Can Acikgoz, Bingxuan Li, Xiusi Chen, Yuji Zhang, et al.",
    url: "https://aclanthology.org/2026.acl-long.623/"
  }
];

const runConfigs = {
  daily: {
    title: "正在准备今日推送",
    command: "daily-papers --date 2026-07-25 --conf CVPR,ICML,ACL",
    steps: [
      ["读取三份 2026 接收列表", "3 sources"],
      ["按 World Model topic 与关键词打分", "6 matches"],
      ["生成锐评、分流与摘要式笔记", "ready"]
    ]
  },
  gallery: {
    title: "正在构建领域画廊",
    command: "domain-papers gallery --domain \"MLLM Personalization\"",
    steps: [
      ["读取详细论文笔记与 category", "23 notes"],
      ["恢复年份、首图与工作关系", "2024—2026"],
      ["导出可分享的 Gallery HTML", "ready"]
    ]
  }
};

const views = [...document.querySelectorAll("[data-view]")];
const dialog = document.querySelector("#run-dialog");
const runTitle = document.querySelector("#run-title");
const runCommand = document.querySelector("#run-command");
const runSteps = document.querySelector("#run-steps");
const progressBar = document.querySelector("#run-progress-bar");
const feed = document.querySelector("#paper-feed");
const filterSummary = document.querySelector("#filter-summary");
let running = false;

function activeRoute() {
  const route = window.location.hash.replace("#", "");
  return ["daily", "gallery"].includes(route) ? route : "home";
}

function showView(route) {
  views.forEach((view) => {
    const isActive = view.dataset.view === route;
    view.hidden = !isActive;
    view.classList.toggle("is-active", isActive);
  });
  document.title = route === "daily"
    ? "Today's Paper Delivery · Research Paper Claw"
    : route === "gallery"
      ? "MLLM Personalization Gallery · Research Paper Claw"
      : "Personalized Research Paper Claw";
  window.scrollTo({ top: 0, behavior: "instant" });
}

function paperMarkup(paper, index) {
  return `
    <article class="paper-card" data-paper-conference="${paper.conference}">
      <div class="paper-index">
        <span class="paper-rank">${String(index + 1).padStart(2, "0")}</span>
        <span class="conference-badge">${paper.conference} 26 · ${paper.status}</span>
      </div>
      <div class="paper-main">
        <h2>${paper.title}</h2>
        <p>${paper.summary}</p>
        <p class="authors">${paper.authors}</p>
      </div>
      <div class="paper-match">
        <span class="priority-badge ${paper.priority}">${paper.priorityLabel}</span>
        <p><strong>Why it matched</strong>${paper.match}</p>
        <a class="paper-link" href="${paper.url}" target="_blank" rel="noopener">查看论文 <span aria-hidden="true">↗</span></a>
      </div>
    </article>`;
}

function renderPapers(conference = "all") {
  const selected = conference === "all"
    ? papers
    : papers.filter((paper) => paper.conference === conference);
  feed.innerHTML = selected.map(paperMarkup).join("");
  filterSummary.textContent = `Showing ${selected.length} World Model match${selected.length === 1 ? "" : "es"}`;
}

function delay(milliseconds) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

async function runDemo(route) {
  if (running) return;
  running = true;
  const config = runConfigs[route];
  runTitle.textContent = config.title;
  runCommand.textContent = config.command;
  runSteps.innerHTML = config.steps.map(([label, meta]) => `<li>${label}<span>${meta}</span></li>`).join("");
  progressBar.style.width = "0";
  dialog.showModal();

  const steps = [...runSteps.children];
  for (let index = 0; index < steps.length; index += 1) {
    steps.forEach((step, stepIndex) => {
      step.classList.toggle("is-active", stepIndex === index);
      step.classList.toggle("is-done", stepIndex < index);
    });
    progressBar.style.width = `${(index + 1) * (100 / steps.length)}%`;
    await delay(index === 0 ? 520 : 620);
  }

  steps.forEach((step) => {
    step.classList.remove("is-active");
    step.classList.add("is-done");
  });
  await delay(260);
  dialog.close();
  running = false;
  window.location.hash = route;
}

document.querySelectorAll("[data-run]").forEach((button) => {
  button.addEventListener("click", () => runDemo(button.dataset.run));
});

document.querySelectorAll("[data-back]").forEach((button) => {
  button.addEventListener("click", () => {
    window.location.hash = "home";
  });
});

document.querySelectorAll("[data-conference]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-conference]").forEach((candidate) => {
      const selected = candidate === button;
      candidate.classList.toggle("is-selected", selected);
      candidate.setAttribute("aria-pressed", String(selected));
    });
    renderPapers(button.dataset.conference);
  });
});

dialog.addEventListener("cancel", (event) => {
  if (running) event.preventDefault();
});

window.addEventListener("hashchange", () => showView(activeRoute()));
renderPapers();
showView(activeRoute());
