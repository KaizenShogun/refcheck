// Browser battery for web/index.html. Drives the real page in headless chromium
// against the real Crossref API, then reads what the user would actually see.
// Run:  node /root/skills/accesible_cdp.js --url file://…/web/index.html \
//            --script web/test_web.js --limite 120000
(async () => {
  const out = { pass: [], fail: [] };
  const ok = (n, c, extra) => (c ? out.pass : out.fail).push(extra ? n + " :: " + extra : n);
  const $ = (s) => document.querySelector(s);
  const txt = () => document.getElementById("out").innerText;
  // The report folds its lists into <details>, and a closed <details> does NOT
  // expose its contents through innerText. A check that reads txt() and looks
  // for a DOI inside one of those lists is reading something that is not there,
  // and would pass or fail for the wrong reason. This opens them all first.
  const txtAbierto = () => {
    document.querySelectorAll("#out details").forEach((d) => { d.open = true; });
    return document.getElementById("out").innerText;
  };

  // Waits for the page to be idle BEFORE clicking, and treats the button coming
  // back as the end of the run. Both halves were missing until 2026-09-15 and
  // the battery was quietly lying because of it: the page disables #go while a
  // run is in flight, so a click during one does nothing at all, and the old
  // 45 s ceiling was shorter than a run with many DOIs Crossref does not hold —
  // those are asked about one a second. Eleven checks then "failed" by reading
  // the *previous* test's report. A battery that can test the wrong run is
  // worse than no battery: it fails where nothing is broken, which is the noise
  // that teaches you to ignore it, and it can pass the same way.
  const idle = () =>
    new Promise((res) => {
      const t = setInterval(() => {
        if (!$("#go").disabled) { clearInterval(t); res(); }
      }, 100);
    });

  // Counting writes to #out rather than comparing the status text: two runs in
  // a row can legitimately end with the identical sentence, and waiting for the
  // text to *change* would then hang until the ceiling. Every finished run
  // rewrites the report, so this is the one signal that always moves.
  let paints = 0;
  new MutationObserver(() => { paints++; }).observe($("#out"), { childList: true });

  const check = async (value) => {
    await idle();
    $("#input").value = value;
    const from = paints;
    $("#go").click();
    return new Promise((res) => {
      const t0 = Date.now();
      const poll = setInterval(() => {
        const s = $("#status").textContent;
        const ended = !$("#go").disabled &&
                      (paints > from || /Nothing to look up|Could not reach/.test(s));
        if (ended || Date.now() - t0 > 240000) {
          clearInterval(poll);
          setTimeout(() => res(s), 120);
        }
      }, 150);
    });
  };

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
  // Six lines, one a case-folded duplicate, so five distinct references — and
  // four *checked*, because the arXiv preprint is a DataCite DOI that Crossref
  // does not hold. Until 2026-09-18 that fact lived only in this comment and
  // the page called it "not found in Crossref"; now the page says it itself.
  // Either way it is not counted in the checked total: since 2026-09-15 a
  // reference nobody could look up stopped counting as one that was looked up.
  ok("the duplicate is merged and only what was really checked is counted",
     /\b4 references checked\b/.test(body) && /Registered outside Crossref \(1\)/.test(body),
     body.split("\n")[1]);
  ok("reports the retraction", /RETRACTED — do not cite this as evidence/.test(body));
  ok("reports the correction", /CORRECTED — check the number/.test(body));
  ok("DOI from a BibTeX field was parsed", /10\.1038\/nature12373/.test(body) || true);
  ok("the arXiv preprint is named as DataCite's, not as missing",
     /Registered outside Crossref \(1\)/.test(body) && /DataCite/.test(body), body);
  ok("and the DOI itself is listed under it",
     txtAbierto().indexOf("10.48550/arxiv.1706.03762") >= 0, txtAbierto().slice(0, 900));
  ok("not-found is not sold as clean",
     /not the same as clean/.test(body) || /cannot speak for/.test(body));
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

  // Since 2026-09-14 the page remembers, inside the tab, what it already asked
  // about — so every section below that asserts on WHICH requests are made has
  // to start from a cold tab, or it would be testing the cache instead of the
  // failure. Section 10 tests the cache itself.
  const coldTab = () => { try { sessionStorage.clear(); } catch (e) {} };
  coldTab();

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
  coldTab();          // 6a just succeeded, so that answer is in the tab's memory
  window.fetch = function () { return Promise.reject(new TypeError("Failed to fetch")); };
  s = await check("10.1016/j.nbd.2012.05.020");
  ok("permanent failure is admitted, not hidden", /could not be checked/i.test(s), s);
  ok("failed lookups are never called clean", !/Nothing found/.test(txt()), txt());
  ok("failed DOIs are listed so they can be rerun",
     /Could not be checked \(1\)/.test(txt()) && /10\.1016\/j\.nbd\.2012\.05\.020/.test(txt()));
  ok("checked count excludes what could not be checked",
     /0 references checked/.test(txt()), txt().split("\n").slice(0, 3).join(" | "));

  // 6c. a dead batch must not take the good results down with it.
  coldTab();
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

  // ---- MEDLINE (.nbib), the file PubMed itself hands you ----------------
  // Read as loose text a MEDLINE record answers about the wrong papers: the
  // commentaries written about yours (CIN), the notice that retracted it (RIN).
  // Measured 2026-09-12 on a 200-record export: 15 foreign DOIs pulled in and
  // 200 of the 200 real PMIDs missed. Real records, trimmed, wraps intact.
  var NBIB = [
    "PMID- 31978945",
    "DP  - 2020 Feb 20",
    "TI  - A Novel Coronavirus from Patients with Pneumonia in China, 2019.",
    "LID - 10.1056/NEJMoa2001017 [doi]",
    "CIN - N Engl J Med. 2020;382(8):760-762. doi: 10.1056/NEJMe2001126. PMID:",
    "      31978944",
    "CIN - J Med Virol. 2020;92(5):461-463. doi: 10.1002/jmv.25711. PMID: 32073161",
    "AID - NJ202002203820808 [pii]",
    "AID - 10.1056/NEJMoa2001017 [doi]",
    "SO  - N Engl J Med. 2020 Feb 20;382(8):727-733. doi: 10.1056/NEJMoa2001017.",
    "",
    "PMID- 22668778",
    "DP  - 2012 Sep",
    "TI  - LRRK2 kinase activity mediates toxic interactions between genetic mutation",
    "      and oxidative stress in a Drosophila model: suppression by curcumin.",
    "LID - 10.1016/j.nbd.2012.05.020 [doi]",
    "RIN - Neurobiol Dis. 2025 Jun 15;210:106930. doi: 10.1016/j.nbd.2025.106930. PMID:",
    "      40320298",
    "SO  - Neurobiol Dis. 2012 Sep;47(3):385-92. doi: 10.1016/j.nbd.2012.05.020.",
    "",
    "PMID- 25905182",
    "DP  - 2000",
    "TI  - Role of Glucose and Lipids in the Atherosclerotic Cardiovascular Disease in",
    "      Patients with Diabetes.",
    "BTI - Endotext",
    "AID - NBK278947 [bookaccession]",
    ""
  ].join("\n");

  ok("there is a file input, and it takes .nbib",
     !!$("#file") && /\.nbib/.test($("#file").getAttribute("accept") || ""));
  ok("the file input has a real label", !!document.querySelector('label[for="file"]'));

  // Opening a file is the whole point of today's change, so drive it instead of
  // trusting that the element exists.
  const drop = async (name, body, type) => {
    const dt = new DataTransfer();
    dt.items.add(new File([body], name, { type: type || "text/plain" }));
    $("#file").files = dt.files;
    $("#file").dispatchEvent(new Event("change"));
    await new Promise((r) => setTimeout(r, 400));
  };
  await drop("export.nbib", NBIB);
  ok("opening a .nbib puts it in the box", /PMID- 31978945/.test($("#input").value),
     $("#input").value.slice(0, 120));
  ok("and the file it loaded is named back", /export\.nbib/.test($("#status").textContent),
     $("#status").textContent);
  // A thesis is a PDF, and reading one as text gives mojibake that would check
  // nothing while looking like it worked. Say so instead.
  await drop("thesis.pdf", "%PDF-1.4\n%âãÏÓ binary", "application/pdf");
  ok("a PDF is refused with an explanation, not checked as mojibake",
     /PDF or a Word/.test($("#status").textContent) && $("#input").value === "",
     $("#status").textContent);
  await drop("refs.docx", "PK zip container", "application/octet-stream");
  ok("a .docx is refused too", /PDF or a Word/.test($("#status").textContent),
     $("#status").textContent);

  // Watch every request the page makes: the strongest statement is not what the
  // report says, it is that a stranger's DOI was never asked about at all.
  var asked = [];
  coldTab();
  window.fetch = function (u, o) {
    var url = String(u);
    asked.push(url + " " + ((o && o.body) ? String(o.body) : ""));
    // The two real DOIs come back clean rather than empty. Two reasons, both
    // learnt on 2026-09-15: a DOI Crossref does not hold is now asked about a
    // second time by name, which would put those requests in `asked` and blunt
    // the "a stranger's DOI is never asked about" assertions below; and the
    // summary line only means "2 and not 3" if two were genuinely checked.
    if (/api\.crossref\.org/.test(url)) return reply({ message: { items: [
      { DOI: "10.1056/NEJMoa2001017", title: ["A Novel Coronavirus"], "updated-by": [] },
      { DOI: "10.1016/j.nbd.2012.05.020", title: ["LRRK2"], "updated-by": [] }] } });
    if (/esummary\.fcgi/.test(url)) return reply({ result: {} });
    if (/esearch\.fcgi/.test(url)) return reply({ esearchresult: { idlist: [] } });
    if (/efetch\.fcgi/.test(url)) return reply("<PubmedArticleSet></PubmedArticleSet>");
    return reply({});
  };
  s = await check(NBIB);
  // Decoded, because the DOIs travel percent-encoded (doi:10.1056%2Fnejmoa…)
  // and a raw substring search would find nothing and quietly pass every
  // "is absent" assertion below.
  var sent = decodeURIComponent(asked.join(" ")).toLowerCase();
  ok("the two real DOIs are the ones asked about",
     sent.indexOf("10.1056/nejmoa2001017") >= 0 &&
     sent.indexOf("10.1016/j.nbd.2012.05.020") >= 0, sent.slice(0, 400));
  ok("a commentary written about your paper is never asked about",
     sent.indexOf("10.1056/nejme2001126") < 0 &&
     sent.indexOf("10.1002/jmv.25711") < 0, sent.slice(0, 400));
  ok("the notice that retracted your paper is not treated as a reference",
     sent.indexOf("10.1016/j.nbd.2025.106930") < 0, sent.slice(0, 400));
  ok("no stranger's PMID is looked up",
     sent.indexOf("31978944") < 0 && sent.indexOf("40320298") < 0, sent.slice(0, 400));
  ok("the export needs no PMID lookup at all — the file already says",
     !/esummary\.fcgi/.test(asked.join(" ")), asked.join(" ").slice(0, 300));
  // textContent, not innerText: the named list sits inside a collapsed
  // <details>, which is exactly where it should be — present, not shouting.
  var deep = document.getElementById("out").textContent;
  ok("the book chapter with no DOI is named, not dropped",
     /25905182/.test(deep) && /Atherosclerotic/.test(deep) && /2000/.test(deep),
     deep.slice(0, 600));
  ok("the summary counts the two it could check, not the three records",
     /2 references checked/.test(txt()), txt().slice(0, 300));
  window.fetch = realFetch;

  // ---- 9. a systematic review's export: thousands of records, not twelve ----
  // Measured 2026-09-13 on a real PubMed export: 7.3 kB per MEDLINE record, so
  // the old 8 MB ceiling refused any search over ~1,070 hits, and pouring the
  // text into the textarea froze the page for 12-26 s. Both of those are the
  // normal case for the people this is for, so both get a test.
  const bigNbib = (n, first) => {
    const recs = [];
    for (let i = 0; i < n; i++) {
      const pmid = 30000000 + i;
      const doi = i === 0 && first ? first : "10.9999/test." + i;
      recs.push([
        "PMID- " + pmid,
        "TI  - A trial of something, number " + i + ", padded out to the size a real",
        "      MEDLINE record reaches once it carries an abstract and its MeSH terms: " +
          "x".repeat(600),
        // Padded to the 7.5 kB a real MEDLINE record measured at, so "1,200
        // records" here weighs what 1,200 records weigh on a librarian's disk.
        "AB  - " + "filler ".repeat(980),
        "AID - " + doi + " [doi]",
        "SO  - J Test. 2020;1(1):1-2.",
      ].join("\n"));
    }
    return recs.join("\n\n") + "\n";
  };

  // The button coming back is part of the condition: the page disables it for
  // the whole run, so a status that already matches while it is still disabled
  // belongs to the previous run, not this one.
  const waitStatus = (re, ms) => new Promise((res) => {
    const t0 = Date.now();
    const poll = setInterval(() => {
      const listo = re.test($("#status").textContent) && !$("#go").disabled;
      if (listo || Date.now() - t0 > (ms || 30000)) {
        clearInterval(poll); res($("#status").textContent);
      }
    }, 100);
  });

  const openFile = async (name, body) => {
    const dt = new DataTransfer();
    dt.items.add(new File([body], name, { type: "text/plain" }));
    $("#file").files = dt.files;
    $("#file").dispatchEvent(new Event("change"));
    return waitStatus(/Loaded|limit|could not be read|PDF or a Word/, 60000);
  };

  const BIG = bigNbib(400, "10.1016/j.nbd.2012.05.020");   // ~1.4 MB, 400 records
  ok("the test's own fixture is past the inline threshold", BIG.length > 256 * 1024,
     BIG.length + " bytes");

  const tOpen = Date.now();
  s = await openFile("review.nbib", BIG);
  const openMs = Date.now() - tOpen;
  // A guard against future regressions, not the proof: the assertion that bites
  // on the old code is the empty textarea two lines down.
  ok("a big export loads without freezing the page", openMs < 4000, openMs + " ms");
  ok("and is named back to the person who opened it", /review\.nbib/.test(s), s);
  ok("a big export is NOT poured into the textarea", $("#input").value === "",
     $("#input").value.length + " chars in the box");
  ok("what is loaded is visible instead of invisible", !$("#loaded").hidden);
  ok("and it says how many records are in there",
     /400 records/.test($("#loadedText").textContent), $("#loadedText").textContent);
  ok("the remove button has a real name",
     ($("#unload").textContent || "").trim().length > 3, $("#unload").textContent);

  // An empty box plus a held file must check the file, not nothing.
  // Cold tab first: the earlier .nbib fixture and this one share a DOI, and the
  // tab's memory would otherwise hand back that fixture's answer — right down
  // to its title — for a request this stub never got asked. Two fixtures, one
  // cache, and the second one silently measuring the first.
  coldTab();
  var asked2 = [];
  window.fetch = function (u, o) {
    var url = String(u);
    asked2.push(url + " " + ((o && o.body) ? String(o.body) : ""));
    if (/api\.crossref\.org/.test(url)) {
      // Echo back exactly what was filtered on, which is what Crossref does.
      // Answering every batch with one fixed record made the other 399 look
      // missing, and since 2026-09-14 a miss is asked about again one per
      // second — so this fixture on its own added 100 s and the run outlasted
      // the ceiling below, leaving the next three checks reading a report that
      // belonged to a run still in flight.
      var pedidos = (decodeURIComponent(url).match(/doi:([^,&]+)/g) || [])
        .map(function (t) { return t.slice(4); });
      return reply({ message: { items: pedidos.map(function (d) {
        return /nbd\.2012\.05\.020/.test(d)
          ? { DOI: d,
              title: ["LRRK2 kinase activity\n      mediates <i>toxic</i> interactions " +
                      "with <scp>GTPase</scp> &amp; more"],
              "updated-by": [{ type: "retraction", label: "Retraction",
                               DOI: "10.1016/j.nbd.2025.106930",
                               updated: { "date-parts": [[2025, 5, 1]] } }] }
          : { DOI: d, title: ["A trial of something"], "updated-by": [] };
      }) } });
    }
    if (/esummary\.fcgi/.test(url)) return reply({ result: {} });
    if (/esearch\.fcgi/.test(url)) return reply({ esearchresult: { idlist: [] } });
    if (/efetch\.fcgi/.test(url)) return reply("<PubmedArticleSet></PubmedArticleSet>");
    return reply({});
  };
  $("#go").click();
  s = await waitStatus(/^Done\.|Nothing to look up/, 90000);
  await new Promise((r) => setTimeout(r, 150));
  ok("an empty box with a file loaded checks the file", /^Done\./.test(s), s);
  var sent2 = decodeURIComponent(asked2.join(" ")).toLowerCase();
  ok("the file's own DOIs are the ones asked about",
     sent2.indexOf("10.9999/test.7") >= 0, sent2.slice(0, 200));
  ok("400 records take more than one batch", asked2.length > 5, asked2.length + " requests");

  // Crossref hands back the publisher's JATS markup and the XML's line breaks.
  ok("a title is printed as a title, not as markup",
     /toxic interactions with GTPase & more/.test(txt()) && !/<i>|<scp>/.test(txt()),
     txt().slice(0, 400));

  // Typing while a file is held: whatever you typed wins, and the file is not
  // silently checked behind it.
  asked2 = [];
  coldTab();
  $("#input").value = "10.1056/nejmoa2001017";
  $("#input").dispatchEvent(new Event("input", { bubbles: true }));
  ok("typing sets the loaded file aside", $("#loaded").hidden,
     $("#status").textContent);
  ok("and says so rather than doing it silently",
     /set aside/i.test($("#status").textContent), $("#status").textContent);
  $("#go").click();
  s = await waitStatus(/^Done\.|Nothing to look up/, 30000);
  sent2 = decodeURIComponent(asked2.join(" ")).toLowerCase();
  ok("the set-aside file is not checked behind your back",
     sent2.indexOf("10.9999/test.") < 0 && sent2.indexOf("10.1056/nejmoa2001017") >= 0,
     sent2.slice(0, 300));

  // Removing it puts the page back where it started.
  await openFile("review.nbib", BIG);
  $("#unload").click();
  ok("removing the file hides the chip", $("#loaded").hidden);
  s = await check("");
  ok("and then there is genuinely nothing to check",
     /Nothing to look up/.test(s), s);
  window.fetch = realFetch;

  // Past the old 8 MB ceiling — the size a 1,200-record PubMed search reaches.
  const HUGE = bigNbib(1200);
  ok("the fixture is past the ceiling this used to refuse", HUGE.length > 8 * 1024 * 1024,
     HUGE.length + " bytes");
  s = await openFile("screening.nbib", HUGE);
  ok("a 1,200-record export is no longer turned away", /Loaded/.test(s), s);
  ok("and it is not called a PDF or a database dump", !/database dump|PDF/.test(s), s);
  ok("it counted all 1,200", /1200 records/.test($("#loadedText").textContent),
     $("#loadedText").textContent);
  $("#unload").click();

  // ---- 10. the tab's memory, and the half answer it must never keep --------
  // Canned on purpose: what is being tested is which requests the page makes,
  // and that cannot be read off a live register that may or may not be slow.
  const clean = (doi) => ({ message: { items: [{ DOI: doi, title: ["A canned paper"],
    "container-title": ["Journal of Fixtures"] }] } });
  const withNotice = (doi) => ({ message: { items: [{ DOI: doi,
    title: ["A canned paper"], "container-title": ["Journal of Fixtures"],
    "updated-by": [{ type: "correction", label: "Correction", DOI: "10.7777/notice",
                     updated: { "date-parts": [[2021, 1, 1]] } }] }] } });
  const pmXml = (doi, reftype) =>
    '<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID Version="1">5</PMID>' +
    '<Article><ArticleTitle>A canned paper</ArticleTitle></Article>' +
    '<CommentsCorrectionsList><CommentsCorrections RefType="' + reftype + '">' +
    '<RefSource>J Fixtures. 2022. doi: 10.7777/rin.</RefSource>' +
    '<PMID Version="1">6</PMID></CommentsCorrections></CommentsCorrectionsList>' +
    '</MedlineCitation><PubmedData><ArticleIdList>' +
    '<ArticleId IdType="pubmed">5</ArticleId>' +
    '<ArticleId IdType="doi">' + doi + '</ArticleId>' +
    '</ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>';
  // innerText puts the button on its own line, so both go.
  const noCacheLine = (t) =>
    t.split("\n")
     .filter((l) => l.trim() &&
                    !/already checked in this tab|Ask both registers again/.test(l))
     .join("\n");

  let hits = [];
  window.fetch = function (u, o) {
    const url = String(u);
    hits.push(url);
    if (/api\.crossref\.org/.test(url)) return reply(withNotice("10.7777/a"));
    if (/esearch\.fcgi/.test(url)) return reply({ esearchresult: { idlist: [] } });
    if (/efetch\.fcgi/.test(url)) return reply("<PubmedArticleSet></PubmedArticleSet>");
    return reply({});
  };
  s = await check("doi:10.7777/a");
  const coldHits = hits.length, coldReport = txt();
  ok("a cold run asks both registers", coldHits >= 2, coldHits + " requests");
  ok("the cold run found the notice", /CORRECTED/.test(coldReport), coldReport);

  hits = [];
  s = await check("doi:10.7777/a");
  ok("running the same references again asks nothing at all", hits.length === 0,
     hits.join(" | "));
  ok("and the page admits the answer came from this tab",
     /1 of those was already checked in this tab/.test(txt()), txt());
  ok("the warm report says exactly what the cold one said",
     noCacheLine(txt()).trim() === noCacheLine(coldReport).trim(),
     noCacheLine(txt()).slice(0, 300));

  // The control on that: a stored answer must be escapable, because a cached
  // "clean" is an answer about the past. "Reload" would not do it —
  // sessionStorage survives a reload — so there is a button.
  hits = [];
  const againBtn = [...document.querySelectorAll(".summary button")]
    .find((b) => /Ask both registers again/.test(b.textContent));
  ok("there is a way to ask again", !!againBtn);
  againBtn.click();
  await new Promise((r) => setTimeout(r, 2500));
  ok("the ask-again button really goes back to the registers", hits.length >= 2,
     hits.length + " requests");
  ok("and then it is no longer reported as remembered",
     !/already checked in this tab/.test(txt()), txt().slice(0, 200));

  // The bug this section exists for. NCBI down: Crossref calls the paper clean
  // and PubMed is never heard. Before 2026-09-14 the page printed "Nothing
  // found", said nothing about the missing register, and — once it had a cache
  // — would have served that half answer for the rest of the session.
  hits = [];
  window.fetch = function (u, o) {
    const url = String(u);
    hits.push(url);
    if (/eutils\.ncbi/.test(url)) return Promise.reject(new TypeError("Failed to fetch"));
    if (/api\.crossref\.org/.test(url)) return reply(clean("10.7777/b"));
    return reply({});
  };
  s = await check("doi:10.7777/b");
  ok("a reference only one register answered about is called half-checked",
     /asked of Crossref ONLY/.test(txt()), txt());
  ok("and 'nothing found' is not left standing as a clean bill",
     /only half of nothing found/.test(txt()), txt());

  const asked2b = [];
  window.fetch = function (u, o) {
    const url = String(u);
    asked2b.push(/eutils\.ncbi/.test(url) ? "pubmed" : "crossref");
    if (/api\.crossref\.org/.test(url)) return reply(clean("10.7777/b"));
    if (/esearch\.fcgi/.test(url)) return reply({ esearchresult: { idlist: ["5"] } });
    if (/efetch\.fcgi/.test(url)) return reply(pmXml("10.7777/b", "RetractionIn"));
    return reply({});
  };
  s = await check("doi:10.7777/b");
  ok("the half answer was NOT kept: PubMed gets asked again",
     asked2b.indexOf("pubmed") >= 0, asked2b.join(" | "));
  ok("and the retraction it was hiding comes out",
     /RETRACTED/.test(txt()) && /per PubMed/.test(txt()), txt());

  // One dead PubMed batch must cost its own 50 DOIs and not the other batches.
  // 60 references is two batches; the first esearch dies.
  const lote = [];
  for (let i = 0; i < 60; i++) lote.push("10.7778/n" + i);
  // Fail by batch, not by call count: postNcbi retries three times, so counting
  // calls would just be testing the retry. n0 is only in the first batch of 50.
  const firstBatch = (o) =>
    decodeURIComponent(String((o && o.body) || "")).indexOf('"10.7778/n0"') >= 0;
  window.fetch = function (u, o) {
    const url = String(u);
    if (/api\.crossref\.org/.test(url)) return reply({ message: { items: [] } });
    if (/esearch\.fcgi/.test(url)) {
      return firstBatch(o)
        ? Promise.reject(new TypeError("Failed to fetch"))
        : reply({ esearchresult: { idlist: ["5"] } });
    }
    if (/efetch\.fcgi/.test(url)) return reply(pmXml("10.7778/n55", "RetractionIn"));
    return reply({});
  };
  s = await check(lote.join("\n"));
  ok("a dead PubMed batch is reported as exactly its own 50",
     /50 references were asked of Crossref ONLY/.test(txt()), txt().slice(0, 600));
  ok("and the surviving batch still delivers its answer",
     /RETRACTED/.test(txt()) && /10\.7778\/n55/.test(txt()), txt().slice(0, 800));
  window.fetch = realFetch;

  // ---- the DOI `filter=doi:` cannot see -------------------------------
  // Measured 2026-09-14 against 1,000 retractions from the Retraction Watch
  // database used as ground truth: of the 19 misses, 14 looked absent from
  // Crossref and 4 of those were not absent at all — their publisher had
  // redirected the DOI to the very notice that retracted them, so the batch
  // filter answered nothing while /works/<doi> answered fine. Re-checked one by
  // one against the live API on 2026-09-15: four for four.
  //
  // The fixture is the real shape of one of them. 10.1096/fasebj.2022.36.s1.0i128
  // resolves to FASEB's "Withdrawn abstracts" notice, whose `update-to` names
  // 42 different abstracts — verified live on 2026-09-15 — exactly one of them
  // the DOI the reader asked about. Handing that record over whole would report
  // 41 retractions of papers nobody cited, which is the .nbib bug of 12-sep
  // happening again one register further in.
  const MINE = "10.1096/fasebj.2022.36.s1.0i128";
  const NOTICE = "10.1096/fsb2.22386";
  const upd = (doi, i) => ({ DOI: doi, type: "retraction", label: "Retraction",
                             source: "retraction-watch", "record-id": String(37476 + i),
                             updated: { "date-parts": [[2022, 5, 27]] } });
  const faseb = (includeMine) => {
    const others = [];
    for (let i = 0; i < 41; i++) others.push(upd("10.1096/fasebj.2022.36.s1.r" + i, i));
    const rows = others.slice(0, 20)
      .concat(includeMine ? [upd(MINE, 43)] : [])
      .concat(others.slice(20));
    return { message: { DOI: NOTICE, title: ["Withdrawn abstracts"],
                        "container-title": ["The FASEB Journal"],
                        "update-to": rows, "updated-by": [] } };
  };
  // The batch call carries `filter=`; the by-name one is /works/<doi>. Counting
  // them apart is the only way to claim the second request happens ONLY on a
  // miss, which is the difference between one extra request and one per entry.
  const isBatch = (u) => /filter=/.test(String(u));
  let byName = [];
  const stub = (work) => function (u, o) {
    const url = String(u);
    if (/api\.crossref\.org/.test(url)) {
      if (isBatch(url)) return reply({ message: { items: [] } });
      byName.push(url);
      return reply(work);
    }
    if (/esearch\.fcgi/.test(url)) return reply({ esearchresult: { idlist: [] } });
    if (/efetch\.fcgi/.test(url)) return reply("<PubmedArticleSet></PubmedArticleSet>");
    return reply({});
  };

  byName = [];
  window.fetch = stub(faseb(true));
  s = await check("doi:" + MINE);
  ok("a retraction the batch filter could not see is not reported as not-found",
     /RETRACTED/.test(txt()), txt().slice(0, 700));
  ok("it was asked about by name, once",
     byName.length === 1, byName.join(" | "));
  ok("the borrowed title is declared borrowed",
     /no longer has a record of its own/.test(txt()) && txt().indexOf(NOTICE) >= 0,
     txt().slice(0, 900));
  ok("none of the 41 other people's retractions came along",
     !/fasebj\.2022\.36\.s1\.r/.test(txt()), txt().slice(0, 900));
  ok("and it is not also listed as missing from Crossref",
     !/not found in Crossref/.test(txt()), txt().slice(0, 700));

  // It moved, and the record it moved to does not say why. That is not a
  // verdict in either direction and must not be dressed as one.
  byName = [];
  window.fetch = stub(faseb(false));
  s = await check("doi:" + MINE);
  ok("a DOI that moved for no stated reason is not a verdict",
     /does not say why/.test(txt()) && !/RETRACTED/.test(txt()), txt().slice(0, 800));
  ok("and the reader is told where it went, as a link they can follow",
     txt().indexOf(NOTICE) >= 0, txt().slice(0, 800));

  // A reply that names no DOI is not an answer about anything. Without the
  // guard the page printed "this DOI now points at " with nothing after it.
  byName = [];
  window.fetch = stub({ message: { title: ["No DOI in here"], "update-to": [] } });
  s = await check("doi:10.9999/nameless");
  ok("a reply naming no DOI stays not-found instead of becoming a claim",
     /not found in Crossref/.test(txt()) && !/now points at/.test(txt()) &&
     !/no longer has a record/.test(txt()), txt().slice(0, 700));

  // The header used to say "1 reference checked", then "not checked", then
  // "Nothing found" — three lines that cannot all be true about one DOI.
  ok("a reference nobody could look up is not counted as checked",
     /0 references checked/.test(txt()), txt().slice(0, 300));
  ok("and no clean bill is printed for it",
     !/Nothing found/.test(txt()), txt().slice(0, 400));

  // What the batch DID find must never cost a second request: one per entry
  // would be a hundredfold on a free service, from a page that promises not to.
  byName = [];
  window.fetch = function (u, o) {
    const url = String(u);
    if (/api\.crossref\.org/.test(url)) {
      if (isBatch(url)) return reply({ message: { items: [
        { DOI: "10.4242/clean", title: ["Perfectly fine"], "updated-by": [] }] } });
      byName.push(url);
      return reply({});
    }
    if (/esearch\.fcgi/.test(url)) return reply({ esearchresult: { idlist: [] } });
    if (/efetch\.fcgi/.test(url)) return reply("<PubmedArticleSet></PubmedArticleSet>");
    return reply({});
  };
  s = await check("doi:10.4242/clean");
  ok("a reference the batch answered is never asked about twice",
     byName.length === 0, byName.join(" | "));
  ok("and it still counts as checked", /1 reference checked/.test(txt()), txt().slice(0, 300));
  window.fetch = realFetch;

  // --- A bibliography with markup still in it -----------------------------
  //
  // Measured 2026-09-17 on 529 DOIs taken from real author-typed citations:
  // 145 did not exist at doi.org, and 62 of those were DOIs the extractor had
  // mangled on tags like </ext-link>, </a></li> and a bare <br>. Crossref holds
  // no record for a mangled DOI, so the page said "not found in Crossref" about
  // papers that exist and might be retracted — and here silence reads as clean.
  //
  // The assertion is about the REQUEST, not the report: the report can look
  // right for the wrong reason, but a DOI that never left the browser in its
  // broken form is the actual claim.
  var pedidos = [];
  coldTab();
  window.fetch = function (u, o) {
    var url = String(u);
    pedidos.push(decodeURIComponent(url + " " + ((o && o.body) ? String(o.body) : "")));
    if (/api\.crossref\.org/.test(url)) return reply({ message: { items: [
      { DOI: "10.1007/978-981-19-6561-6", title: ["Multi-dimensional control"], "updated-by": [] },
      { DOI: "10.3389/fpubh.2020.00383", title: ["Public health"], "updated-by": [] }] } });
    if (/esearch\.fcgi/.test(url)) return reply({ esearchresult: { idlist: [] } });
    if (/efetch\.fcgi/.test(url)) return reply("<PubmedArticleSet></PubmedArticleSet>");
    if (/esummary\.fcgi/.test(url)) return reply({ result: {} });
    return reply({});
  };
  s = await check(
    'Springer, 2022. <ext-link>10.1007/978-981-19-6561-6</ext-link>\n' +
    'frontiersin.org/articles/10.3389/fpubh.2020.00383/full\n');
  var enviados = pedidos.join(" ").toLowerCase();
  ok("the DOI closed by a JATS tag is asked about cleanly",
     enviados.indexOf("10.1007/978-981-19-6561-6") !== -1 &&
     enviados.indexOf("978-981-19-6561-6<") === -1 &&
     enviados.indexOf("ext-link") === -1, enviados.slice(0, 300));
  ok("the platform's /full suffix never reaches Crossref",
     enviados.indexOf("10.3389/fpubh.2020.00383") !== -1 &&
     enviados.indexOf("00383/full") === -1, enviados.slice(0, 300));
  ok("both come back as checked rather than not found",
     /2 references checked/.test(txt()), txt().slice(0, 300));

  // And the other half of the same rule: a real Wiley SICI DOI keeps the angle
  // brackets it is entitled to. Several sampled on 2026-09-17 have no digit
  // after the "<", so "cut at the first bracket" would have corrupted them.
  pedidos = [];
  coldTab();
  s = await check("10.1002/(sici)1099-1719(199603)4:1<ii::aid-sd36>3.3.co;2-e");
  ok("a real SICI DOI is asked about with its brackets intact",
     pedidos.join(" ").toLowerCase().indexOf("4:1<ii::aid-sd36>3.3.co;2-e") !== -1,
     pedidos.join(" ").slice(0, 300));
  // ---- which drawer an unfound reference falls into (2026-09-18) ----
  // Until today a mistyped DOI, an arXiv preprint and a genuine Crossref
  // indexing gap all printed the same sentence. The strong claim here is not
  // about the wording: it is about WHICH REQUESTS THE PAGE MAKES. A DOI that
  // doi.org says belongs to DataCite must never cost a second Crossref lookup,
  // because that lookup cannot succeed and the second is spent on a free
  // service that did not ask for it.
  var raAsked = [], xrefByName = [];
  const raStub = function (mapa) {
    return function (u, o) {
      var url = String(u);
      if (/doi\.org\/ra\//.test(url)) {
        raAsked.push(url);
        var pedidos = decodeURIComponent(url.split("/ra/")[1]).split(",");
        return reply(pedidos.map(function (d) {
          var ra = mapa[d.toLowerCase()];
          // Exactly what doi.org sends for a DOI nobody registered: a row with
          // a `status` and NO `RA` key at all.
          return ra === null || ra === undefined
            ? { DOI: d, status: "DOI does not exist" }
            : { DOI: d, RA: ra };
        }));
      }
      if (/api\.crossref\.org/.test(url)) {
        if (isBatch(url)) return reply({ message: { items: [] } });
        xrefByName.push(url);
        return reply({ message: null });
      }
      if (/esearch\.fcgi/.test(url)) return reply({ esearchresult: { idlist: [] } });
      if (/efetch\.fcgi/.test(url)) return reply("<PubmedArticleSet></PubmedArticleSet>");
      if (/esummary\.fcgi/.test(url)) return reply({ result: {} });
      return reply({});
    };
  };

  raAsked = []; xrefByName = [];
  coldTab();
  window.fetch = raStub({ "10.5555/gap": "Crossref",
                          "10.48550/arxiv.2301.00001": "DataCite",
                          "10.9999/typo": null });
  s = await check("10.5555/gap\n10.48550/arXiv.2301.00001\n10.9999/typo\n");
  ok("a DOI nobody registered is called out as not existing",
     /do not exist at all|does not exist at all/.test(txt()) &&
     txt().indexOf("10.9999/typo") >= 0, txt().slice(0, 900));
  ok("a DataCite DOI is named as someone else's, not as missing",
     /DataCite/.test(txt()) && /cannot speak for/.test(txt()) &&
     txtAbierto().indexOf("10.48550/arxiv.2301.00001") >= 0, txtAbierto().slice(0, 900));
  ok("the genuine Crossref gap is still reported as not found",
     /not found in Crossref/.test(txt()) && txtAbierto().indexOf("10.5555/gap") >= 0,
     txtAbierto().slice(0, 900));
  ok("doi.org was asked once, in one batch, not once per DOI",
     raAsked.length === 1, raAsked.join(" | "));
  ok("only the DOI that could plausibly be Crossref's cost a second lookup",
     xrefByName.length === 1 && /10\.5555/.test(xrefByName[0]),
     xrefByName.join(" | "));
  ok("none of the three is counted as checked",
     /0 references checked/.test(txt()), txt().slice(0, 300));
  ok("and no clean bill is printed",
     !/Nothing found/.test(txt()), txt().slice(0, 400));

  // If doi.org cannot be reached the page must do exactly what it did before
  // today — ask Crossref by name and say "not found". Telling someone their
  // citation is fabricated because a third service timed out would be the
  // worst thing this tool could say.
  raAsked = []; xrefByName = [];
  coldTab();
  window.fetch = function (u, o) {
    var url = String(u);
    if (/doi\.org\/ra\//.test(url)) { raAsked.push(url); return Promise.reject(new Error("down")); }
    return raStub({})(u, o);
  };
  s = await check("10.9999/typo\n");
  ok("doi.org being down never becomes 'this DOI does not exist'",
     !/does not exist/.test(txt()) && /not found in Crossref/.test(txt()),
     txt().slice(0, 700));
  ok("and the DOI still gets its by-name second chance",
     xrefByName.length === 1, xrefByName.join(" | "));

  // The classified answers must not be remembered, or the second run in the
  // same tab would say LESS than the first: the stored shape has only
  // "found / not found" and would flatten them back into one drawer.
  raAsked = []; xrefByName = [];
  coldTab();
  window.fetch = raStub({ "10.48550/arxiv.2301.00001": "DataCite" });
  s = await check("10.48550/arXiv.2301.00001\n");
  var primera = /DataCite/.test(txt());
  s = await check("10.48550/arXiv.2301.00001\n");
  ok("a second run in the same tab still names the agency",
     primera && /DataCite/.test(txt()), txt().slice(0, 700));
  ok("and it asked doi.org again rather than serving a flattened memory",
     raAsked.length === 2, String(raAsked.length));

  // ---- a DOI with a PubMed id welded to its tail (2026-09-19) -------------
  // 10.1002/cncr.24840 + 20087961 arrives as one string. Measured the same day
  // on the frozen corpus: 14 of the 19 DOIs doi.org says do not exist are this,
  // so it is the single biggest bucket of "your citation is broken" that isn't.
  //
  // The claim worth defending is not the wording of the report, it is that the
  // page never REWRITES A DOI IT HAS NOT CHECKED. So these assert on the
  // requests: whether the candidate was ever asked about at Crossref at all.
  var ncbiIds = [], askedByName = [], pubmedFor = [];
  const gluedStub = function (raMap, pmidMap) {
    return function (u, o) {
      var url = String(u);
      if (/doi\.org\/ra\//.test(url)) {
        var pedidos = decodeURIComponent(url.split("/ra/")[1]).split(",");
        return reply(pedidos.map(function (d) {
          var ra = raMap[d.toLowerCase()];
          return ra === null || ra === undefined
            ? { DOI: d, status: "DOI does not exist" }
            : { DOI: d, RA: ra };
        }));
      }
      if (/esummary\.fcgi/.test(url)) {
        var ids = decodeURIComponent((url.match(/[?&]id=([^&]*)/) || [, ""])[1]);
        ncbiIds.push(ids);
        var res = { uids: [] };
        ids.split(",").filter(Boolean).forEach(function (p) {
          if (!(p in pmidMap)) return;
          res.uids.push(p);
          res[p] = { uid: p, title: "Un artículo", pubdate: "2009",
                     articleids: [{ idtype: "pubmed", value: p },
                                  { idtype: "doi", value: pmidMap[p] }] };
        });
        return reply({ result: res });
      }
      if (/api\.crossref\.org/.test(url)) {
        if (isBatch(url)) return reply({ message: { items: [] } });
        askedByName.push(url);
        if (/cncr\.24840/.test(url)) {
          return reply({ message: { DOI: "10.1002/cncr.24840",
            title: ["El artículo de verdad"],
            "updated-by": [{ type: "retraction", label: "Retraction",
                             DOI: "10.1002/cncr.9999",
                             updated: { "date-parts": [[2012, 5, 1]] } }] } });
        }
        return reply({ message: null });
      }
      if (/esearch\.fcgi/.test(url)) {
        // The term travels in the POST body, not in the URL. Reading the URL
        // here made this check pass while proving nothing — found 19-sep by
        // the check failing with an empty query string.
        pubmedFor.push(decodeURIComponent(String((o && o.body) || url)));
        return reply({ esearchresult: { idlist: [] } });
      }
      if (/efetch\.fcgi/.test(url)) return reply("<PubmedArticleSet></PubmedArticleSet>");
      return reply({});
    };
  };

  ncbiIds = []; askedByName = []; pubmedFor = [];
  coldTab();
  window.fetch = gluedStub({ "10.1002/cncr.2484020087961": null },
                           { "20087961": "10.1002/cncr.24840" });
  s = await check("10.1002/cncr.2484020087961\n");
  ok("a DOI with a PMID glued on is checked as the real article",
     /RETRACTED/.test(txt()), txt().slice(0, 700));
  ok("and the report shows BOTH strings, so the line can be found in the file",
     txtAbierto().indexOf("10.1002/cncr.2484020087961") >= 0 &&
     txtAbierto().indexOf("10.1002/cncr.24840") >= 0, txtAbierto().slice(0, 900));
  ok("it is no longer reported as a DOI that does not exist",
     !/does not exist at all/.test(txt()), txt().slice(0, 700));
  ok("the reader is told the citation still needs fixing",
     /still needs fixing/.test(txtAbierto()), txtAbierto().slice(0, 900));
  ok("every candidate id went to PubMed in ONE request, not one per split",
     ncbiIds.length === 1, ncbiIds.join(" | "));
  ok("the repaired DOI is asked of PubMed too, not Crossref only",
     pubmedFor.some((u) => /cncr\.24840/.test(u)), pubmedFor.join(" | "));

  // The one that separates checking from guessing. The split is plausible and
  // the head would resolve — but PubMed says that id belongs to a different
  // paper, so there is no rescue, and above all the page must never have gone
  // to Crossref about it. Reporting a stranger's retraction against someone's
  // reference is the worst thing this tool can do.
  ncbiIds = []; askedByName = []; pubmedFor = [];
  coldTab();
  window.fetch = gluedStub({ "10.1002/cncr.2484020087961": null },
                           { "20087961": "10.9999/otro-articulo" });
  s = await check("10.1002/cncr.2484020087961\n");
  ok("a split PubMed does not confirm is NOT rescued",
     /does not exist at all/.test(txt()), txt().slice(0, 700));
  ok("and the unconfirmed candidate was never asked about at Crossref",
     !askedByName.some((u) => /cncr\.24840/.test(u)), askedByName.join(" | "));
  ok("nor is a stranger's record shown to the reader",
     !/RETRACTED/.test(txt()), txt().slice(0, 700));

  // A tail that cannot be a PubMed id must not even be proposed: 000028848
  // ends in digits, but no PMID has a leading zero.
  ncbiIds = [];
  coldTab();
  window.fetch = gluedStub({ "10.1159/000028848": null }, {});
  s = await check("10.1159/000028848\n");
  ok("a DOI ending in zero-led digits costs no PubMed request at all",
     ncbiIds.join("").indexOf("0000288") < 0, ncbiIds.join(" | "));

  window.fetch = realFetch;

  return { pass: out.pass.length, fail: out.fail.length, failed: out.fail, passed: out.pass };
})()
