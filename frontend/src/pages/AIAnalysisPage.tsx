import { Brain, RefreshCw, Search, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { WorkflowHandoff } from "../components/WorkflowHandoff";
import { WorkspaceGuide } from "../components/WorkspaceGuide";
import {
  analyzeScenesBatch,
  listSceneAnalyses,
  type SceneAnalysisResult,
} from "../services/aiClient";
import {
  listScriptScenes,
  type SceneCollection,
  type ScriptScene,
} from "../services/scriptClient";

const providerOptions = ["ollama", "openai", "gemini"];

const defaultModels: Record<string, string> = {
  ollama: "llama3.2",
  openai: "gpt-4.1-mini",
  gemini: "gemini-1.5-flash",
};

export function AIAnalysisPage() {
  const [scenes, setScenes] = useState<SceneCollection | null>(null);
  const [analyses, setAnalyses] = useState<SceneAnalysisResult[]>([]);
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null);
  const [providerId, setProviderId] = useState("ollama");
  const [model, setModel] = useState(defaultModels.ollama);
  const [contentType, setContentType] = useState("news");
  const [language, setLanguage] = useState("English");
  const [reanalyze, setReanalyze] = useState(false);
  const [message, setMessage] = useState("Loading AI analysis workspace...");
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const analysisBySceneId = useMemo(
    () => new Map(analyses.map((analysis) => [analysis.sceneId, analysis])),
    [analyses],
  );
  const selectedScene = useMemo(
    () => scenes?.scenes.find((scene) => scene.id === selectedSceneId) ?? null,
    [scenes, selectedSceneId],
  );
  const selectedAnalysis = selectedSceneId
    ? (analysisBySceneId.get(selectedSceneId) ?? null)
    : null;
  const analyzedCount = scenes?.scenes.filter((scene) =>
    analysisBySceneId.has(scene.id),
  ).length ?? 0;

  useEffect(() => {
    void loadWorkspace();
  }, []);

  async function loadWorkspace() {
    try {
      const [nextScenes, nextAnalyses] = await Promise.all([
        listScriptScenes(),
        listSceneAnalyses(),
      ]);
      setScenes(nextScenes);
      setAnalyses(nextAnalyses?.results ?? []);
      setSelectedSceneId((current) =>
        nextScenes?.scenes.some((scene) => scene.id === current)
          ? current
          : (nextScenes?.scenes[0]?.id ?? null),
      );
      setMessage(nextScenes ? "AI analysis workspace ready." : "Import a script first.");
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "AI analysis unavailable");
    }
  }

  async function handleAnalyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!scenes?.scenes.length) {
      setMessage("Import scenes before running AI analysis.");
      return;
    }
    setIsAnalyzing(true);
    setMessage("Analyzing scenes...");
    try {
      const result = await analyzeScenesBatch({
        contentType: contentType.trim(),
        language: language.trim(),
        providerId,
        model: model.trim() || null,
        reanalyze,
      });
      await loadWorkspace();
      setMessage(
        `Analyzed ${result.successCount} scenes, skipped ${result.skippedCount}, failed ${result.failureCount}.`,
      );
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Scene analysis failed");
    } finally {
      setIsAnalyzing(false);
    }
  }

  function handleProviderChange(nextProviderId: string) {
    setProviderId(nextProviderId);
    setModel(defaultModels[nextProviderId] ?? "");
  }

  return (
    <section className="analysisWorkspace" aria-label="AI analysis workspace">
      <header className="analysisWorkspaceHeader">
        <div>
          <p className="eyebrow">AI Analysis</p>
          <h2>Analyze scenes and prepare media keywords</h2>
          <p className="timelineMessage" role="status">
            {message}
          </p>
        </div>
        <button className="iconButton" title="Refresh analysis" onClick={() => void loadWorkspace()}>
          <RefreshCw aria-hidden="true" size={18} />
        </button>
      </header>

      <WorkflowHandoff
        current="AI"
        nextLabel="Next: Media search"
        nextTo="/media"
        note="Use approved keywords to search media without leaving the guided workflow."
      />

      <form className="analysisControls" onSubmit={handleAnalyze}>
        <label>
          Provider
          <select value={providerId} onChange={(event) => handleProviderChange(event.target.value)}>
            {providerOptions.map((provider) => (
              <option key={provider} value={provider}>
                {provider}
              </option>
            ))}
          </select>
        </label>
        <label>
          Model
          <input value={model} onChange={(event) => setModel(event.target.value)} />
        </label>
        <label>
          Content type
          <input value={contentType} onChange={(event) => setContentType(event.target.value)} />
        </label>
        <label>
          Language
          <input value={language} onChange={(event) => setLanguage(event.target.value)} />
        </label>
        <label className="inlineToggle">
          <input
            checked={reanalyze}
            onChange={(event) => setReanalyze(event.target.checked)}
            type="checkbox"
          />
          Reanalyze existing
        </label>
        <button className="primaryButton" disabled={isAnalyzing} type="submit">
          <Sparkles aria-hidden="true" size={16} />
          {isAnalyzing ? "Analyzing" : "Analyze all"}
        </button>
      </form>

      <div className="analysisSummary">
        <SummaryItem label="Scenes" value={scenes?.sceneCount ?? 0} />
        <SummaryItem label="Analyzed" value={analyzedCount} />
        <SummaryItem label="Keywords" value={keywordCount(analyses)} />
      </div>

      {!scenes?.scenes.length && (
        <WorkspaceGuide
          actionLabel="Go to Script"
          message="Import a TXT or SRT file first. AI analysis needs scene text before it can create descriptions, categories, and keywords."
          title="Import scenes before AI analysis"
          to="/pipeline"
          tone="warning"
        />
      )}
      {Boolean(scenes?.scenes.length) && analyzedCount === 0 && (
        <WorkspaceGuide
          actionLabel="Check setup"
          message="Choose a provider and run Analyze all. If the provider is not ready, open Settings to see the exact setup hint."
          title="Run analysis to unlock media keywords"
          to="/settings"
        />
      )}

      <div className="analysisGrid">
        <section className="analysisScenePanel" aria-label="Scenes for analysis">
          <PanelHeading title="Scenes" meta={`${analyzedCount}/${scenes?.sceneCount ?? 0} ready`} />
          <div className="analysisSceneList">
            {(scenes?.scenes ?? []).map((scene) => (
              <SceneButton
                analysis={analysisBySceneId.get(scene.id) ?? null}
                isSelected={scene.id === selectedSceneId}
                key={scene.id}
                onClick={() => setSelectedSceneId(scene.id)}
                scene={scene}
              />
            ))}
            {!scenes?.scenes.length && (
              <p className="emptyState">Import TXT or SRT scenes before analysis.</p>
            )}
          </div>
        </section>

        <section className="analysisDetailPanel" aria-label="Scene analysis detail">
          <PanelHeading
            title={selectedScene ? `Scene ${selectedScene.order}` : "Scene detail"}
            meta={selectedAnalysis ? selectedAnalysis.providerId : "Not analyzed"}
          />
          {selectedScene ? (
            <div className="analysisDetail">
              <p className="analysisSceneText">{selectedScene.text}</p>
              {selectedAnalysis ? (
                <AnalysisResult analysis={selectedAnalysis} />
              ) : (
                <div className="emptyState">
                  Run analysis to generate description, category, and keywords.
                </div>
              )}
            </div>
          ) : (
            <p className="emptyState">No scene selected.</p>
          )}
        </section>
      </div>
    </section>
  );
}

function SummaryItem({ label, value }: { label: string; value: number }) {
  return (
    <div className="analysisSummaryItem">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function PanelHeading({ title, meta }: { title: string; meta: string }) {
  return (
    <div className="analysisPanelHeading">
      <h3>{title}</h3>
      <span>{meta}</span>
    </div>
  );
}

function SceneButton({
  analysis,
  isSelected,
  onClick,
  scene,
}: {
  analysis: SceneAnalysisResult | null;
  isSelected: boolean;
  onClick: () => void;
  scene: ScriptScene;
}) {
  return (
    <button
      className={`analysisSceneRow${isSelected ? " selected" : ""}`}
      onClick={onClick}
      type="button"
    >
      <Brain aria-hidden="true" size={18} />
      <span>
        <strong>Scene {scene.order}</strong>
        <small>{analysis ? analysis.category : "Waiting for analysis"}</small>
      </span>
    </button>
  );
}

function AnalysisResult({ analysis }: { analysis: SceneAnalysisResult }) {
  const primaryKeyword = analysis.keywords[0] ?? "";
  return (
    <div className="analysisResult">
      <div>
        <span className="analysisLabel">Description</span>
        <p>{analysis.description}</p>
      </div>
      <div>
        <span className="analysisLabel">Category</span>
        <strong>{analysis.category}</strong>
      </div>
      <div>
        <span className="analysisLabel">Keywords</span>
        <div className="keywordList">
          {analysis.keywords.map((keyword) => (
            <Link
              className="keywordChip"
              key={keyword}
              to={`/media?query=${encodeURIComponent(keyword)}`}
            >
              {keyword}
            </Link>
          ))}
        </div>
      </div>
      {primaryKeyword && (
        <Link className="primaryButton analysisMediaLink" to={`/media?query=${encodeURIComponent(primaryKeyword)}`}>
          <Search aria-hidden="true" size={16} />
          Search media
        </Link>
      )}
    </div>
  );
}

function keywordCount(analyses: SceneAnalysisResult[]): number {
  return new Set(analyses.flatMap((analysis) => analysis.keywords)).size;
}
