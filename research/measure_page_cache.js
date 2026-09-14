// How much does the browser page's tab memory actually save, and what does it
// cost in storage? Measured, not assumed — the whole reason the cache exists is
// a number, so the number should be reproducible.
//
// Run (needs a headless chromium driver; this is the one I have):
//   node /root/skills/accesible_cdp.js \
//     --url https://kaizenshogun.github.io/refcheck/ \
//     --script research/measure_page_cache.js --limite 300000
//
// The network is stubbed with instant replies ON PURPOSE. What is being
// measured is the page's own pacing — one Crossref request a second, 350 ms
// between NCBI calls, which is what the registers ask for and where the whole
// wait lives. Hammering two free public APIs with a thousand real lookups to
// time my own cache would be rude and would measure their load, not my code.
(async () => {
  const $ = (s) => document.querySelector(s);
  const realFetch = window.fetch;
  const reply = (body) => Promise.resolve({
    ok: true, status: 200,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(typeof body === "string" ? body : JSON.stringify(body))
  });

  const N = 1000;
  const dois = [];
  for (let i = 0; i < N; i++) dois.push("10.7779/measure." + i);
  // One in forty carries a notice, which is about what a real screening run
  // turns up, so the stored entries are not all the cheap empty kind.
  const notice = (doi) => ({ DOI: doi, title: ["A measured paper number " + doi],
    "container-title": ["Journal of Measurement"],
    "updated-by": [{ type: "correction", label: "Correction", DOI: doi + "/c",
                     updated: { "date-parts": [[2021, 1, 1]] } }] });

  let requests = 0;
  window.fetch = function (u, o) {
    const url = String(u);
    requests++;
    if (/api\.crossref\.org/.test(url)) {
      // Answer about exactly the DOIs the filter asked for.
      const asked = decodeURIComponent(url).split("filter=")[1] || "";
      const items = asked.split(",")
        .map((p) => p.replace(/^doi:/, "").trim())
        .filter((d) => /^10\./.test(d))
        .map((d, i) => i % 40 === 0 ? notice(d)
                                    : { DOI: d, title: ["A measured paper"] });
      return reply({ message: { items: items } });
    }
    if (/esearch\.fcgi/.test(url)) return reply({ esearchresult: { idlist: [] } });
    if (/efetch\.fcgi/.test(url)) return reply("<PubmedArticleSet></PubmedArticleSet>");
    return reply({});
  };

  const runOnce = () => new Promise((res) => {
    const t0 = Date.now();
    requests = 0;
    $("#input").value = dois.join("\n");
    $("#go").click();
    const poll = setInterval(() => {
      if (/^Done\.|Nothing to look up/.test($("#status").textContent)) {
        clearInterval(poll);
        setTimeout(() => res({ ms: Date.now() - t0, requests: requests }), 150);
      }
    }, 100);
  });

  try { sessionStorage.clear(); } catch (e) {}
  const cold = await runOnce();
  const stored = (sessionStorage.getItem("refcheck.checked.v2") || "").length;
  const warm = await runOnce();
  const summaryCold = cold.ms, summaryWarm = warm.ms;

  // And the promise that matters more than the speed: nothing survives the tab.
  let leaks = [];
  for (let i = 0; i < localStorage.length; i++) leaks.push(localStorage.key(i));

  window.fetch = realFetch;
  return {
    references: N,
    cold_ms: summaryCold, cold_requests: cold.requests,
    warm_ms: summaryWarm, warm_requests: warm.requests,
    saved_ms: summaryCold - summaryWarm,
    stored_bytes: stored,
    stored_bytes_per_reference: Math.round(stored / N),
    localStorage_keys: leaks,
    report_says_it: /already checked in this tab/.test(
      document.getElementById("out").innerText)
  };
})();
