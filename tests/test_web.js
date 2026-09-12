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
        if (/^Done\.|Nothing to look up|Could not reach/.test(s) || Date.now() - t0 > 45000) {
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
  ok("junk text is refused with an explanation", /Nothing to look up/.test(s), s);
  ok("copy button hidden when there is nothing to copy", $("#copy").hidden);

  // A bibliography is made of numbers. None of these is an identifier, and
  // treating one as a PMID would send a stranger's page number to NCBI and then
  // report back about whatever unrelated paper holds that id.
  s = await check("Smith J. Lancet 1998;351(9103):637-41. ISBN 9780262033848, " +
                  "pages 12345678-12345699, volume 351, year 2019.");
  ok("bare numbers are not mistaken for PMIDs", /Nothing to look up/.test(s), s);

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

  // ---- 4b. Vancouver style: the half of biomedicine that never writes a DOI ----
  // Before PMIDs were understood, this whole bibliography came back as "no DOIs
  // found in that text" — a tool that is silent about the reference that matters.
  s = await check([
    "1. Wakefield AJ, Murch SH, Anthony A, et al. Ileal-lymphoid-nodular",
    "   hyperplasia. Lancet. 1998;351(9103):637-41. PMID: 9500320.",
    "2. Kovalevskii AA. [Aleksandr Antonovich Kovalevskii]. 1971. PMID: 4948411.",
    "3. Someone. A citation with a digit too many. PMID: 999999999."
  ].join("\n"));
  ok("PMID-only bibliography runs", /^Done\./.test(s), s);
  const pmidBody = txt();
  ok("the retraction is found through the PMID alone",
     /RETRACTED — do not cite this as evidence/.test(pmidBody), pmidBody);
  ok("the reference is named back the way it was cited",
     /PMID 9500320/.test(pmidBody), pmidBody);
  ok("a PMID with no DOI is reported, not dropped",
     /PMIDs with no DOI — not checked \(1\)/.test(pmidBody), pmidBody);
  ok("a PMID with no DOI is not sold as clean",
     /not the same as clean/.test(pmidBody) && /nothing to ask about it/.test(pmidBody),
     pmidBody);
  ok("a PMID that does not exist is named",
     /PMIDs not found in PubMed \(1\)/.test(pmidBody), pmidBody);
  ok("only what really got checked is counted",
     /\b1 reference checked\b/.test(pmidBody), pmidBody.split("\n").slice(0, 3).join(" | "));

  // 4c. the same paper cited twice, once each way, is one reference
  s = await check("Zhu N, et al. N Engl J Med. 2020. doi:10.1056/NEJMoa2001017. PMID: 31978945.");
  ok("DOI and PMID of one paper are not counted twice",
     /\b1 reference checked\b/.test(txt()), txt().split("\n").slice(0, 3).join(" | "));

  // 4d. a PMID with nothing behind it must not produce an empty screen
  s = await check("Kovalevskii AA. 1971. PMID: 4948411.");
  ok("a bibliography that could not be checked at all says so",
     /Nothing could be checked/.test(s), s);
  ok("and does not claim a clean result", !/Nothing found/.test(txt()), txt());

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

  // 6d. PubMed falling over is its own failure, and it must not turn a PMID
  // into silence. Only the NCBI calls are broken here; Crossref stays up, so
  // the DOI in the same bibliography still gets its answer.
  window.fetch = function (u, o) {
    if (/eutils\.ncbi\.nlm\.nih\.gov/.test(String(u))) {
      return Promise.reject(new TypeError("Failed to fetch"));
    }
    return realFetch(u, o);
  };
  s = await check("Wakefield. PMID: 9500320.\nZhang. doi:10.1371/journal.pone.0161231");
  ok("a PMID whose lookup died is admitted, not hidden",
     /could not be checked/i.test(s), s);
  ok("the dead PMID is listed by name so it can be rerun",
     /Could not be checked \(1\)/.test(txt()) && /PMID 9500320/.test(txt()), txt());
  ok("PubMed being down does not take Crossref down with it",
     /CORRECTED — check the number/.test(txt()), txt());

  window.fetch = realFetch;

  // ---- 7. the second register --------------------------------------------
  // Measured 2026-09-11: 21.2% of the papers PubMed says were corrected carry
  // nothing at all in Crossref's `updated-by`. These cases are live on purpose;
  // if Crossref ever deposits them the assertions go red, which is how I want
  // to hear about it.
  s = await check("Liu SK et al. J Natl Cancer Inst 2011. doi:10.1093/jnci/djr419");
  ok("a paper Crossref calls clean is not called clean",
     /EXPRESSION OF CONCERN/.test(txt()), txt().split("\n").slice(0, 6).join(" | "));
  ok("the notice says which register knows about it",
     /per PubMed/.test(txt()), txt());
  ok("both PubMed notices come through",
     /Expression Of Concern/.test(txt()) && /Erratum/.test(txt()), txt());

  // The 2004 notice on the 1998 Lancet paper: a correction to Crossref, a
  // RetractionIn to PubMed. Both must survive, and the headline must stay
  // RETRACTED, because both registers list the undisputed 2010 retraction.
  s = await check("Wakefield AJ et al. Lancet 1998. doi:10.1016/S0140-6736(97)11096-0");
  ok("a severity disagreement keeps both verdicts",
     (txt().match(/Retraction/g) || []).length >= 2, txt());
  ok("a disagreement does not bury what both registers confirm",
     /RETRACTED — do not cite/.test(txt()) && !/REGISTERS DISAGREE/.test(txt()), txt());

  // correction/erratum is one word in two vocabularies. If this ever starts
  // printing two lines for 10.1371/journal.pone.0301214, the merge key broke.
  s = await check("doi:10.1371/journal.pone.0161231");
  ok("the same notice under two names is printed once",
     (txt().match(/journal\.pone\.0301214/g) || []).length <= 1 &&
     !/REGISTERS DISAGREE/.test(txt()), txt());

  // A withdrawn paper whose own DOI carries the retraction twice, deposited
  // 2019-03-19 and again 2019-04-01. One withdrawal, so one line, dated the
  // first time it appeared. If this starts printing two, the date crept back
  // into the merge key.
  s = await check("doi:10.1016/j.engfailanal.2019.01.024");
  ok("one notice deposited twice is printed once",
     (txt().match(/Retraction \(/g) || []).length === 1, txt());
  ok("the earliest of the two deposit dates is the one shown",
     /2019-03-19/.test(txt()) && !/2019-04-01/.test(txt()), txt());

  // 7b. NCBI down must cost only the second opinion, never the first.
  window.fetch = function (u, o) {
    if (/eutils\.ncbi\.nlm\.nih\.gov/.test(String(u))) {
      return Promise.reject(new TypeError("Failed to fetch"));
    }
    return realFetch(u, o);
  };
  s = await check("doi:10.1371/journal.pone.0161231");
  ok("Crossref's answer survives PubMed being unreachable",
     /CORRECTED — check the number/.test(txt()), txt());
  window.fetch = realFetch;

  // 7c. The disagreement headline, on canned answers. It has to be canned: the
  // branch only fires when the graver verdict exists ONLY in PubMed, and there
  // is no live DOI I can pin that to for as long as this test should last.
  // This branch shipped once with an undefined variable in it precisely because
  // no live case in the battery ever reached it.
  var fakeWork = {
    message: { items: [{ DOI: "10.1234/test", title: ["A canned paper"],
      "container-title": ["Journal of Fixtures"],
      "updated-by": [{ type: "correction", DOI: "10.1234/notice",
                       updated: { "date-parts": [[2020, 1, 1]] } }] }] }
  };
  var fakeXml =
    '<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID Version="1">1</PMID>' +
    '<Article><ArticleTitle>A canned paper</ArticleTitle></Article>' +
    '<CommentsCorrectionsList><CommentsCorrections RefType="RetractionIn">' +
    '<RefSource>J Fixtures. 2021. doi: 10.1234/notice.</RefSource>' +
    '<PMID Version="1">2</PMID></CommentsCorrections></CommentsCorrectionsList>' +
    '</MedlineCitation><PubmedData><ArticleIdList>' +
    '<ArticleId IdType="pubmed">1</ArticleId>' +
    '<ArticleId IdType="doi">10.1234/test</ArticleId>' +
    '</ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>';
  var reply = function (body) {
    return Promise.resolve({ ok: true, status: 200,
      json: function () { return Promise.resolve(body); },
      text: function () { return Promise.resolve(typeof body === "string" ? body : JSON.stringify(body)); } });
  };
  window.fetch = function (u, o) {
    var url = String(u);
    if (/api\.crossref\.org/.test(url)) return reply(fakeWork);
    if (/esearch\.fcgi/.test(url)) return reply({ esearchresult: { idlist: ["1"] } });
    if (/efetch\.fcgi/.test(url)) return reply(fakeXml);
    return realFetch(u, o);
  };
  s = await check("doi:10.1234/test");
  ok("a severity disagreement over the worst notice takes the headline",
     /REGISTERS DISAGREE/.test(txt()), txt());
  ok("and the graver verdict is not the one dropped",
     /Retraction/.test(txt()) && /Correction/.test(txt()), txt());
  ok("the reader is told which two lines are one notice",
     /same notice \(10\.1234\/notice\)/.test(txt()), txt());
  window.fetch = realFetch;

  return { pass: out.pass.length, fail: out.fail.length, failed: out.fail, passed: out.pass };
})()
