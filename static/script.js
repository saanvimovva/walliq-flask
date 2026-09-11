const form = document.querySelector("#lookupForm");
const addressInput = document.querySelector("#walletAddress");
const networkInput = document.querySelector("#network");
const addressStatus = document.querySelector("#addressStatus");
const sourceList = document.querySelector("#sourceList");
const ownerPanel = document.querySelector("#ownerPanel");
const walletSignals = document.querySelector("#walletSignals");
const ensIntel = document.querySelector("#ensIntel");
const alchemyIntel = document.querySelector("#alchemyIntel");
const coingeckoIntel = document.querySelector("#coingeckoIntel");
const openseaIntel = document.querySelector("#openseaIntel");
const aiAnalysis = document.querySelector("#aiAnalysis");
const lookupStatus = document.querySelector("#lookupStatus");
const summary = document.querySelector("#summary");
const transactions = document.querySelector("#transactions");
const transactionFilters = document.querySelector("#transactionFilters");
const sampleButtons = document.querySelectorAll("[data-address]");
const tabButtons = document.querySelectorAll("[data-tab]");
const tabPanels = document.querySelectorAll(".tab-panel");

let currentTransactions = [];
let currentExplorerTx = "";
let activeTransactionFilter = "all";

function isEthAddress(value) {
  return /^0x[a-fA-F0-9]{40}$/.test(value.trim());
}

function updateAddressStatus() {
  const address = addressInput.value.trim();
  addressInput.classList.remove("valid", "invalid");
  addressStatus.classList.remove("valid", "invalid");

  if (!address) {
    addressStatus.textContent = "Waiting for a wallet address.";
    return false;
  }
  if (!address.startsWith("0x")) return invalidAddress("Invalid: address must start with 0x.");
  if (address.length !== 42) return invalidAddress(`Invalid: address is ${address.length} characters; expected 42.`);
  if (!isEthAddress(address)) return invalidAddress("Invalid: only hexadecimal characters are allowed after 0x.");

  addressInput.classList.add("valid");
  addressStatus.classList.add("valid");
  addressStatus.textContent = "Valid EVM address format. Ready for backend lookup.";
  return true;
}

function invalidAddress(message) {
  addressInput.classList.add("invalid");
  addressStatus.classList.add("invalid");
  addressStatus.textContent = message;
  return false;
}

async function fetchLookup(address) {
  const response = await fetch(`/api/lookup?address=${encodeURIComponent(address)}&network=${encodeURIComponent(networkInput.value)}`);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "Lookup failed.");
  return body;
}

function renderLookup(result) {
  currentExplorerTx = result.signals?.network?.explorerTx || "";
  currentTransactions = Array.isArray(result.transactions) ? result.transactions : [];

  renderVerdictBuckets(result);
  renderSources(result.dataSources || []);
  renderOwner(result.owner || {});
  renderWalletSignals(result.signals || {});
  renderEns(result.ens || {}, result.dataSources || []);
  renderAlchemy(result.alchemy || {}, result.dataSources || []);
  renderCoinGecko(result.coingecko || {}, result.dataSources || []);
  renderOpenSea(result.opensea || {}, result.dataSources || []);
  renderAiAnalysis(result.aiAnalysis, result.dataSources || []);
  drawTransactions();
  renderStatus(result);
}

function renderEns(data, sources) {
  const source = sources.find((item) => item.name === "ENS");
  if (source?.status === "failed") {
    ensIntel.innerHTML = `<div class="empty">${source.error || "ENS lookup failed."}</div>`;
    return;
  }

  ensIntel.innerHTML = [
    ["Primary name", data.name || "No ENS name found", data.detail || "Reverse lookup completed."],
    ["Coin type", data.coinType || "60", "ETH uses 60; Base uses ENSIP-19 coin type"],
    ["Resolver", data.resolver ? shortAddress(data.resolver) : "Unavailable"],
    ["Value", "Identity clue", "Not legal ownership proof"],
  ].map(card).join("");
}

function renderSources(sources) {
  sourceList.innerHTML = sources.map((source) => `
    <div class="source ${source.status}">
      <strong>${source.name}</strong>
      <span>${statusLabel(source.status)}</span>
      ${source.error ? `<small>${source.error}</small>` : ""}
    </div>
  `).join("");
}

function statusLabel(status) {
  const labels = {
    available: "Available",
    partial: "Partial data",
    not_configured: "Not configured",
    account_limited: "Account setup needed",
    auth_failed: "Authentication failed",
    failed: "Failed",
  };
  return labels[status] || status || "Unknown";
}

function renderOwner(owner) {
  ownerPanel.innerHTML = [
    ["Owner", owner.label || "Unknown owner", owner.detail || "No owner evidence returned."],
    ["Status", owner.status || "unknown", "Known, named, contract, or unknown"],
    ["Type", owner.type || "Unavailable", "Address classification"],
    ["Source", owner.source || "Unavailable", `Confidence: ${owner.confidence || "not available"}`],
  ].map(card).join("");
}

function renderWalletSignals(data) {
  if (!Object.keys(data).length) {
    walletSignals.innerHTML = `<div class="empty">RPC wallet signals are unavailable.</div>`;
    return;
  }

  walletSignals.innerHTML = [
    ["Network", data.network?.name || "Unavailable"],
    ["Address type", data.isContract ? "Smart contract" : "Normal wallet"],
    ["Known address", data.knownLabel ? data.knownLabel.label : "No local label"],
    ["Native balance", `${formatNumber(data.nativeBalance)} ${data.network?.currency || ""}`],
    ["Outgoing tx count", Number(data.txCount || 0).toLocaleString()],
    ["USDC balance", `${formatNumber(data.usdcBalance)} USDC`],
    ["Recent USDC transfers", Number(data.recentUsdcTransfers || 0).toLocaleString()],
    ["Recent USDC volume", `${formatNumber(data.recentUsdcVolume)} USDC`],
    ["Recent counterparties", Number(data.counterparties || 0).toLocaleString()],
    ["Latest block", Number(data.latestBlock || 0).toLocaleString()],
    ["Block window scanned", Number(data.logWindowBlocks || 0).toLocaleString()],
  ].map(card).join("");
}

function renderAlchemy(data, sources) {
  const source = sources.find((item) => item.name === "Alchemy");
  if (!data || source?.status === "not_configured") {
    alchemyIntel.innerHTML = `<div class="empty">Alchemy is optional. Add ALCHEMY_API_KEY to .env for token, transfer, and NFT enrichment.</div>`;
    return;
  }
  if (["account_limited", "auth_failed", "failed"].includes(source?.status)) {
    alchemyIntel.innerHTML = `<div class="empty">${source.error || "Alchemy failed."}</div>`;
    return;
  }

  const tokens = Array.isArray(data.tokenBalances) ? data.tokenBalances : [];
  const transfers = Array.isArray(data.recentTransfers) ? data.recentTransfers : [];
  const nfts = Array.isArray(data.nfts) ? data.nfts : [];

  alchemyIntel.innerHTML = [
    ["Source status", statusLabel(source?.status || "unknown")],
    ["Network", data.network || "Unavailable"],
    ["ERC-20 tokens", `${tokens.length} shown`, tokens.slice(0, 4).map((item) => `${item.symbol}${item.balanceFormatted ? ` ${item.balanceFormatted}` : ""}`).join(", ") || "No token sample"],
    ["Recent transfers", `${transfers.length} shown`, transfers.slice(0, 2).map((item) => `${item.direction} ${item.asset || item.category}`).join(" | ") || "No transfer sample"],
    ["NFT sample", `${nfts.length} shown`, nfts.slice(0, 3).map((item) => item.collectionName || item.name).filter(Boolean).join(", ") || "No NFT sample"],
    ["Value", "Activity enrichment", "Not owner proof or compliance attribution"],
  ].map(card).join("");
}

function renderCoinGecko(data, sources) {
  const source = sources.find((item) => item.name === "CoinGecko");
  if (!data || source?.status === "not_configured") {
    coingeckoIntel.innerHTML = `<div class="empty">CoinGecko is optional. Add COINGECKO_API_KEY to .env for token pricing.</div>`;
    return;
  }
  if (["account_limited", "auth_failed", "failed"].includes(source?.status)) {
    coingeckoIntel.innerHTML = `<div class="empty">${source.error || "CoinGecko failed."}</div>`;
    return;
  }

  const tokens = Array.isArray(data.tokens) ? data.tokens : [];
  const priced = tokens.filter((item) => item.priceUsd !== null && item.priceUsd !== undefined);
  const pricedSample = priced
    .slice(0, 4)
    .map((item) => `${item.symbol}: ${money(item.priceUsd)}`)
    .join(", ");

  coingeckoIntel.innerHTML = [
    ["Source status", statusLabel(source?.status || "unknown")],
    ["Platform", data.platform || "Unavailable"],
    ["Portfolio value", money(data.portfolioValueUsd || 0), "Based on priced Alchemy token sample"],
    ["Priced tokens", `${data.pricedTokenCount || 0} of ${tokens.length}`, pricedSample || "No CoinGecko price matches"],
    ["Largest priced holding", largestHoldingLabel(priced)],
    ["Value", "Token market pricing", "Not owner proof or wallet attribution"],
  ].map(card).join("");
}

function renderOpenSea(data, sources) {
  const source = sources.find((item) => item.name === "OpenSea");
  if (!data || source?.status === "not_configured") {
    openseaIntel.innerHTML = `<div class="empty">OpenSea is optional. Add OPENSEA_API_KEY to .env for NFT holdings and collection samples.</div>`;
    return;
  }
  if (["account_limited", "auth_failed", "failed"].includes(source?.status)) {
    openseaIntel.innerHTML = `<div class="empty">${source.error || "OpenSea failed."}</div>`;
    return;
  }

  const nfts = Array.isArray(data.nfts) ? data.nfts : [];
  const collections = Array.isArray(data.notableCollections) ? data.notableCollections : [];

  openseaIntel.innerHTML = [
    ["Source status", statusLabel(source?.status || "unknown")],
    ["Chain", data.chain || "Unavailable"],
    ["NFTs shown", String(data.nftCountShown || nfts.length)],
    ["Notable collections", collections.map((item) => `${item.collection} (${item.count})`).join(", ") || "No collection sample"],
    ["NFT sample", nfts.slice(0, 3).map((item) => item.name).filter(Boolean).join(", ") || "No NFT sample"],
    ["Value", "NFT holdings", "Not owner proof or identity attribution"],
  ].map(card).join("");
}

function renderAiAnalysis(data, sources) {
  const source = sources.find((item) => item.name === "OpenAI");
  if (!data || source?.status === "not_configured") {
    aiAnalysis.innerHTML = `<div class="empty">OpenAI analysis is not configured. Add OPENAI_API_KEY to .env.</div>`;
    return;
  }
  if (["account_limited", "auth_failed", "failed"].includes(source?.status)) {
    aiAnalysis.innerHTML = `<div class="empty">${source.error || "OpenAI analysis failed."}</div>`;
    return;
  }

  aiAnalysis.innerHTML = `
    <div class="ai-headline">
      ${card(["Decision", data.decision || "Review needed", data.summary || "No summary returned."])}
      ${card(["Risk level", data.riskLevel || "unknown", `Confidence: ${data.confidence || "low"}`])}
      ${card(["Ownership caveat", data.ownershipCaveat || "Owner cannot be proven from the configured sources."])}
    </div>
    <div class="ai-lists">
      ${listBlock("Key findings", data.keyFindings)}
      ${listBlock("Red flags", data.redFlags)}
      ${listBlock("Missing data", data.missingData)}
      ${listBlock("Next steps", data.recommendedNextSteps)}
    </div>
  `;
}

function renderStatus(result) {
  const warnings = Array.isArray(result.warnings) ? result.warnings : [];
  const explorer = result.signals?.network?.explorerAddress;
  if (!lookupStatus) return;
  lookupStatus.innerHTML = `
    <strong>Architecture:</strong> UI -> Flask /api/lookup -> RPC + ENS + Alchemy + CoinGecko + OpenSea + OpenAI.
    ${warnings.length ? `<br><br><strong>Warnings:</strong><br>${warnings.map((item) => `- ${item}`).join("<br>")}` : ""}
    ${explorer ? `<br><br><a href="${explorer}${result.address}" target="_blank" rel="noreferrer">Open this address in the block explorer</a>` : ""}
  `;
}

function listBlock(title, items) {
  const cleanItems = Array.isArray(items) && items.length ? items : ["No items returned."];
  return `
    <div class="ai-list">
      <h3>${title}</h3>
      <ul>${cleanItems.map((item) => `<li>${item}</li>`).join("")}</ul>
    </div>
  `;
}

function drawTransactions() {
  const filtered = currentTransactions.filter((item) => activeTransactionFilter === "all" || classifyTransaction(item) === activeTransactionFilter);

  if (!currentTransactions.length) {
    transactions.innerHTML = `<div class="empty">No recent decoded transactions were returned.</div>`;
    return;
  }
  if (!filtered.length) {
    transactions.innerHTML = `<div class="empty">No transactions match this filter.</div>`;
    return;
  }

  transactions.innerHTML = filtered.map((item) => {
    const type = classifyTransaction(item);
    const label = bestCounterpartyLabel(item);
    const when = item.blockTimestamp ? new Date(item.blockTimestamp).toLocaleString() : "Time unavailable";
    const hash = item.transactionHash || item.hash || "";
    const explorerUrl = hash && currentExplorerTx ? `${currentExplorerTx}${hash}` : "";
    const summary = item.summary || transferSummary(item);

    return `
      <div class="transaction">
        <span class="tx-type ${type}">${type}</span>
        <div>
          <strong>${summary}</strong>
          <span>${label}</span>
          <small>${when}${item.possibleSpam ? " · possible spam" : ""}</small>
        </div>
        <div>${explorerUrl ? `<a href="${explorerUrl}" target="_blank" rel="noreferrer">View transaction</a>` : "<span>No hash</span>"}</div>
      </div>
    `;
  }).join("");
}

function classifyTransaction(item) {
  const text = `${item.direction || ""} ${item.category || ""} ${item.summary || ""}`.toLowerCase();
  if (text.includes("approve")) return "approve";
  if (text.includes("inbound") || text.includes("received") || text.includes("receive")) return "receive";
  if (text.includes("outbound") || text.includes("sent") || text.includes("send") || text.includes("transferred")) return "send";
  return "contract";
}

function bestCounterpartyLabel(item) {
  const from = item.fromEntity || item.fromLabel || shortAddress(item.fromAddress || item.from);
  const to = item.toEntity || item.toLabel || shortAddress(item.toAddress || item.to);
  if (from && to) return `From ${from} to ${to}`;
  if (from) return `From ${from}`;
  if (to) return `To ${to}`;
  return "Counterparty label unavailable";
}

function transferSummary(item) {
  const direction = item.direction === "inbound" ? "Received" : item.direction === "outbound" ? "Sent" : "Activity";
  const value = item.value === null || item.value === undefined ? "" : formatNumber(item.value, 6);
  const asset = item.asset || item.category || "asset";
  return `${direction} ${value} ${asset}`.replace(/\s+/g, " ").trim();
}

function shortAddress(address) {
  if (!address) return "";
  return `${address.slice(0, 6)}...${address.slice(-4)}`;
}

function card([label, value, detail = ""]) {
  return `
    <div class="card">
      <span>${label}</span>
      <strong>${value}</strong>
      ${detail ? `<small>${detail}</small>` : ""}
    </div>
  `;
}

function formatNumber(value, decimals = 4) {
  return Number(value || 0).toLocaleString("en-US", { maximumFractionDigits: decimals });
}

function money(value) {
  const number = Number(value || 0);
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: number >= 100 ? 0 : 2,
  }).format(number);
}

function largestHoldingLabel(tokens) {
  if (!tokens.length) return "Unavailable";
  const largest = [...tokens].sort((a, b) => Number(b.valueUsd || 0) - Number(a.valueUsd || 0))[0];
  if (!largest || largest.valueUsd === null || largest.valueUsd === undefined) return "Unavailable";
  return `${largest.symbol || "TOKEN"} ${money(largest.valueUsd)}`;
}

function setSummary(title, detail) {
  summary.innerHTML = `<strong>${title}</strong><span>${detail}</span>`;
}

function renderVerdictBuckets(result) {
  const overallRisk = getOverallRisk(result);
  const topBuckets = [
    {
      label: "Overall Risk Analysis",
      state: overallRisk.state,
      value: overallRisk.value,
      detail: overallRisk.detail,
    },
    {
      label: "AI Risk Analysis",
      state: aiRiskState(result.aiAnalysis?.riskLevel),
      value: result.aiAnalysis?.riskLevel || "Unknown",
      detail: result.aiAnalysis?.decision || "No AI decision",
    },
  ];
  const buckets = [
    {
      label: "Identity",
      state: ["known", "named"].includes(result.owner?.status) ? "ok" : "warn",
      value: result.owner?.label || "Unknown",
      detail: result.owner?.source || "No identity source",
    },
    {
      label: "Wallet type",
      state: result.signals?.isContract ? "warn" : "ok",
      value: result.signals?.isContract ? "Contract" : "EOA wallet",
      detail: result.signals?.isContract ? "Smart contract address" : "Externally owned wallet",
    },
    {
      label: "Activity",
      state: Number(result.signals?.txCount || 0) > 0 ? "ok" : "warn",
      value: `${Number(result.signals?.txCount || 0).toLocaleString()} tx`,
      detail: `${Number(result.transactions?.length || 0)} recent transfers`,
    },
    {
      label: "Pricing",
      state: Number(result.coingecko?.pricedTokenCount || 0) > 0 ? "ok" : "warn",
      value: money(result.coingecko?.portfolioValueUsd || 0),
      detail: `${Number(result.coingecko?.pricedTokenCount || 0)} priced tokens`,
    },
    {
      label: "NFTs",
      state: Number(result.opensea?.nftCountShown || 0) > 0 ? "ok" : "warn",
      value: `${Number(result.opensea?.nftCountShown || 0)} shown`,
      detail: "OpenSea holdings sample",
    },
  ];

  summary.innerHTML = `
    <div class="risk-row risk-row-top">
      ${topBuckets.map(verdictCard).join("")}
    </div>
    <div class="risk-row risk-row-supporting">
      ${buckets.map(verdictCard).join("")}
    </div>
  `;
}

function verdictCard(bucket) {
  return `
    <div class="verdict ${bucket.state}">
      <span class="verdict-icon" aria-hidden="true">${verdictIcon(bucket.state)}</span>
      <div>
        <span>${bucket.label}</span>
        <strong>${bucket.value}</strong>
        <small>${bucket.detail}</small>
      </div>
    </div>
  `;
}

function getOverallRisk(result) {
  const aiLevel = (result.aiAnalysis?.riskLevel || "").toLowerCase();
  if (["low", "medium", "high"].includes(aiLevel)) {
    return {
      state: aiRiskState(aiLevel),
      value: aiLevel.toUpperCase(),
      detail: buildOverallRiskReason(result),
    };
  }

  if (result.signals?.isContract) {
    return { state: "warn", value: "REVIEW", detail: "Contract address needs manual review" };
  }
  if (!["known", "named"].includes(result.owner?.status)) {
    return { state: "warn", value: "UNKNOWN", detail: "No identity signal found" };
  }
  return { state: "ok", value: "LOW", detail: "No major risk signal found" };
}

function buildOverallRiskReason(result) {
  const aiSentence = firstSentence(result.aiAnalysis?.summary);
  if (aiSentence) return aiSentence;

  const reasons = [];
  if (result.signals?.isContract) reasons.push("contract address");
  if (["known", "named"].includes(result.owner?.status)) reasons.push(`${result.owner.label} identity signal`);
  if (!["known", "named"].includes(result.owner?.status)) reasons.push("unknown identity");
  if (Number(result.signals?.txCount || 0) > 1000) reasons.push(`${Number(result.signals.txCount).toLocaleString()} transactions`);
  if (Number(result.transactions?.length || 0) > 0) reasons.push(`${Number(result.transactions.length).toLocaleString()} recent transfers`);
  if (Number(result.coingecko?.pricedTokenCount || 0) === 0) reasons.push("no priced token matches");
  if (Number(result.opensea?.nftCountShown || 0) > 0) reasons.push(`${Number(result.opensea.nftCountShown).toLocaleString()} NFTs shown`);

  if (!reasons.length) return "Limited wallet evidence available, so manual review is recommended.";
  return `Risk is based on ${reasons.slice(0, 3).join(", ")}.`;
}

function firstSentence(text) {
  const clean = String(text || "").replace(/\s+/g, " ").trim();
  if (!clean) return "";
  const match = clean.match(/^(.{1,150}?[.!?])(\s|$)/);
  return match ? match[1] : `${clean.slice(0, 150)}${clean.length > 150 ? "..." : ""}`;
}

function aiRiskState(level) {
  const normalized = (level || "unknown").toLowerCase();
  if (normalized === "high") return "bad";
  if (normalized === "medium") return "warn";
  if (normalized === "low") return "ok";
  return "warn";
}

function verdictIcon(state) {
  if (state === "ok") return "✓";
  if (state === "bad") return "×";
  return "!";
}

function setLoading(isLoading) {
  document.body.classList.toggle("loading", isLoading);
  form.querySelector("button").disabled = isLoading;
  form.querySelector("button").textContent = isLoading ? "Analyzing..." : "Analyze";
}

async function analyze() {
  const address = addressInput.value.trim();
  if (!updateAddressStatus()) {
    sourceList.innerHTML = `<div class="empty">No backend lookup was attempted.</div>`;
    ownerPanel.innerHTML = `<div class="empty">Invalid address.</div>`;
    walletSignals.innerHTML = `<div class="empty">Invalid address.</div>`;
    ensIntel.innerHTML = `<div class="empty">Invalid address.</div>`;
    alchemyIntel.innerHTML = `<div class="empty">Invalid address.</div>`;
    coingeckoIntel.innerHTML = `<div class="empty">Invalid address.</div>`;
    openseaIntel.innerHTML = `<div class="empty">Invalid address.</div>`;
    aiAnalysis.innerHTML = `<div class="empty">Invalid address.</div>`;
    transactions.innerHTML = `<div class="empty">Invalid address.</div>`;
    if (lookupStatus) lookupStatus.textContent = "Enter 0x followed by 40 hexadecimal characters.";
    setSummary("Invalid address", "Fix the wallet address format before running a lookup.");
    return;
  }

  setLoading(true);
  setSummary("Analyzing", "Calling Flask /api/lookup.");
  sourceList.innerHTML = `<div class="empty">Gathering source statuses...</div>`;
  ownerPanel.innerHTML = `<div class="empty">Finding best available identity evidence...</div>`;
  walletSignals.innerHTML = `<div class="empty">Fetching RPC wallet signals...</div>`;
  ensIntel.innerHTML = `<div class="empty">Checking ENS reverse lookup...</div>`;
  alchemyIntel.innerHTML = `<div class="empty">Fetching Alchemy wallet enrichment if configured...</div>`;
  coingeckoIntel.innerHTML = `<div class="empty">Pricing Alchemy tokens with CoinGecko if configured...</div>`;
  openseaIntel.innerHTML = `<div class="empty">Fetching OpenSea NFT holdings if configured...</div>`;
  aiAnalysis.innerHTML = `<div class="empty">Running OpenAI analyst review if configured...</div>`;
  transactions.innerHTML = `<div class="empty">Loading decoded transactions...</div>`;

  try {
    renderLookup(await fetchLookup(address));
  } catch (error) {
    setSummary("Lookup failed", error.message);
    if (lookupStatus) lookupStatus.textContent = error.message;
  } finally {
    setLoading(false);
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  analyze();
});

addressInput.addEventListener("input", updateAddressStatus);
networkInput.addEventListener("change", () => {
  if (addressInput.value.trim()) analyze();
});

transactionFilters.addEventListener("click", (event) => {
  const button = event.target.closest("[data-filter]");
  if (!button) return;
  activeTransactionFilter = button.dataset.filter;
  transactionFilters.querySelectorAll(".filter").forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  drawTransactions();
});

sampleButtons.forEach((button) => {
  button.addEventListener("click", () => {
    addressInput.value = button.dataset.address;
    networkInput.value = button.dataset.network;
    updateAddressStatus();
    analyze();
  });
});

tabButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setActiveTab(button.dataset.tab);
  });
});

function setActiveTab(tabId) {
  tabButtons.forEach((button) => {
    const active = button.dataset.tab === tabId;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });

  tabPanels.forEach((panel) => {
    const active = panel.id === tabId;
    panel.classList.toggle("active", active);
    panel.hidden = !active;
  });
}
