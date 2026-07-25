const papers = [
  {
    conference: "CVPR",
    status: "Highlight",
    priority: "must",
    priorityLabel: "Must read",
    title: "Premier: Personalized Preference Modulation with Learnable User Embedding in Text-to-Image Generation",
    summary: "用可学习 user embedding 和 preference adapter 把用户偏好直接注入生成过程，并通过 dispersion loss 拉开个体风格；比依赖 MLLM 猜提示词更接近可控的长期个性化。",
    match: "MLLM personalization · preference learning",
    authors: "Zihao Wang, Yuxiang Wei, Xinpeng Zhou, Tianyu Zhang, Tao Liang, et al.",
    url: "https://cvpr.thecvf.com/virtual/2026/poster/37526"
  },
  {
    conference: "ACL",
    status: "Findings",
    priority: "must",
    priorityLabel: "Must read",
    title: "EgoMemory: Memory-Augmented Personalized Retrieval for Long-Context Egocentric Video",
    summary: "把 45 位用户的长期第一视角视频组织成个性化情景记忆检索任务；training-free EgoRetriever 用反思式 CoT 解释用户意图，并在三项基准上稳定超过现有方法。",
    match: "personal memory · long-context MLLM",
    authors: "Yuanmin Tang, Jue Zhang, Xiaoting Qin, Jing Yu, Meikang Qiu, et al.",
    url: "https://aclanthology.org/2026.findings-acl.362/"
  },
  {
    conference: "ACL",
    status: "Findings",
    priority: "must",
    priorityLabel: "Must read",
    title: "Beyond Static Profiles: Capturing the Fluidity of User Preferences in Diverse Scenarios",
    summary: "用 stable preference 与 situational preference 的分层 taxonomy 拆开静态画像和情境偏好，并以 10k 条 S2Pref 检验模型能否优先使用上下文、主动消解歧义。",
    match: "dynamic preference · user profiling",
    authors: "Chunyang Gao, Yi Huang, Jingyu Yao, Xiaoting Wu, Junlan Feng",
    url: "https://aclanthology.org/2026.findings-acl.1033/"
  },
  {
    conference: "CVPR",
    status: "Highlight",
    priority: "worth",
    priorityLabel: "Worth reading",
    title: "WorldMM: Dynamic Multimodal Memory Agent for Long Video Reasoning",
    summary: "同时维护 episodic、semantic 与 visual memory，让检索 agent 按问题自适应选择记忆源和时间尺度；长视频问答平均比此前 SOTA 提升 8.4%。",
    match: "multimodal memory · agentic retrieval",
    authors: "Woongyeong Yeo, Kangsan Kim, Jaehong Yoon, Sung Ju",
    url: "https://cvpr.thecvf.com/virtual/2026/poster/39925"
  },
  {
    conference: "ICML",
    status: "Poster",
    priority: "worth",
    priorityLabel: "Worth reading",
    title: "MMKU-Bench: A Multimodal Update Benchmark for Diverse Visual Knowledge",
    summary: "覆盖 25k 知识实例与 49k 图像，把“未知知识学习”和“已知知识更新”放进同一跨模态评测；结果显示 SFT、RLHF 容易灾难性遗忘，KE 的持续更新仍有限。",
    match: "multimodal update · continual memory",
    authors: "Baochen Fu, Yuntao Du, Cheng Chang, Baihao Jin, Wenzhi Deng, et al.",
    url: "https://icml.cc/virtual/2026/poster/63508"
  },
  {
    conference: "ICML",
    status: "Poster",
    priority: "worth",
    priorityLabel: "Worth reading",
    title: "Optimal Bayesian Stopping for Efficient Inference of Consistent LLM Answers",
    summary: "为多次采样投票加入 Bayesian stopping，只跟踪高频答案即可提前停止；理论上证明 L=3 足以渐近最优，在维持答案准确率时减少推理采样。",
    match: "LLM reliability · efficient inference",
    authors: "Jingkai Huang, Will Ma, Zhengyuan Zhou",
    url: "https://icml.cc/virtual/2026/poster/64810"
  }
];

const runConfigs = {
  daily: {
    title: "正在准备今日推送",
    command: "daily-papers --date 2026-07-25 --conf CVPR,ICML,ACL",
    steps: [
      ["读取三份 2026 接收列表", "3 sources"],
      ["按个人研究偏好打分与去重", "6 matches"],
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
  filterSummary.textContent = `Showing ${selected.length} personalized match${selected.length === 1 ? "" : "es"}`;
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
