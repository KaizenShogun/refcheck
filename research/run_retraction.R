# Half of measure_vs_retraction.py: runs the R package `retraction` (0.1.0) on a
# CSV with a `doi` column. Run in a container, nothing installed on the host:
#   docker run --rm -v $PWD:/w -w /w rocker/r-ver:4.5 Rscript run_retraction.R xera dois.csv out.csv
# sources: xera (its default, Retraction Watch), all, or a comma list. MIT.
.libPaths(Sys.getenv("RLIB", "/w/rlib")); suppressMessages(library(retraction))
a <- commandArgs(TRUE); src <- a[1]; inp <- a[2]; out <- a[3]
d <- read.csv(inp, stringsAsFactors=FALSE)
s <- if (src == "all") "all" else strsplit(src, ",")[[1]]
t0 <- Sys.time()
r <- check_dois(unique(d$doi), sources=s, progress=FALSE)
r <- as.data.frame(r)
keep <- c("id","doi","matched","status","is_retracted","nature","sources","disagreement","disagreeing")
r <- r[, keep]; r[] <- lapply(r, function(x) if (is.list(x)) sapply(x, paste, collapse="|") else x)
write.csv(r, out, row.names=FALSE)
cat(src, nrow(r), "rows in", format(Sys.time()-t0), "\n"); print(table(r$status, useNA="ifany"))
