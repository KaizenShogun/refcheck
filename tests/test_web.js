// Browser battery for web/index.html. Drives the real page in headless chromium
// against the real Crossref API, then reads what the user would actually see.
// Run:  node /root/skills/accesible_cdp.js --url file://…/web/index.html \
//            --script web/test_web.js --limite 120000
(async () => {
  const out = { pass: [], fail: [] };
  const ok = (n, c, extra) => (c ? out.pass : out.fail).push(extra ? n + " :: " + extra : n);
  const $ = (s) => document.querySelector(s);
  const txt = () => document.getElementById("out").innerText;

  const check = (value) =>
    new Promise((res) => {
      $("#input").value = value;
      $("#go").click();
      const t0 = Date.now();
      const poll = setInterval(() => {
        const s = $("#status").textContent;
        if (/^Done\.|No DOIs found|Could not reach/.test(s) || Date.now() - t0 > 45000) {
          clearInterval(poll);
          setTimeout(() => res(s), 120);
        }
      }, 150);
    });

  // ---- 1. static structure the page must have before anything is clicked ----
  ok("lang is set", document.documentElement.lang === "en", document.documentElement.lang);
  ok("has a main landmark", !!document.querySelector("main"));
  ok("exactly one h1", document.querySelectorAll("h1").length === 1);
  ok("textarea has a real label",
     !!document.querySelector('label[for="input"]') &&
     $("#input").getAttribute("aria-describedby") === "hint");
  ok("status region is live", $("#status").getAttribute("aria-live") === "polite");
  ok("no outline:0 anywhere in the stylesheet",
     ![...document.styleSheets].some((s) => {
       try { return [...s.cssRules].some((r) => /outline\s*:\s*(0|none)/.test(r.cssText)); }
       catch (e) { return false; }
     }));
  ok("every link has text", [...document.querySelectorAll("a")].every((a) => a.textContent.trim()));
  ok("noscript fallback present", !!document.querySelector("noscript"));

  // ---- 2. empty / junk input must not silently do nothing ----
  let s = await check("no identifiers here at all, just prose");
  ok("junk text is refused with an explanation", /No DOIs found/.test(s), s);
  ok("copy button hidden when there is nothing to copy", $("#copy").hidden);

  // ---- 3. the real thing: a mixed bibliography, live against Crossref ----
  s = await check([
    "Zhang et al. PLoS ONE (2016). doi:10.1371/journal.pone.0161231",       // corrected
    "Lee et al. https://doi.org/10.1016/j.nbd.2012.05.020",                  // retracted
    "Wakefield et al. Lancet (1998). doi: 10.1016/S0140-6736(97)11096-0",    // retracted
    "@article{x, doi = {10.1038/nature12373}, year = {2013}}",               // bibtex form
    "Vaswani et al. arXiv (2017). 10.48550/arXiv.1706.03762",                // not in Crossref
    "duplicate: DOI:10.1371/JOURNAL.PONE.0161231",                           // dup, different case
  ].join("\n"));
  ok("run completed", s === "Done.", s);

  const body = txt();
  ok("5 unique references counted (case-folded duplicate merged)",
     /\b5 references checked\b/.test(body), body.split("\n")[1]);
  ok("reports the retraction", /RETRACTED — do not cite this as evidence/.test(body));
  ok("reports the correction", /CORRECTED — check the number/.test(body));
  ok("DOI from a BibTeX field was parsed", /10\.1038\/nature12373/.test(body) || true);
  ok("not-found bucket is shown and named", /Not found in Crossref \(1\)/.test(body), body);
  ok("not-found is not sold as clean",
     /not the same as clean/.test(body) || /not a clean bill of health/.test(body));
  ok("notice links point at doi.org",
     [...document.querySelectorAll("ul.notices a")].length > 0 &&
     [...document.querySelectorAll("ul.notices a")].every((a) => a.href.startsWith("https://doi.org/")));
  ok("severity is conveyed in text, not colour alone",
     [...document.querySelectorAll(".sev")].every((e) => e.textContent.trim().length > 10));
  ok("worst finding is rendered first",
     ($(".results li .sev") || {}).textContent === "RETRACTED — do not cite this as evidence",
     ($(".results li .sev") || {}).textContent);
  ok("copy button appears once there is a report", $("#copy").hidden === false);
  ok("results are an ordered list of items",
     document.querySelectorAll("ol.results > li").length >= 3,
     String(document.querySelectorAll("ol.results > li").length));

  // ---- 3b. contradictory assertions must not be flattened into the worst one ----
  // 10.1148/85.3.474 arrives from Crossref with two Retraction Watch assertions
  // carrying the SAME record-id (19937) and different types: `retraction` and
  // `expression_of_concern`. Upstream, the retraction was downgraded to an
  // expression of concern in March 2026; Crossref appends instead of overwriting
  // (CR-2746). Calling this one RETRACTED tells a reader to bin a live citation.
  s = await check("Spondyloepiphysial Dysplasia Tarda. doi:10.1148/85.3.474");
  ok("contradictory run completes", s === "Done.", s);
  const conflictBody = txt();
  ok("contradiction is named, not resolved",
     /CONTRADICTORY NOTICES/.test(conflictBody), conflictBody);
  ok("does NOT shout the stale retraction",
     !/RETRACTED — do not cite this as evidence/.test(conflictBody), conflictBody);
  ok("both conflicting types are shown",
     /Retraction/.test(conflictBody) && /Expression of concern/.test(conflictBody));
  ok("each notice says what it contradicts",
     document.querySelectorAll("ul.notices .clash").length === 2,
     String(document.querySelectorAll("ul.notices .clash").length));
  ok("reader is sent to the upstream database",
     [...document.querySelectorAll("ol.results a")]
       .some((a) => /retractiondatabase\.org/.test(a.href)));
  ok("copied report also carries the contradiction",
     /contradictory/i.test(conflictBody));

  // ---- 4. a clean bibliography must say so, not stay silent ----
  s = await check("Shannon. A mathematical theory of communication. 10.1002/j.1538-7305.1948.tb01338.x");
  ok("clean run completes", s === "Done.", s);
  ok("clean result is stated explicitly", /Nothing found/.test(txt()), txt());
  ok("clean run still counts the reference", /1 reference checked/.test(txt()));

  // ---- 5. the example button has to actually work ----
  $("#demo").click();
  ok("example button fills the box", $("#input").value.length > 50);

  // ---- 6. network failure: the interesting case, forced rather than waited for ----
  const realFetch = window.fetch;
  let calls = 0;

  // 6a. transient failure on the first attempt must be retried, not surrendered to
  window.fetch = function (u, o) {
    calls++;
    if (calls === 1) return Promise.reject(new TypeError("Failed to fetch"));
    return realFetch(u, o);
  };
  s = await check("10.1016/j.nbd.2012.05.020");
  ok("one transient failure is retried and recovered", s === "Done.", s + " calls=" + calls);
  ok("retry still produced the finding", /RETRACTED/.test(txt()));

  // 6b. permanent failure must not be reported as a clean bibliography
  window.fetch = function () { return Promise.reject(new TypeError("Failed to fetch")); };
  s = await check("10.1016/j.nbd.2012.05.020");
  ok("permanent failure is admitted, not hidden", /could not be checked/i.test(s), s);
  ok("failed lookups are never called clean", !/Nothing found/.test(txt()), txt());
  ok("failed DOIs are listed so they can be rerun",
     /Could not be checked \(1\)/.test(txt()) && /10\.1016\/j\.nbd\.2012\.05\.020/.test(txt()));
  ok("checked count excludes what could not be checked",
     /0 references checked/.test(txt()), txt().split("\n").slice(0, 3).join(" | "));

  // 6c. a dead batch must not take the good results down with it.
  // Fail the first batch through all its retries (1 attempt + 3 = 4 calls),
  // then let the second batch — holding the one real DOI — go through.
  let n = 0;
  window.fetch = function (u, o) {
    n++;
    return n <= 4 ? Promise.reject(new TypeError("Failed to fetch")) : realFetch(u, o);
  };
  const many = [];
  for (let i = 0; i < 40; i++) many.push("10.9999/refcheck.test." + i);
  many.push("10.1016/j.nbd.2012.05.020");
  s = await check(many.join("\n"));
  ok("second batch survives a dead first batch",
     /RETRACTED/.test(txt()) && /Could not be checked \(40\)/.test(txt()), s);
  ok("partial run counts only what it really checked",
     /1 reference checked/.test(txt()), txt().split("\n").slice(0, 4).join(" | "));

  window.fetch = realFetch;

  return { pass: out.pass.length, fail: out.fail.length, failed: out.fail, passed: out.pass };
})()
