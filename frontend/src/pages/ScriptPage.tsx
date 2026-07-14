import { FileText, FolderOpen, RefreshCw, Save, Upload } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import { WorkflowHandoff } from "../components/WorkflowHandoff";
import { WorkspaceGuide } from "../components/WorkspaceGuide";
import {
  importScript,
  listScriptScenes,
  type SceneCollection,
  type ScriptScene,
  updateScriptScene,
} from "../services/scriptClient";
import { selectScriptFile } from "../services/desktopClient";

type ScriptLoadState = "loading" | "ready" | "empty" | "error";

export function ScriptPage() {
  const [collection, setCollection] = useState<SceneCollection | null>(null);
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null);
  const [draftText, setDraftText] = useState("");
  const [scriptPath, setScriptPath] = useState("");
  const [loadState, setLoadState] = useState<ScriptLoadState>("loading");
  const [message, setMessage] = useState("Loading scenes...");
  const [isImporting, setIsImporting] = useState(false);
  const [isSelectingFile, setIsSelectingFile] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const selectedScene = useMemo(
    () =>
      collection?.scenes.find((scene) => scene.id === selectedSceneId) ?? null,
    [collection, selectedSceneId],
  );
  const hasUnsavedChanges = Boolean(
    selectedScene && draftText !== selectedScene.text,
  );

  useEffect(() => {
    void loadScenes();
  }, []);

  useEffect(() => {
    setDraftText(selectedScene?.text ?? "");
  }, [selectedScene?.id, selectedScene?.text]);

  async function loadScenes() {
    setLoadState("loading");
    setMessage("Loading scenes...");
    try {
      acceptCollection(await listScriptScenes());
    } catch (error: unknown) {
      setLoadState("error");
      setMessage(error instanceof Error ? error.message : "Scenes unavailable");
    }
  }

  async function handleImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsImporting(true);
    try {
      const document = await importScript(scriptPath.trim());
      acceptCollection({
        schemaVersion: 1,
        sceneCount: document.sceneCount,
        scenes: document.scenes,
        updatedAt: document.importedAt,
      });
      setScriptPath("");
      setMessage(
        `Imported ${document.sceneCount} ${document.format.toUpperCase()} scene${document.sceneCount === 1 ? "" : "s"}.`,
      );
    } catch (error: unknown) {
      setLoadState("error");
      setMessage(error instanceof Error ? error.message : "Script import failed");
    } finally {
      setIsImporting(false);
    }
  }

  async function handleChooseScriptFile() {
    setIsSelectingFile(true);
    try {
      const selectedPath = await selectScriptFile();
      if (selectedPath) {
        setScriptPath(selectedPath);
        setMessage("Script file selected.");
      }
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "File picker unavailable");
    } finally {
      setIsSelectingFile(false);
    }
  }

  async function handleSaveScene() {
    if (!selectedScene || !draftText.trim()) return;
    setIsSaving(true);
    try {
      acceptCollection(await updateScriptScene(selectedScene.id, draftText));
      setMessage(`Scene ${selectedScene.order} saved.`);
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Scene save failed");
    } finally {
      setIsSaving(false);
    }
  }

  function acceptCollection(nextCollection: SceneCollection | null) {
    setCollection(nextCollection);
    if (!nextCollection || nextCollection.sceneCount === 0) {
      setLoadState("empty");
      setSelectedSceneId(null);
      setMessage("Import a TXT or SRT file to create scenes.");
      return;
    }
    setLoadState("ready");
    setSelectedSceneId((current) =>
      nextCollection.scenes.some((scene) => scene.id === current)
        ? current
        : (nextCollection.scenes[0]?.id ?? null),
    );
    setMessage(`${nextCollection.sceneCount} scenes loaded.`);
  }

  return (
    <section className="scriptWorkspace" aria-label="Script import and scenes">
      <header className="scriptToolbar">
        <div>
          <p className="eyebrow">Script</p>
          <h2>Import and edit scenes</h2>
          <p className="timelineMessage" role="status">
            {message}
          </p>
        </div>
        <button
          className="iconButton"
          title="Reload scenes"
          onClick={() => void loadScenes()}
        >
          <RefreshCw aria-hidden="true" size={18} />
        </button>
      </header>

      <WorkflowHandoff
        current="Script"
        nextLabel="Next: AI analysis"
        nextTo="/analysis"
        note="After scenes are imported and edited, move directly into AI keyword generation."
      />

      <section className="scriptImportPanel" aria-label="Import script">
        <form className="scriptImportForm" onSubmit={handleImport}>
          <label>
            TXT or SRT file path
            <span className="scriptPathControl">
              <input
                required
                value={scriptPath}
                onChange={(event) => setScriptPath(event.target.value)}
                placeholder="D:\\Scripts\\episode-01.srt"
              />
              <button
                className="secondaryButton"
                disabled={isSelectingFile || isImporting}
                onClick={() => void handleChooseScriptFile()}
                type="button"
              >
                <FolderOpen aria-hidden="true" size={16} />
                {isSelectingFile ? "Choosing" : "Choose file"}
              </button>
            </span>
          </label>
          <button className="primaryButton" disabled={isImporting} type="submit">
            <Upload aria-hidden="true" size={16} />
            {isImporting ? "Importing" : "Import script"}
          </button>
        </form>
      </section>

      {loadState === "empty" && (
        <WorkspaceGuide
          actionLabel="Open project"
          message="Create or open a project, then choose a TXT or SRT file above to create editable scenes."
          title="Start by importing a script"
          to="/projects"
          tone="warning"
        />
      )}
      {loadState === "error" && (
        <WorkspaceGuide
          actionLabel="Open project"
          message={message}
          title="Script workspace needs attention"
          to="/projects"
          tone="error"
        />
      )}

      <section className="scriptEditorGrid">
        <aside className="sceneListPanel" aria-label="Scene list">
          <div className="sceneListHeader">
            <h3>Scenes</h3>
            <span>{collection?.sceneCount ?? 0}</span>
          </div>
          {loadState === "ready" && collection ? (
            <div className="scriptSceneRows">
              {collection.scenes.map((scene) => (
                <button
                  className={`scriptSceneRow${
                    scene.id === selectedSceneId ? " active" : ""
                  }`}
                  key={scene.id}
                  onClick={() => setSelectedSceneId(scene.id)}
                  type="button"
                >
                  <strong>Scene {scene.order}</strong>
                  <span>{scene.text}</span>
                </button>
              ))}
            </div>
          ) : (
            <p className="emptyState">
              {loadState === "loading" ? "Loading scenes..." : "No scenes available."}
            </p>
          )}
        </aside>

        <article className="sceneEditorPanel" aria-label="Scene editor">
          {selectedScene ? (
            <SceneEditor
              draftText={draftText}
              hasUnsavedChanges={hasUnsavedChanges}
              isSaving={isSaving}
              scene={selectedScene}
              onChange={setDraftText}
              onSave={() => void handleSaveScene()}
            />
          ) : (
            <div className="sceneEditorEmpty">
              <FileText aria-hidden="true" size={28} />
              <p>Import a script to start editing scenes.</p>
            </div>
          )}
        </article>
      </section>
    </section>
  );
}

interface SceneEditorProps {
  scene: ScriptScene;
  draftText: string;
  hasUnsavedChanges: boolean;
  isSaving: boolean;
  onChange: (text: string) => void;
  onSave: () => void;
}

function SceneEditor({
  scene,
  draftText,
  hasUnsavedChanges,
  isSaving,
  onChange,
  onSave,
}: SceneEditorProps) {
  return (
    <>
      <div className="sceneEditorHeader">
        <div>
          <p className="eyebrow">Scene {scene.order}</p>
          <h3>{scene.id}</h3>
          <small>{formatSceneTiming(scene)}</small>
        </div>
        <button
          className="primaryButton"
          disabled={!hasUnsavedChanges || isSaving || !draftText.trim()}
          onClick={onSave}
          type="button"
        >
          <Save aria-hidden="true" size={16} />
          {isSaving ? "Saving" : "Save scene"}
        </button>
      </div>
      <label className="sceneTextEditor">
        Scene text
        <textarea
          value={draftText}
          onChange={(event) => onChange(event.target.value)}
          rows={12}
        />
      </label>
    </>
  );
}

function formatSceneTiming(scene: ScriptScene): string {
  if (scene.startMilliseconds === null || scene.endMilliseconds === null) {
    return "Untimed TXT scene";
  }
  return `${formatTime(scene.startMilliseconds)} - ${formatTime(scene.endMilliseconds)}`;
}

function formatTime(milliseconds: number): string {
  const totalSeconds = Math.floor(milliseconds / 1_000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}
