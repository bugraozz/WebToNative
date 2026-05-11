import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  convertProject,
  getAnalyzeResult,
  getAnalyzeStatus,
  getApiBase,
  startAnalyze,
} from "./api";
import type { DetectedSummary, Report, Selection, StatusResponse } from "./types";

const emptyDetected: DetectedSummary = {
  frontend: [],
  backend: [],
  database: [],
  styles: [],
  payments: [],
  docker: [],
  notes: [],
};

const withFallback = (items: string[]) => (items.length > 0 ? items : ["unknown"]);

const buildDefaultSelection = (detected: DetectedSummary): Selection => ({
  frontend: withFallback(detected.frontend)[0],
  backend: withFallback(detected.backend)[0],
  database: withFallback(detected.database)[0],
  styles: withFallback(detected.styles)[0],
});

const getDownloadUrl = (path: string) => {
  if (path.startsWith("http")) {
    return path;
  }
  const base = getApiBase().replace(/\/api$/, "");
  return `${base}${path}`;
};

const formatPercent = (value: number) => `${Math.round(value * 100)}%`;

const formatDuration = (seconds?: number | null) => {
  if (seconds === null || seconds === undefined) {
    return "Calculating...";
  }
  const safeSeconds = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(safeSeconds / 60);
  const remainder = safeSeconds % 60;
  return `${minutes}:${remainder.toString().padStart(2, "0")}`;
};

const countDetected = (items: string[]) => items.filter((item) => item && item !== "unknown").length;

export default function App() {
  const [mode, setMode] = useState<"zip" | "git">("zip");
  const [file, setFile] = useState<File | null>(null);
  const [repoUrl, setRepoUrl] = useState("");
  const [detected, setDetected] = useState<DetectedSummary>(emptyDetected);
  const [selection, setSelection] = useState<Selection>({});
  const [jobId, setJobId] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "analyzing" | "converting">("idle");
  const [error, setError] = useState<string | null>(null);
  const [analysisStatus, setAnalysisStatus] = useState<StatusResponse | null>(null);
  const [analysisElapsed, setAnalysisElapsed] = useState(0);

  const pollRef = useRef<number | null>(null);
  const timerRef = useRef<number | null>(null);

  const canAnalyze = useMemo(() => {
    if (status !== "idle") {
      return false;
    }
    if (mode === "zip") {
      return Boolean(file);
    }
    return repoUrl.trim().length > 0;
  }, [file, repoUrl, mode, status]);

  const stopTimers = () => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  useEffect(() => {
    return () => stopTimers();
  }, []);

  const frontendOptions = useMemo(
    () => withFallback(detected.frontend),
    [detected.frontend]
  );
  const backendOptions = useMemo(
    () => withFallback(detected.backend),
    [detected.backend]
  );
  const databaseOptions = useMemo(
    () => withFallback(detected.database),
    [detected.database]
  );
  const stylesOptions = useMemo(
    () => withFallback(detected.styles),
    [detected.styles]
  );

  const analysisReady = useMemo(() => analysisStatus?.state === "done", [analysisStatus]);
  const analysisComplete = analysisReady && status === "idle";
  const analysisSummary = useMemo(
    () => ({
      frontend: countDetected(detected.frontend),
      backend: countDetected(detected.backend),
      database: countDetected(detected.database),
      styles: countDetected(detected.styles),
      payments: countDetected(detected.payments),
    }),
    [detected]
  );
  const canConvert = useMemo(
    () => status === "idle" && Boolean(jobId) && analysisReady,
    [jobId, status, analysisReady]
  );

  const handleAnalyze = async () => {
    setError(null);
    setReport(null);
    setDownloadUrl(null);
    setDetected(emptyDetected);
    setSelection({});
    setJobId(null);
    setAnalysisStatus(null);
    setAnalysisElapsed(0);
    stopTimers();
    setStatus("analyzing");

    try {
      const response = await startAnalyze({
        file: mode === "zip" ? file : undefined,
        repoUrl: mode === "git" ? repoUrl.trim() : undefined,
      });
      setJobId(response.job_id);
      setAnalysisStatus(response.status);

      const startedAt = Date.now();
      timerRef.current = window.setInterval(() => {
        setAnalysisElapsed(Math.floor((Date.now() - startedAt) / 1000));
      }, 1000);

      pollRef.current = window.setInterval(async () => {
        try {
          const latest = await getAnalyzeStatus(response.job_id);
          setAnalysisStatus(latest);

          if (latest.state === "done") {
            stopTimers();
            const result = await getAnalyzeResult(response.job_id);
            setDetected(result.detected);
            setSelection(buildDefaultSelection(result.detected));
            setStatus("idle");
          } else if (latest.state === "error") {
            stopTimers();
            setError(latest.error || "Analyze failed");
            setStatus("idle");
          }
        } catch (pollError) {
          stopTimers();
          setError(pollError instanceof Error ? pollError.message : "Status check failed");
          setStatus("idle");
        }
      }, 1200);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analyze failed");
      setStatus("idle");
    }
  };

  const handleConvert = async () => {
    if (!jobId) {
      return;
    }

    setError(null);
    setReport(null);
    setDownloadUrl(null);
    setStatus("converting");

    try {
      const resolvedSelection: Selection = {
        frontend: selection.frontend ?? frontendOptions[0],
        backend: selection.backend ?? backendOptions[0],
        database: selection.database ?? databaseOptions[0],
        styles: selection.styles ?? stylesOptions[0],
      };
      const response = await convertProject({ job_id: jobId, selection: resolvedSelection });
      setReport(response.report);
      setDownloadUrl(getDownloadUrl(response.download_url));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Convert failed");
    } finally {
      setStatus("idle");
    }
  };

  return (
    <div className="page">
      <main className="container">
        <header className="hero">
          <span className="badge">Web to Native</span>
          <h1>Convert web projects into React Native output.</h1>
          <p>
            Upload a ZIP or provide a Git URL, select the stacks, and generate a
            conversion report with a starter React Native structure.
          </p>
        </header>

        <section className="panel">
          <div className="panel-header">
            <h2>Project input</h2>
            <div className="tabs">
              <button
                className={mode === "zip" ? "tab active" : "tab"}
                onClick={() => setMode("zip")}
              >
                ZIP upload
              </button>
              <button
                className={mode === "git" ? "tab active" : "tab"}
                onClick={() => setMode("git")}
              >
                Git URL
              </button>
            </div>
          </div>
          <div className="panel-body">
            {mode === "zip" ? (
              <div className="input-row">
                <input
                  key="zip-file"
                  className="input"
                  type="file"
                  accept=".zip"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
                <button className="btn-primary" onClick={handleAnalyze} disabled={!canAnalyze}>
                  {status === "analyzing" ? "Analyzing..." : "Analyze"}
                </button>
              </div>
            ) : (
              <div className="input-row">
                <input
                  key="git-url"
                  className="input"
                  type="text"
                  placeholder="https://github.com/org/repo"
                  value={repoUrl}
                  onChange={(event) => setRepoUrl(event.target.value)}
                />
                <button className="btn-primary" onClick={handleAnalyze} disabled={!canAnalyze}>
                  {status === "analyzing" ? "Analyzing..." : "Analyze"}
                </button>
              </div>
            )}
            {status === "analyzing" && analysisStatus ? (
              <div className="analysis-status">
                <div className="status-row">
                  <span className="status-pill">{analysisStatus.step}</span>
                  <span className="muted timer">
                    Elapsed {formatDuration(analysisElapsed)}
                  </span>
                  <span className="muted timer">
                    ETA {formatDuration(analysisStatus.eta_seconds)}
                  </span>
                </div>
                <div className="progress progress-strong">
                  <span style={{ width: `${analysisStatus.progress}%` }} />
                </div>
                {analysisElapsed > 90 ? (
                  <span className="muted">Large repos can take a few minutes.</span>
                ) : null}
              </div>
            ) : null}
          </div>
        </section>

        {analysisComplete ? (
          <section className="panel analysis-complete">
            <div className="analysis-banner">
              <div>
                <span className="status-pill success">Analysis complete</span>
                <h2>Project scan finished</h2>
                <p className="muted">
                  Completed in {formatDuration(analysisElapsed)}. Review detected stacks below.
                </p>
              </div>
              <div className="analysis-metrics">
                <div className="metric-tile">
                  <span className="label">Frontend</span>
                  <span className="value">{analysisSummary.frontend}</span>
                </div>
                <div className="metric-tile">
                  <span className="label">Backend</span>
                  <span className="value">{analysisSummary.backend}</span>
                </div>
                <div className="metric-tile">
                  <span className="label">Database</span>
                  <span className="value">{analysisSummary.database}</span>
                </div>
                <div className="metric-tile">
                  <span className="label">Styles</span>
                  <span className="value">{analysisSummary.styles}</span>
                </div>
                <div className="metric-tile">
                  <span className="label">Payments</span>
                  <span className="value">{analysisSummary.payments}</span>
                </div>
              </div>
            </div>
          </section>
        ) : null}

        <section className="panel">
          <div className="panel-header">
            <div className="panel-title-group">
              <h2>Detected stacks</h2>
              <span className="muted">Choose or override before converting.</span>
            </div>
            {analysisComplete ? <span className="status-pill success">Ready</span> : null}
          </div>
          <div className="panel-grid">
            <div className="field">
              <label>Frontend</label>
              <select
                className="input"
                value={selection.frontend ?? frontendOptions[0]}
                onChange={(event) => setSelection({ ...selection, frontend: event.target.value })}
              >
                {frontendOptions.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Backend</label>
              <select
                className="input"
                value={selection.backend ?? backendOptions[0]}
                onChange={(event) => setSelection({ ...selection, backend: event.target.value })}
              >
                {backendOptions.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Database</label>
              <select
                className="input"
                value={selection.database ?? databaseOptions[0]}
                onChange={(event) => setSelection({ ...selection, database: event.target.value })}
              >
                {databaseOptions.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Styles</label>
              <select
                className="input"
                value={selection.styles ?? stylesOptions[0]}
                onChange={(event) => setSelection({ ...selection, styles: event.target.value })}
              >
                {stylesOptions.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="panel-footer">
            <div className="chips">
              {detected.payments.map((item) => (
                <span key={item} className="badge success">
                  {item}
                </span>
              ))}
              {detected.docker.map((item) => (
                <span key={item} className="badge ghost">
                  {item}
                </span>
              ))}
              {detected.notes.map((item) => (
                <span key={item} className="badge warning">
                  {item}
                </span>
              ))}
            </div>
            <button className="btn-primary" onClick={handleConvert} disabled={!canConvert}>
              {status === "converting" ? "Converting..." : "Convert"}
            </button>
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2>Conversion report</h2>
            <span className="muted">Score and manual fixes for React Native.</span>
          </div>
          {error ? <div className="alert danger">{error}</div> : null}
          {report ? (
            <div className="report">
              <div className="report-metrics">
                <div className="metric">
                  <span className="label">Score</span>
                  <strong>{formatPercent(report.score)}</strong>
                  <div className="progress">
                    <span style={{ width: formatPercent(report.score) }} />
                  </div>
                </div>
                <div className="metric">
                  <span className="label">Success rate</span>
                  <strong>{formatPercent(report.success_rate)}</strong>
                  <span className="subtext">
                    {report.files_converted} of {report.files_total} files
                  </span>
                </div>
              </div>
              <div className="report-grid">
                <div>
                  <h3>Issues</h3>
                  {report.issues.length ? (
                    <ul>
                      {report.issues.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="muted">No issues detected.</p>
                  )}
                </div>
                <div>
                  <h3>Warnings</h3>
                  {report.warnings.length ? (
                    <ul>
                      {report.warnings.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="muted">No warnings.</p>
                  )}
                </div>
              </div>
              {downloadUrl ? (
                <a className="btn-ghost" href={downloadUrl}>
                  Download React Native output
                </a>
              ) : null}
            </div>
          ) : (
            <p className="muted">Run analyze and convert to see a report.</p>
          )}
        </section>
      </main>
    </div>
  );
}
